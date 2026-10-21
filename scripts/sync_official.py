"""Fetch the public JSON used by jcc.qq.com. Never evaluate remote JavaScript.

Run: python -m scripts.sync_official --dry-run
     python -m scripts.sync_official
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.catalog import ROOT, validate_catalog

BASE = "https://game.gtimg.cn/images/lol/act/jkzlk/js"
VERSION_URL = BASE + "/config/versiondataconfig.js"
LINEUP_URL = "https://game.gtimg.cn/images/lol/act/jkzlkauto/json/lineupJson/m100030/11/11/lineup_detail_total.json"
KEYS = ("hero", "equip", "hex", "trait", "galaxy")


def clean(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def ids(value: str, *, unique: bool = True) -> list[str]:
    parts = [x.strip() for x in re.split(r"[,|]", str(value or "")) if x.strip()]
    return list(dict.fromkeys(parts)) if unique else parts


def fetch(url: str) -> tuple[dict | list, str]:
    if urlparse(url).hostname != "game.gtimg.cn" or not url.startswith("https://"):
        raise ValueError("Only the official Tencent data host is allowed")
    error = None
    for _ in range(3):
        try:
            request = Request(url, headers={"User-Agent": "HualingAssistant/1.0", "Accept": "application/json"})
            with urlopen(request, timeout=25) as response:
                raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise ValueError("Official response exceeds size limit")
            return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()
        except (OSError, ValueError) as exc:
            error = exc
    raise RuntimeError(f"Failed to fetch {url}: {error}")


def normalize(raw: dict, version: dict, sources: list[dict]) -> dict:
    traits_by_id = {}
    for entry in raw["trait"]["data"].values():
        if not all(str(entry.get(k, "")).isdigit() for k in ("checkId", "num", "color")):
            continue
        trait_id = str(entry["checkId"])
        trait = traits_by_id.setdefault(trait_id, {
            "id": trait_id, "name": entry["name"], "kind": "origin" if entry["type"] == 0 else "class",
            "icon": entry["picture"], "description": clean(entry["prefix"]), "levels": [], "source_id": "tencent-trait",
        })
        trait["levels"].append({"count": int(entry["num"]), "effect": clean(entry["realDesc"]), "color": int(entry["color"])})
    for trait in traits_by_id.values():
        trait["levels"].sort(key=lambda x: x["count"])

    hero_raw = raw["hero"]["data"]
    referenced_hero_ids = set()
    for lineup in raw["lineups"]["lineup_list"]:
        detail = json.loads(lineup["detail"]) if isinstance(lineup["detail"], str) else lineup["detail"]
        referenced_hero_ids.update(u["hero_id"] for u in detail["hero_location"])
    heroes = []
    # IDs beginning with 2/3 contain star variants, not additional champions.
    for hero in hero_raw.values():
        if not hero["id"].startswith("1") or (hero["showHeroTag"] != "1" and hero["id"] not in referenced_hero_ids):
            continue
        trait_ids = [x for x in ids(hero["species"]) + ids(hero["class"]) if x in traits_by_id]
        stars = []
        for star in (1, 2, 3):
            variant = hero_raw.get(str(star) + hero["id"][1:])
            if variant:
                stars.append({"star": star, "hp": float(variant["initHP"]), "attack": float(variant["initAttackDamage"]),
                              "skill": clean(variant["skillDesc"])})
        heroes.append({
            "id": hero["id"], "name": hero["name"], "cost": int(hero["price"]), "icon": hero["picture"],
            "summon": hero["heroType"] != "0" or hero["name"] == "提伯斯",
            "form": hero["showHeroTag"] != "1" and hero["heroType"] == "0",
            "traits": [{"id": x, "name": traits_by_id[x]["name"]} for x in trait_ids],
            "stats": {"hp": float(hero["initHP"]), "attack": float(hero["initAttackDamage"]),
                      "armor": float(hero["armor"]), "magic_resist": float(hero["magicResist"]),
                      "attack_speed": float(hero["attackSpeed"]), "range": int(hero["attackRange"]),
                      "mana": f"{hero['initMP']}/{hero['maxMP']}"},
            "skill_name": clean(hero["skillName"]), "skill_description": clean(hero["skillDesc"]),
            "skill_values": clean(hero["skillValueDesc"]).split("|"), "stars": stars, "source_id": "tencent-hero",
        })
    hero_index = {x["id"]: x for x in heroes}
    items = [{"id": x["id"], "name": x["name"], "type": x["type"], "icon": x["picture"],
              "description": clean(x["desc"]), "stats": clean(x["basicDesc"]),
              "components": [str(x[k]) for k in ("synthesis1", "synthesis2") if str(x[k]) not in ("0", "", "-1")],
              "trait_id": str(x.get("fetterID", "")), "source_id": "tencent-equip"}
             for x in raw["equip"]["data"].values()]
    item_index = {x["id"]: x for x in items}
    augments = [{"id": x["id"], "name": x["name"], "tier": int(x["level"]), "icon": x["icon"],
                 "description": clean(x["desc"]), "source_id": "tencent-hex"}
                for x in raw["hex"]["data"].values()]
    augment_index = {x["id"]: x for x in augments}
    portals = [{"id": x["id"], "name": x["name"], "description": clean(x["desc"]),
                "icon": x["logo"], "source_id": "tencent-galaxy"} for x in raw["galaxy"]["data"].values()]
    lineups = []
    for row in raw["lineups"]["lineup_list"]:
        detail = json.loads(row["detail"]) if isinstance(row["detail"], str) else row["detail"]
        units = []
        for unit in detail["hero_location"]:
            pos = unit["location"].split(",")
            units.append({"hero_id": unit["hero_id"], "item_ids": ids(unit["equipment_id"], unique=False),
                          "carry": bool(unit["is_carry_hero"]), "row": int(pos[0]), "col": int(pos[1])})
        name_match = re.search(r"【(.*?)】", detail["line_name"])
        name = name_match.group(1) if name_match else detail["line_name"]
        core = [x for x in units if x["carry"]] or [x for x in units if len(x["item_ids"]) >= 2][:1]
        carry_cost = min((hero_index[x["hero_id"]]["cost"] for x in core), default=4)
        style = "reroll" if carry_cost <= 3 else "level"
        gate_augments = [a["id"] for a in augments if a["name"] in name and len(a["name"]) >= 3]
        unavailable_requirements = []
        # Official guides explicitly name mandatory hero augments in these titles.
        for keyword in ("冒险启程", "急落怒放", "飘渺之刃"):
            if keyword in name or (keyword == "冒险启程" and "启程天使" in name):
                official_keyword = "缥缈之刃" if keyword == "飘渺之刃" else keyword
                matches = [a["id"] for a in augments if official_keyword in a["name"]]
                gate_augments += matches
                if not matches:
                    unavailable_requirements.append(keyword)
        emblem_ids = list(dict.fromkeys(i for u in units for i in u["item_ids"] if item_index[i]["type"] == "转职纹章"))
        lineups.append({
            "id": row["id"], "name": name, "full_name": detail["line_name"], "style": style,
            "target_level": sum(not hero_index[u["hero_id"]]["summon"] for u in units),
            "carry_ids": [x["hero_id"] for x in core], "units": units,
            "traits": sorted([{"id": str(t["id"]), "name": traits_by_id[str(t["id"])]["name"], "count": int(t["num"])}
                              for t in detail.get("contact", []) if str(t["id"]) in traits_by_id], key=lambda t: -t["count"]),
            "augment_ids": [x for x in ids(detail.get("hexbuff", {}).get("recomm", "")) if x in augment_index],
            "alternate_augment_ids": [x for x in ids(detail.get("hexbuff", {}).get("replace", "")) if x in augment_index],
            "required_augment_ids": list(dict.fromkeys(gate_augments)), "emblem_ids": emblem_ids,
            "unavailable_requirements": unavailable_requirements,
            "guides": {key: clean(detail.get(field, "")) for key, field in {
                "early": "early_info", "rolling": "d_time", "equipment": "equipment_info", "positioning": "location_info",
                "augments": "hex_info", "matchups": "enemy_info"}.items()},
            "priority_component_ids": ids(detail.get("equipment_order", ""), unique=False),
            "three_star_ids": ids(detail.get("level_3_heros", "")),
            "author": row.get("lineupauthor_data", {}).get("name", "官网阵容资料"),
            "published_at": row.get("rel_time", ""), "original_created_at": row.get("sub_time", ""),
            "source_id": "tencent-lineups", "source_url": f"https://jcc.qq.com/#/lineupDetail/11,S100030,,Mode11_S100030/{row['id']}/1",
        })
    return {
        "meta": {"name": "画之灵 · 2026 返场", "season": "S100030", "mode": "11", "version": version["version"],
                 "version_started_at": version["version_start_time"], "synced_at": datetime.now(timezone.utc).isoformat(),
                 "data_updated_at": max(raw[k]["time"] for k in KEYS),
                 "recommendation_note": "匹配分为本助手的条件匹配结果，不代表官方强度排行或胜率。官网阵容含历史攻略返场重发，请结合当前对局判断。",
                 "mechanics": [{"name": "绘境", "description": "2-5、3-5、4-5 各选择一次绘境格，可放置于棋盘。分为战力、经济、陷阱等类型。",
                                "source_url": "https://www.taptap.cn/moment/851886704909353222"},
                               {"name": "狂风奇遇", "description": "返场版加入改变对局规则的奇遇。选择开局城邦或奇遇条件，让助手调整运营倾向。",
                                "source_url": "https://www.taptap.cn/moment/852521787559247892"}],
                 "coverage_note": "官网公开数据未提供完整绘境格与所有中途奇遇列表；当前不对未收录效果作精确计算。资料版本号来自官网数据配置，不等同于客户端公告版本号。"},
        "sources": sources, "heroes": sorted(heroes, key=lambda h: (h["cost"], h["id"])),
        "items": items, "augments": augments, "traits": list(traits_by_id.values()), "portals": portals, "lineups": lineups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Download and validate without replacing the catalog")
    parser.add_argument("--from-cache", type=Path, help="Use a previously downloaded research directory (development only)")
    args = parser.parse_args()
    if args.from_cache:
        versions = json.loads((args.from_cache / "version.js").read_text(encoding="utf-8"))
    else:
        versions, _ = fetch(VERSION_URL)
    version = next(v for v in versions if v["mode"] == "11" and v["season"] == "S100030" and v["is_newest_version"] == 1)
    urls = {k: BASE + "/" + version[k + "url"].lstrip("/") for k in KEYS}
    urls["lineups"] = LINEUP_URL
    if args.from_cache:
        fetched = {}
        for key in urls:
            content = (args.from_cache / f"{key}.json").read_bytes()
            fetched[key] = json.loads(content), hashlib.sha256(content).hexdigest()
    else:
        with ThreadPoolExecutor(max_workers=6) as pool:
            fetched = dict(zip(urls, pool.map(fetch, urls.values())))
    for key in KEYS:
        payload = fetched[key][0]
        if (payload.get("version"), payload.get("season"), str(payload.get("setId"))) != (version["version"], "S100030", "11"):
            raise ValueError(f"{key}: official data version/season mismatch; keeping the existing snapshot")
    if any(str(row.get("mode")) != "11" or str(row.get("season")) != "100030" for row in fetched["lineups"][0]["lineup_list"]):
        raise ValueError("Lineup season mismatch; keeping the existing snapshot")
    labels = {"hero": "英雄与技能", "equip": "装备与合成", "hex": "强化符文", "trait": "羁绊", "galaxy": "城邦与开局奇遇", "lineups": "官网阵容库"}
    sources = [{"id": "tencent-" + k, "title": "金铲铲官网 · " + labels[k], "url": urls[k],
                "publisher": "腾讯游戏 / 金铲铲之战", "sha256": fetched[k][1],
                "updated_at": fetched[k][0].get("time", ""), "kind": "official_public_data"} for k in urls]
    sources.append({"id": "tencent-version", "title": "官网资料版本配置", "url": VERSION_URL,
                    "publisher": "腾讯游戏 / 金铲铲之战", "kind": "official_public_data"})
    result = normalize({k: v[0] for k, v in fetched.items()}, version, sources)
    validate_catalog(result)
    print(json.dumps({"version": version["version"], "counts": {k: len(result[k]) for k in ("heroes", "items", "augments", "traits", "portals", "lineups")}, "dry_run": args.dry_run}, ensure_ascii=False))
    if not args.dry_run:
        destination = ROOT / "data" / "catalog.json"
        destination.parent.mkdir(exist_ok=True)
        # A failed download/validation leaves the last working snapshot intact.
        fd, temp_name = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
            os.replace(temp_name, destination)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


if __name__ == "__main__":
    main()
