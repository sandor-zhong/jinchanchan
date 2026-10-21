"""Reference integrity and statistical evidence rules, independent of live inputs."""
from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.catalog import get_catalog, index
from app.main import app
from app.reference import get_reference, item_reason
from app.statistics import StatisticsSnapshot, load_statistics, rankings


def test_complete_static_handbook_and_detail_apis():
    data = get_catalog()
    with TestClient(app) as client:
        ref = client.get('/api/v1/guidebook').json()
        for key in ('heroes', 'lineups', 'augments'):
            assert set(ref[key]) == {r['id'] for r in data[key]}
        assert len(ref['fundamentals']) == 4
        assert client.get('/api/v1/heroes/13213').json()['study']['builds']
        assert client.get('/api/v1/lineups/2244/guide').json()['choose_when']
        assert client.get('/api/v1/augments/2922').json()['study']['category'] == '英雄专属'
        assert client.get('/api/v1/augments/unknown').status_code == 404
        assert client.get('/api/v1/lineups/unknown/guide').status_code == 404
        assert client.get('/api/v1/rankings?metric=score').status_code == 422


def test_roll_window_is_distinct_from_final_roster_and_special_prerequisites():
    profiles = get_reference()['lineups']
    assert (profiles['2244']['roll_level'], profiles['2244']['final_level']) == (7, 9)
    assert profiles['2310']['route_type'] == 'level'  # A 95 title overrides a low-cost carry tag.
    assert profiles['2310']['notes'][-1].startswith('官网标题与主C标记存在差异')
    assert profiles['2233']['route_type'] == 'special'
    assert '2922' in profiles['2233']['prerequisites'][0]['ids']
    assert any(p['kind'] == 'unverified' for p in profiles['2395']['prerequisites'])


def test_official_augment_relations_are_bidirectional_and_explained():
    data, ref = get_catalog(), get_reference()
    for lineup in data['lineups']:
        for aid in lineup['augment_ids']:
            forward = next(r for r in ref['lineups'][lineup['id']]['augment_matches'] if r['augment_id'] == aid)
            reverse = next(r for r in ref['augments'][aid]['lineups'] if r['lineup_id'] == lineup['id'])
            assert forward == reverse
            assert forward['basis'] == 'official_primary'
            assert forward['reason_evidence_type'] == 'assistant_analysis'
    bard = ref['lineups']['2244']['augment_matches']
    assert any('持续攻击' in r['reason'] for r in bard if r['augment_id'] == '2483')


def test_inferred_rune_matches_respect_fee_and_random_reward_constraints():
    data, ref = get_catalog(), get_reference()
    heroes, lineups = index(data['heroes']), index(data['lineups'])
    for match in ref['augments']['1020']['lineups']:
        if match['basis'] == 'mechanic_inference':
            assert heroes[lineups[match['lineup_id']]['carry_ids'][0]]['cost'] <= 2
    for aid in ('20021', '30021', '1017', '2017', '3017'):
        assert not any(r['basis'] == 'mechanic_inference' for r in ref['augments'][aid]['lineups'])
    assert any('随机' in c for c in ref['augments']['20021']['cautions'])
    assert any(r['lineup_id'] == '2233' and r['basis'] == 'mechanic_inference' for r in ref['augments']['3922']['lineups'])


def test_unit_analysis_keeps_real_builds_and_flags_overlapping_utility():
    data, ref = get_catalog(), get_reference()
    bard = ref['heroes']['13213']
    assert bard['damage_type'] == '物理 / 魔法'
    assert any(len(b['item_ids']) != len(set(b['item_ids'])) for b in bard['builds'])
    assert ref['heroes']['15177']['builds']  # Shop entry inherits Xayah/Rakan builds.
    zyra = next(h for h in data['heroes'] if h['name'] == '婕拉')
    burn = next(i for i in data['items'] if '莫雷洛' in i['name'] and '重伤' in i['description'])
    assert '已经包含重伤' in item_reason(burn, zyra)['reasons'][0]
    assert not any('提供续航' in r for r in item_reason(burn)['reasons'])
    shred = next(i for i in data['items'] if i['name'] == '最后的轻语')
    assert not any('生存或承伤' in r for r in item_reason(shred)['reasons'])
    healing = next(i for i in data['items'] if i['name'] == '海克斯科技枪刃')
    assert any('提供续航' in r for r in item_reason(healing)['reasons'])


