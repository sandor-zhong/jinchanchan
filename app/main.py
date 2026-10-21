from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.catalog import ROOT, canonical_hero_ids, get_catalog, index
from app.recommend import RecommendRequest, rank_lineups
from app.reference import get_reference
from app.statistics import rankings
from app.ai import router as ai_router
from dotenv import load_dotenv

load_dotenv(ROOT / '.env', override=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_catalog()  # Fail early when a deployment snapshot is missing or invalid.
    yield


app = FastAPI(title="画之灵助手 API", version="2.0.0", lifespan=lifespan,
              description="基于官网资料的阵容学习手册、棋子属性与出装、强化符文双向查询及可选条件匹配。")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(ai_router)
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-AI-Access-Token"])


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path in ("/", "/sw.js") or request.url.path.startswith(("/static/", "/api/v1/")):
        response.headers["Cache-Control"] = "no-cache"
    if request.url.path == "/":
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' https://game.gtimg.cn data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response


@app.get("/healthz", tags=["运维"])
def health():
    return {"status": "ok", "version": get_catalog()["meta"]["version"]}


@app.get("/api/v1/meta", tags=["资料"])
def meta():
    data = get_catalog()
    synced = datetime.fromisoformat(data["meta"]["synced_at"])
    age_days = max(0, (datetime.now(timezone.utc) - synced).days)
    return {**data["meta"], "snapshot_age_days": age_days, "stale": age_days > 7,
            "counts": {k: len(data[k]) for k in ("heroes", "items", "augments", "traits", "portals", "lineups")},
            "sources": data["sources"]}


@app.get("/api/v1/catalog", tags=["资料"])
def catalog():
    return get_catalog()


@app.get('/api/v1/guidebook', tags=['学习手册'])
def guidebook():
    return get_reference()


@app.get('/api/v1/lineups/{lineup_id}/guide', tags=['学习手册'])
def lineup_guide(lineup_id: str):
    find('lineups', lineup_id)
    return get_reference()['lineups'][lineup_id]


@app.get('/api/v1/augments/{augment_id}', tags=['学习手册'])
def augment_detail(augment_id: str):
    return {**find('augments', augment_id), 'study': get_reference()['augments'][augment_id]}


@app.get('/api/v1/rankings', tags=['数据统计'])
def statistical_rankings(metric: str = Query('top4_rate', pattern='^(top4_rate|first_rate|average_placement)$'), min_samples: int = Query(30, ge=1, le=100000)):
    return rankings(metric, min_samples)


def find(key: str, entry_id: str):
    entry = next((x for x in get_catalog()[key] if x["id"] == entry_id), None)
    if entry is None:
        raise HTTPException(404, "没有找到这条资料")
    return entry


@app.get("/api/v1/heroes", tags=["英雄"])
def heroes(q: str = Query("", max_length=50), cost: int | None = Query(None, ge=0, le=5), trait_id: str | None = None):
    return [h for h in get_catalog()["heroes"] if (q in h["name"] or any(q in t["name"] for t in h["traits"]))
            and (cost is None or h["cost"] == cost) and (trait_id is None or any(t["id"] == trait_id for t in h["traits"]))]


@app.get("/api/v1/heroes/{hero_id}", tags=["英雄"])
def hero_detail(hero_id: str):
    hero = find("heroes", hero_id)
    data = get_catalog()
    canonical = canonical_hero_ids(data)
    hero_index = index(data["heroes"])
    builds, seen = [], set()
    for lineup in get_catalog()["lineups"]:
        for unit in lineup["units"]:
            signature = tuple(sorted(unit["item_ids"]))
            if canonical[unit["hero_id"]] == canonical[hero_id] and signature and signature not in seen:
                seen.add(signature)
                builds.append({"item_ids": unit["item_ids"], "lineup_id": lineup["id"], "lineup_name": lineup["name"],
                               "source_url": lineup["source_url"], "carry": unit["carry"],
                               "form_name": hero_index[unit["hero_id"]]["name"]})
    return {**hero, "recommended_builds": sorted(builds, key=lambda b: not b["carry"]), 'study': get_reference()['heroes'][hero_id]}


@app.get("/api/v1/items", tags=["装备"])
def items(q: str = Query("", max_length=50), type: str | None = None):
    return [x for x in get_catalog()["items"] if q in x["name"] and (type is None or type == x["type"])]


@app.get("/api/v1/items/{item_id}", tags=["装备"])
def item_detail(item_id: str):
    item = find("items", item_id)
    hero_ids = list(dict.fromkeys(u["hero_id"] for l in get_catalog()["lineups"] for u in l["units"] if item_id in u["item_ids"]))
    return {**item, "recommended_hero_ids": hero_ids, "recommendation_basis": "官网阵容中使用此装备的英雄"}


@app.get("/api/v1/augments", tags=["资料"])
def augments(q: str = Query("", max_length=50), tier: int | None = Query(None, ge=1, le=3)):
    return [x for x in get_catalog()["augments"] if q in x["name"] and (tier is None or x["tier"] == tier)]


@app.get("/api/v1/portals", tags=["资料"])
def portals():
    return get_catalog()["portals"]


@app.get("/api/v1/traits", tags=["资料"])
def traits():
    return get_catalog()["traits"]


@app.get("/api/v1/lineups", tags=["阵容"])
def lineups(q: str = Query("", max_length=50), style: str | None = None):
    return [x for x in get_catalog()["lineups"] if q in x["full_name"] and (style is None or x["style"] == style)]


@app.get("/api/v1/lineups/{lineup_id}", tags=["阵容"])
def lineup_detail(lineup_id: str):
    return find("lineups", lineup_id)


@app.post("/api/v1/recommend", tags=["阵容"])
def recommend(request: RecommendRequest):
    try:
        return rank_lineups(request, get_catalog())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(ROOT / "app" / "static" / "sw.js", media_type="application/javascript")


app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
