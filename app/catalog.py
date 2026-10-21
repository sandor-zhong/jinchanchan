from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_catalog(data: dict) -> None:
    """Reject broken snapshots before they can replace the working catalog."""
    for key in ("heroes", "items", "augments", "traits", "portals", "lineups"):
        rows = data[key]
        ids = [row["id"] for row in rows]
        if not rows or len(ids) != len(set(ids)):
            raise ValueError(f"{key}: empty data or duplicate IDs")
    if data["meta"]["season"] != "S100030" or data["meta"]["mode"] != "11":
        raise ValueError("Refusing a catalog from a different season")
    hero_ids = {x["id"] for x in data["heroes"]}
    item_ids = {x["id"] for x in data["items"]}
    augment_ids = {x["id"] for x in data["augments"]}
    for item in data["items"]:
        if not set(item["components"]) <= item_ids:
            raise ValueError(f"Unknown recipe component for item {item['id']}")
    for lineup in data["lineups"]:
        for unit in lineup["units"]:
            if unit["hero_id"] not in hero_ids:
                raise ValueError(f"Unknown hero in lineup {lineup['id']}")
            if not set(unit["item_ids"]) <= item_ids:
                raise ValueError(f"Unknown equipment in lineup {lineup['id']}")
            if not (1 <= unit["row"] <= 4 and 1 <= unit["col"] <= 7):
                raise ValueError("Invalid board position")
        if not set(lineup["augment_ids"] + lineup["alternate_augment_ids"]) <= augment_ids:
            raise ValueError(f"Unknown augment in lineup {lineup['id']}")


@lru_cache(maxsize=1)
def get_catalog() -> dict:
    path = Path(os.getenv("CATALOG_PATH", str(ROOT / "data" / "catalog.json")))
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_catalog(data)
    return data


def index(rows: list[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in rows}


def canonical_hero_ids(data: dict) -> dict[str, str]:
    """Shop units and their separate guide/skill forms share a single inventory."""
    canonical = {h["id"]: h["id"] for h in data["heroes"]}
    base_names = {(h["name"], h["cost"]): h["id"] for h in data["heroes"] if not h["form"]}
    for hero in data["heroes"]:
        if hero["form"]:
            canonical[hero["id"]] = base_names.get((hero["name"], hero["cost"]), hero["id"])
        if hero["name"] in ("霞", "洛"):
            canonical[hero["id"]] = "15177"
    return canonical