@pytest.fixture()
def stats_file(tmp_path, monkeypatch):
    path = tmp_path / 'statistics.json'
    monkeypatch.setenv('STATISTICS_PATH', str(path))
    load_statistics.cache_clear()
    yield path
    load_statistics.cache_clear()


def snapshot_payload():
    """Synthetic placement records are test fixtures, never production data."""
    now = datetime.now(timezone.utc)
    return {
        'season': 'S100030', 'data_version': get_catalog()['meta']['version'],
        'source_name': 'Synthetic test fixture', 'source_url': 'https://example.com/test-fixture',
        'region': 'CN', 'rank_scope': 'test only',
        'lineup_definition': 'Synthetic unit test lineup mapping only.',
        'period_start': (now - timedelta(days=2)).isoformat(),
        'period_end': (now - timedelta(days=1)).isoformat(),
        'samples': [
            {'lineup_id': '2244', 'placement_counts': [1, 2, 3, 4, 0, 0, 0, 0]},
            {'lineup_id': '2202', 'placement_counts': [20, 10, 10, 10, 10, 10, 10, 20]},
        ],
    }


def test_missing_statistics_does_not_fabricate_rankings(stats_file):
    result = rankings()
    assert result['status'] == 'unavailable'
    assert result['rows'] == []
    assert 'source' not in result


def test_real_count_formulas_filtering_and_source_metadata(stats_file):
    stats_file.write_text(json.dumps(snapshot_payload()), encoding='utf-8')
    result = rankings(min_samples=30)
    assert result['status'] == 'available'
    assert len(result['rows']) == 1
    row = result['rows'][0]
    assert row['lineup_id'] == '2202'
    assert row['sample_count'] == 100
    assert row['top4_rate'] == .5
    assert row['first_rate'] == .2
    assert row['average_placement'] == 4.5
    assert result['source']['rank_scope'] == 'test only'
    assert 'samples' not in result['source']
    assert rankings('average_placement', 1)['rows'][0]['lineup_id'] == '2244'


@pytest.mark.parametrize('change,expected', [
    ({'data_version': 'outdated'}, 'version_mismatch'),
    ({'samples': [{'lineup_id': 'unknown', 'placement_counts': [1] * 8}]}, 'invalid_mapping'),
    ({'period_end': (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(),
      'period_start': (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()}, 'stale'),
])
def test_unusable_statistics_are_hidden_or_marked_historical(stats_file, change, expected):
    payload = {**snapshot_payload(), **change}
    stats_file.write_text(json.dumps(payload), encoding='utf-8')
    result = rankings()
    assert result['status'] == expected
    if expected != 'stale':
        assert not result['rows']


@pytest.mark.parametrize('counts', [[0] * 8, [-1] + [1] * 7, [1] * 7, [True] + [1] * 7, ['2'] + [1] * 7])
def test_invalid_placement_counts_are_rejected(counts):
    payload = snapshot_payload()
    payload['samples'][0]['placement_counts'] = counts
    with pytest.raises(ValidationError):
        StatisticsSnapshot.model_validate(payload)


@pytest.mark.parametrize('field,value', [
    ('season', 'S18'),
    ('period_end', '2099-01-01T00:00:00Z'),
    ('period_start', '2026-01-01T00:00:00'),
])
def test_cross_season_future_and_naive_periods_are_rejected(field, value):
    with pytest.raises(ValidationError):
        StatisticsSnapshot.model_validate({**snapshot_payload(), field: value})


def test_duplicate_statistical_rosters_are_rejected():
    payload = snapshot_payload()
    payload['samples'].append(payload['samples'][0])
    with pytest.raises(ValidationError):
        StatisticsSnapshot.model_validate(payload)
