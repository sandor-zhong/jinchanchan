from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.catalog import get_catalog, index, validate_catalog
from app.main import app
from app.recommend import RecommendRequest, equipment_plan, rank_lineups


@pytest.fixture()
def client():
    with TestClient(app) as session:
        yield session


def test_bundled_snapshot_is_complete_and_current_season():
    data = get_catalog()
    validate_catalog(data)
    assert len(data["lineups"]) >= 40
    assert len(data["augments"]) >= 200
    assert all(s["url"].startswith("https://game.gtimg.cn/") for s in data["sources"])
    assert any(p["name"] == "一元店" for p in data["portals"])


def test_health_home_and_documented_api(client):
    assert client.get("/healthz").json()["status"] == "ok"
    home = client.get("/")
    assert home.status_code == 200
    assert "画之灵助手" in home.text
    assert "Content-Security-Policy" in home.headers
    assert client.get("/openapi.json").json()["paths"]["/api/v1/recommend"]["post"]
    for url in ("/api/v1/meta", "/api/v1/catalog", "/api/v1/heroes", "/api/v1/items", "/api/v1/augments", "/api/v1/portals", "/api/v1/traits", "/api/v1/lineups", "/static/app.js", "/sw.js", "/static/manifest.webmanifest"):
        assert client.get(url).status_code == 200


def test_hero_search_star_variants_and_official_builds(client):
    heroes = client.get("/api/v1/heroes", params={"q": "巴德"}).json()
    assert len(heroes) == 1
    hero = client.get(f"/api/v1/heroes/{heroes[0]['id']}").json()
    assert [s["star"] for s in hero["stars"]] == [1, 2, 3]
    assert hero["recommended_builds"]
    assert client.get("/api/v1/heroes/not-a-hero").status_code == 404
    # The upstream uses | to separate multiple origins and classes.
    neeko = client.get('/api/v1/heroes/12303').json()
    assert {t['name'] for t in neeko['traits']} == {'山海绘卷', '天将', '法师'}
    kogmaw = client.get('/api/v1/heroes/11217').json()
    assert len(kogmaw['traits']) == 3
    assert client.get('/api/v1/heroes/15177').json()['recommended_builds']


def test_shop_unit_matches_its_alternate_form():
    data = get_catalog()
    result = rank_lineups(RecommendRequest(hero_counts={"15177": 3}, limit=12), data)
    assert result["results"][0]["matched_hero_ids"] == ["15177"]


def test_retired_guide_dependency_is_explained_and_penalized():
    data = get_catalog()
    lineup = next(l for l in data["lineups"] if l["name"] == "启程天使")
    assert "冒险启程" in lineup["unavailable_requirements"]
    specialized = next(l for l in data["lineups"] if "专属慎" in l["name"])
    assert "2922" in specialized["required_augment_ids"]


def test_copies_and_augment_raise_matching_composition():
    data = get_catalog()
    bard = next(h for h in data["heroes"] if h["name"] == "巴德")
    candidates = [l for l in data["lineups"] if bard["id"] in l["carry_ids"]]
    assert candidates
    l = candidates[0]
    baseline = rank_lineups(RecommendRequest(limit=12), data)
    improved = rank_lineups(RecommendRequest(hero_counts={bard["id"]: 6}, augment_ids=l["augment_ids"][:1], limit=12), data)
    match = next(r for r in improved["results"] if r["lineup"]["id"] == l["id"])
    assert match["score"] > max(r["score"] for r in baseline["results"])
    assert any(b["factor"] == "来牌" and b["points"] > 0 for b in match["breakdown"])


