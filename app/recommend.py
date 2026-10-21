from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.catalog import canonical_hero_ids, index


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    portal_id: str | None = None
    augment_ids: list[str] = Field(default_factory=list, max_length=3)
    hero_counts: dict[str, int] = Field(default_factory=dict, max_length=25)
    component_ids: list[str] = Field(default_factory=list, max_length=40)
    owned_item_ids: list[str] = Field(default_factory=list, max_length=20)
    contested_hero_ids: list[str] = Field(default_factory=list, max_length=20)
    level: int = Field(default=7, ge=3, le=10)
    hp: int = Field(default=80, ge=1, le=115)
    gold: int = Field(default=50, ge=0, le=999)
    preferred_style: Literal["auto", "reroll", "level"] = "auto"
    limit: int = Field(default=6, ge=1, le=12)

    @field_validator("hero_counts")
    @classmethod
    def valid_copies(cls, value: dict[str, int]) -> dict[str, int]:
        if any(n < 1 or n > 9 for n in value.values()):
            raise ValueError("每位英雄的张数必须为 1–9（两星请填写 3 张）")
        return value

    @field_validator("augment_ids", "contested_hero_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("不能重复选择同一项")
        return value


def validate_ids(request: RecommendRequest, data: dict) -> None:
    valid = {key: {x["id"] for x in data[key]} for key in ("heroes", "items", "augments", "portals")}
    selections = {"heroes": set(request.hero_counts) | set(request.contested_hero_ids),
                  "items": set(request.component_ids + request.owned_item_ids), "augments": set(request.augment_ids),
                  "portals": {request.portal_id} if request.portal_id else set()}
    for key, values in selections.items():
        unknown = values - valid[key]
        if unknown:
            raise ValueError(f"未知的 {key} ID：{', '.join(sorted(unknown))}")
    items = index(data["items"])
    if any(items[i]["type"] != "基础装备" for i in request.component_ids):
        raise ValueError("component_ids 只能包含基础装备；成装请使用 owned_item_ids")
    if any(items[i]["type"] == "基础装备" for i in request.owned_item_ids):
        raise ValueError("owned_item_ids 只能包含成装；散件请使用 component_ids")
    heroes = index(data["heroes"])
    if any(heroes[h]["summon"] for h in request.hero_counts):
        raise ValueError("召唤物不能作为商店来牌输入")


def equipment_plan(lineup: dict, request: RecommendRequest, items: dict, heroes: dict) -> tuple[list[dict], float]:
    """Allocate a finite inventory once across the core units, including duplicates."""
    units = sorted((u for u in lineup["units"] if u["item_ids"]), key=lambda u: (not u["carry"], -len(u["item_ids"])))[:3]
    components, owned = Counter(request.component_ids), Counter(request.owned_item_ids)
    plans = []
    for unit in units:
        for item_id in unit["item_ids"]:
            item = items[item_id]
            plans.append({"hero_id": unit["hero_id"], "hero_name": heroes[unit["hero_id"]]["name"],
                          "item_id": item_id, "item_name": item["name"], "status": "missing", "missing": [], "allocated": [],
                          "_recipe": Counter(item["components"])})
    # Complete all possible recipes before spending remaining pieces on partial recipes.
    for plan in plans:
        recipe = plan["_recipe"]
        if owned[plan["item_id"]] > 0:
            owned[plan["item_id"]] -= 1
            plan["status"] = "owned"
        elif recipe and not (recipe - components):
            components.subtract(recipe)
            plan["allocated"] = list(recipe.elements())
            plan["status"] = "craftable"
    matched = 0
    total = 0
    for plan in plans:
        recipe = plan.pop("_recipe")
        weight = max(2, sum(recipe.values()))
        total += weight
        if plan["status"] in ("owned", "craftable"):
            matched += weight
            continue
        if not recipe:
            plan["missing"] = [{"id": plan["item_id"], "name": plan["item_name"], "count": 1}]
        else:
            allocated = recipe & +components
            components.subtract(allocated)
            plan["allocated"] = list(allocated.elements())
            matched += sum(allocated.values())
            plan["missing"] = [{"id": k, "name": items[k]["name"], "count": n} for k, n in (recipe - allocated).items()]
    return plans, matched / total if total else 0


def rank_lineups(request: RecommendRequest, data: dict) -> dict:
    validate_ids(request, data)
    heroes, items, augments, portals = (index(data[k]) for k in ("heroes", "items", "augments", "portals"))
    # The shop sells one Xayah & Rakan unit; guides reference its separate forms.
    canonical = canonical_hero_ids(data)
    copies = Counter()
    for hero_id, count in request.hero_counts.items():
        copies[canonical[hero_id]] = min(9, copies[canonical[hero_id]] + count)
    contested_ids = {canonical[h] for h in request.contested_hero_ids}
    results = []
    for lineup in data["lineups"]:
        breakdown = [{"factor": "基础", "points": 40, "reason": "来自官网阵容库的候选阵容"}]
        warnings = []
        gates = []

        def add(factor: str, points: float, reason: str) -> None:
            breakdown.append({"factor": factor, "points": round(points, 1), "reason": reason})

        unit_ids = {u["hero_id"] for u in lineup["units"]}
        matched = {h for h in request.hero_counts if canonical[h] in {canonical[u] for u in unit_ids}}
        canonical_carries = {canonical[h] for h in lineup["carry_ids"]}
        if matched:
            matched_canonical = {canonical[h] for h in matched}
            points = min(20, sum(2 + min(copies[h], 6) * (1.3 if h in canonical_carries else .45) for h in matched_canonical))
            add("来牌", points, "已有 " + "、".join(heroes[h]["name"] + f"×{request.hero_counts[h]}" for h in sorted(matched)))
        elif request.hero_counts:
            add("来牌", -3, "当前来牌与这套阵容重合较少")

        plans, coverage = equipment_plan(lineup, request, items, heroes)
        if request.component_ids or request.owned_item_ids:
            ready = sum(p["status"] in ("owned", "craftable") for p in plans)
            add("装备", coverage * 24, f"核心出装可直接装备或合成 {ready} 件；按有限库存分配")

        for augment_id in request.augment_ids:
            augment = augments[augment_id]
            if augment_id in lineup["augment_ids"]:
                add("海克斯", 9, f"{augment['name']} 是这套官网攻略的优选符文")
            elif augment_id in lineup["alternate_augment_ids"]:
                add("海克斯", 5, f"{augment['name']} 是这套官网攻略的备选符文")
            elif any(t["name"] in augment["name"] for t in lineup["traits"]):
                add("海克斯", 4, f"{augment['name']} 与阵容羁绊同名，存在搭配空间")

        if lineup["required_augment_ids"] and not (set(lineup["required_augment_ids"]) & set(request.augment_ids)):
            names = " / ".join(augments[a]["name"] for a in lineup["required_augment_ids"])
            gates.append("专属强化条件：" + names)
            add("成型条件", -22, "尚未选择这套阵容所需的专属强化")
        for missing in lineup.get("unavailable_requirements", []):
            gates.append(f"原攻略依赖 {missing}，当前官网符文库未收录；此方案需重新核实")
            add("资料差异", -30, f"当前符文库未收录原攻略要求的 {missing}")
        remaining_components = Counter(request.component_ids)
        for plan in plans:
            remaining_components.subtract(plan["allocated"])
        for emblem_id in lineup["emblem_ids"]:
            emblem = items[emblem_id]
            supplied = emblem_id in request.owned_item_ids or any(emblem["name"] in augments[a]["description"] for a in request.augment_ids)
            if any(p["item_id"] == emblem_id and p["status"] == "craftable" for p in plans):
                supplied = True
            recipe = Counter(emblem["components"])
            if not supplied and recipe and not (recipe - remaining_components):
                supplied = True
                remaining_components.subtract(recipe)
            if not supplied:
                gates.append("参考站位使用 " + emblem["name"] + "；请确认能获取，或调整羁绊")
                add("转职", -7, emblem["name"] + " 尚未确认获取")

        if request.portal_id:
            portal = portals[request.portal_id]
            if request.portal_id in ("445", "449", "472", "478") and lineup["style"] == "reroll":
                add("城邦／奇遇", 8, portal["name"] + " 有利于刷新或低费追星")
            elif request.portal_id in ("471", "451", "444") and lineup["style"] == "level":
                add("城邦／奇遇", 5, portal["name"] + " 为高费阵容提供机会")
            elif request.portal_id == "475":
                add("城邦／奇遇", min(7, len(lineup["traits"])), "追梦羁绊心可提升已激活羁绊计数，需随局调整棋盘")
            else:
                add("城邦／奇遇", 0, portal["name"] + " 未设置阵容专属加分，按实际局势选择")
            if request.portal_id == "471":
                warnings.append("一元店改变购买价格，不代表低等级更容易刷到五费卡。")
            if request.portal_id == "474":
                warnings.append("限时消费取消常规额外收入，官网攻略中的存息与连胜经济节奏需要调整。")
            if request.portal_id == "477":
                warnings.append("背包扩容可带四件装备；这里仍展示官网三件核心出装，第四件按对手补充。")

        contested = {h for h in lineup["carry_ids"] if canonical[h] in contested_ids}
        if contested:
            add("同行", -14 if lineup["style"] == "reroll" else -7, "主 C 有同行：" + "、".join(heroes[h]["name"] for h in sorted(contested)))
            warnings.append("主 C 有同行，追三星前先观察其他玩家持牌。")
        if request.preferred_style != "auto" and request.preferred_style == lineup["style"]:
            add("打法", 5, "符合你的打法偏好")
        if request.hp <= 35 and lineup["target_level"] > request.level and request.gold < 30:
            add("容错", -12, "血量与经济偏低，直接转高人口阵容风险较大")
            warnings.append("优先提升眼前战力，避免为最终站位强行攒钱。")
        elif lineup["style"] == "reroll" and request.level >= 9 and all(heroes[h]["cost"] <= 2 for h in lineup["carry_ids"]):
            add("阶段", -8, "当前等级偏高，回头追低费主 C 成本较大")
        if lineup["original_created_at"].startswith("2024"):
            warnings.append("官网在返场时重新发布了历史攻略；具体运营与当前平衡可能存在差异。")
        score = max(0, min(100, round(sum(x["points"] for x in breakdown))))
        results.append({"lineup": lineup, "score": score, "breakdown": breakdown, "warnings": warnings,
                        "conditions": gates, "equipment_plan": plans,
                        "matched_hero_ids": sorted(matched)})
    results.sort(key=lambda r: -r["score"])
    general_notes = [data["meta"]["recommendation_note"]]
    if not (request.hero_counts or request.augment_ids or request.component_ids or request.owned_item_ids or request.portal_id):
        general_notes.append("尚未输入对局条件，当前按官网候选阵容及成型条件展示。补充来牌与装备后推荐更有参考价值。")
    return {"version": data["meta"]["version"], "algorithm": "rules-v1", "notes": general_notes,
            "total_candidates": len(results), "results": results[:request.limit]}
