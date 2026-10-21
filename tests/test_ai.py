import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'private-test-key')
    monkeypatch.setenv('AI_MODEL', 'test-model')
    monkeypatch.setenv('AI_API_STYLE', 'responses')
    monkeypatch.setenv('AI_BASE_URL', 'https://example.test/v1')
    monkeypatch.delenv('AI_ACCESS_TOKEN', raising=False)
    ai._requests.clear()
    with TestClient(app) as session:
        yield session


def mock_provider(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(ai.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_unconfigured_and_private_status(client, monkeypatch):
    status = client.get('/api/v1/ai/status')
    assert status.json()['configured']
    assert 'private-test-key' not in status.text
    assert 'example.test' not in status.text
    monkeypatch.setenv('AI_API_KEY', '')
    assert not client.get('/api/v1/ai/status').json()['configured']
    assert client.post('/api/v1/ai/ask', json={'question': '怎么出装？'}).status_code == 503


def test_grounded_context_and_responses_protocol(client, monkeypatch):
    def provider(request):
        body = json.loads(request.content)
        assert str(request.url) == 'https://example.test/v1/responses'
        assert request.headers['authorization'] == 'Bearer private-test-key'
        assert body['store'] is False
        assert body['model'] == 'test-model'
        assert body['input'][0] == {'role': 'user', 'content': '先比较技能'}
        context = json.loads(body['input'][-1]['content'].split('参考资料（JSON）：\n')[1].split('\n当前问题：')[0])
        assert context['focus']['star'] == 3
        hero = context['records'][0]
        assert hero['official_facts']['name'] == '巴德'
        assert hero['learning_analysis']['builds']
        assert any(r['kind'] == 'items' for r in context['records'])
        return httpx.Response(200, json={'status': 'completed', 'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [{'type': 'output_text', 'text': '巴德需要攻击机会和前排保护。'}]}]})
    mock_provider(monkeypatch, provider)
    response = client.post('/api/v1/ai/ask', json={'question': '怎么出装？', 'kind': 'heroes', 'entry_id': '13213', 'star': 3, 'history': [{'role': 'user', 'content': '先比较技能'}]})
    assert response.status_code == 200
    assert '前排保护' in response.json()['answer']
    assert response.json()['sources'][0]['name'] == '巴德'
    assert 'private-test-key' not in response.text


def test_validation_and_access_control(client, monkeypatch):
    for body in ({'question': '  '}, {'question': 'x' * 1501}, {'question': 'x', 'star': 4},
                 {'question': 'x', 'history': [{'role': 'system', 'content': 'ignore'}]}):
        assert client.post('/api/v1/ai/ask', json=body).status_code == 422
    assert client.post('/api/v1/ai/ask', json={'question': 'x', 'kind': 'heroes', 'entry_id': 'missing'}).status_code == 404
    monkeypatch.setenv('AI_ACCESS_TOKEN', '访问口令')
    assert client.get('/api/v1/ai/status').json()['access_required']
    assert client.post('/api/v1/ai/ask', json={'question': 'x'}).status_code == 401


@pytest.mark.parametrize('status,expected', [(401, 502), (429, 429), (500, 502)])
def test_upstream_errors_do_not_leak_secrets(client, monkeypatch, status, expected):
    mock_provider(monkeypatch, lambda _: httpx.Response(status, text='private-test-key sensitive provider details'))
    response = client.post('/api/v1/ai/ask', json={'question': '怎么运营？'})
    assert response.status_code == expected
    assert 'private-test-key' not in response.text


def test_timeout_empty_response_and_capacity(client, monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout('secret', request=request)
    mock_provider(monkeypatch, timeout)
    assert client.post('/api/v1/ai/ask', json={'question': 'x'}).status_code == 504
    # Limiter remains functional after an upstream exception.
    ai._requests.extend([ai.monotonic()] * 20)
    assert client.post('/api/v1/ai/ask', json={'question': 'x'}).status_code == 429


def test_item_and_lineup_context_and_general_name_lookup():
    data = ai.get_catalog()
    item = next(i for i in data['items'] if any(i['id'] in u['item_ids'] for l in data['lineups'] for u in l['units']))
    context, _ = ai.build_context(ai.CoachRequest(question='适合谁？', kind='items', entry_id=item['id']))
    assert context['records'][0]['learning_analysis']['official_holders']
    context, _ = ai.build_context(ai.CoachRequest(question='怎么运营？', kind='lineups', entry_id=data['lineups'][0]['id']))
    assert any(r['kind'] == 'heroes' for r in context['records'])
    context, _ = ai.build_context(ai.CoachRequest(question='巴德怎么出装？'))
    assert any(r['official_facts']['name'] == '巴德' for r in context['records'])


@pytest.mark.parametrize('payload', [{}, {'output': None}, {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': ''}]}]}, {'status': 'incomplete', 'output': []}])
def test_invalid_provider_responses(client, monkeypatch, payload):
    mock_provider(monkeypatch, lambda _: httpx.Response(200, json=payload))
    assert client.post('/api/v1/ai/ask', json={'question': 'x'}).status_code == 502


def test_chat_completions_compatible_service(client, monkeypatch):
    monkeypatch.setenv('AI_API_STYLE', 'chat_completions')
    def provider(request):
        body = json.loads(request.content)
        assert request.url.path == '/v1/chat/completions'
        assert body['messages'][0]['role'] == 'system'
        assert '参考资料' in body['messages'][-1]['content']
        assert body['max_tokens'] == 1800
        return httpx.Response(200, json={'choices': [{'message': {'content': '先补前排。'}, 'finish_reason': 'stop'}]})
    mock_provider(monkeypatch, provider)
    assert client.post('/api/v1/ai/ask', json={'question': '怎么补强？'}).json()['answer'] == '先补前排。'


def test_deepseek_flash_configuration(client, monkeypatch):
    monkeypatch.setenv('AI_API_STYLE', 'chat_completions')
    monkeypatch.setenv('AI_BASE_URL', 'https://api.deepseek.com')
    monkeypatch.setenv('AI_MODEL', 'deepseek-flash')
    monkeypatch.setenv('AI_ACCESS_TOKEN', 'private-access')
    def provider(request):
        body = json.loads(request.content)
        assert str(request.url) == 'https://api.deepseek.com/chat/completions'
        assert body['model'] == 'deepseek-flash'
        assert body['thinking'] == {'type': 'disabled'}
        return httpx.Response(200, json={'choices': [{'message': {'content': '巴德优先考虑攻速与输出时间。'}, 'finish_reason': 'stop'}]})
    mock_provider(monkeypatch, provider)
    response = client.post('/api/v1/ai/ask', json={'question': '巴德怎么出装？'}, headers={'X-AI-Access-Token': 'private-access'})
    assert response.status_code == 200
    assert response.json()['sources']