def test_inventory_cannot_be_reused_for_multiple_items():
    # Two identical recipes require two copies of each component.
    items = {"a": {"name": "弓"}, "b": {"name": "棒"}, "blade": {"name": "羊刀", "components": ["a", "b"]}}
    heroes = {"h": {"name": "巴德"}}
    lineup = {"units": [{"hero_id": "h", "item_ids": ["blade", "blade"], "carry": True}]}
    request = RecommendRequest(component_ids=["a", "b"])
    plans, coverage = equipment_plan(lineup, request, items, heroes)
    assert [p["status"] for p in plans] == ["craftable", "missing"]
    assert coverage == .5
    assert Counter(c for p in plans for c in p["allocated"]) == Counter(request.component_ids)


def test_same_component_recipe_requires_two_copies():
    items = {"a": {"name": "弓"}, "double": {"name": "双弓", "components": ["a", "a"]}}
    lineup = {"units": [{"hero_id": "h", "item_ids": ["double"], "carry": True}]}
    plans, _ = equipment_plan(lineup, RecommendRequest(component_ids=["a"]), items, {"h": {"name": "英雄"}})
    assert plans[0]["status"] == "missing"
    assert plans[0]["missing"] == [{"id": "a", "name": "弓", "count": 1}]


@pytest.mark.parametrize("payload", [
    {"portal_id": "bad"}, {"augment_ids": ["bad"]}, {"hero_counts": {"11205": 10}},
    {"hero_counts": {"11205": 0}}, {"component_ids": ["2004"]}, {"owned_item_ids": ["1001"]},
    {"level": 0}, {"hp": 116}, {"limit": 100}, {"unexpected": "field"},
    {"augment_ids": ["1004", "1004"]}, {"component_ids": ["1001"] * 41},
])
def test_invalid_recommendations_return_422(client, payload):
    assert client.post("/api/v1/recommend", json=payload).status_code == 422


def test_portal_rules_impact_reroll_and_explain_actual_effect():
    data = get_catalog()
    response = rank_lineups(RecommendRequest(portal_id="449", limit=12), data)
    assert response["results"][0]["lineup"]["style"] == "reroll"
    assert any(b["factor"] == "城邦／奇遇" and b["points"] > 0 for b in response["results"][0]["breakdown"])
    shop = rank_lineups(RecommendRequest(portal_id="471"), data)
    assert "不代表低等级" in "".join(shop["results"][0]["warnings"])


def test_contested_carry_reduces_score():
    data = get_catalog()
    l = next(l for l in data["lineups"] if l["style"] == "reroll" and not l["emblem_ids"] and not l["required_augment_ids"])
    carry_id = l["carry_ids"][0]
    clear = rank_lineups(RecommendRequest(hero_counts={carry_id: 9}, limit=12), data)
    contested = rank_lineups(RecommendRequest(hero_counts={carry_id: 9}, contested_hero_ids=[carry_id], limit=12), data)
    first = next(r for r in clear["results"] if r["lineup"]["id"] == l["id"])
    second = next((r for r in contested["results"] if r["lineup"]["id"] == l["id"]), None)
    # A sufficient penalty can move this composition out of the returned top 12.
    assert second is None or second["score"] < first["score"]


def test_specialized_composition_requires_its_augment():
    data = get_catalog()
    specialized = [l for l in data["lineups"] if l["required_augment_ids"]]
    assert specialized
    lineup = specialized[0]
    augmented = rank_lineups(RecommendRequest(augment_ids=[lineup["required_augment_ids"][0]], limit=12), data)
    matched = next(r for r in augmented["results"] if r["lineup"]["id"] == lineup["id"])
    assert not any("专属强化条件" in c for c in matched["conditions"])


def test_api_accepts_real_request_and_returns_explainable_score(client):
    result = client.post("/api/v1/recommend", json={"portal_id": "449", "hero_counts": {"13213": 6}, "component_ids": ["1002", "1003", "1002"], "hp": 42, "gold": 35}).json()
    assert result["algorithm"] == "rules-v1"
    assert len(result["results"]) == 6
    assert all(0 <= row["score"] <= 100 for row in result["results"])
    assert all(row["breakdown"] and row["equipment_plan"] for row in result["results"])
