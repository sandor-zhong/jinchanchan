"""Accept only explicitly sourced, matching-season placement samples."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictInt, model_validator

from app.catalog import ROOT, get_catalog


class LineupSample(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lineup_id: str
    placement_counts: list[StrictInt] = Field(min_length=8, max_length=8)

    @model_validator(mode='after')
    def valid_counts(self):
        if any(n < 0 for n in self.placement_counts) or sum(self.placement_counts) < 1:
            raise ValueError('Need non-negative placement counts and at least one sample')
        return self


class StatisticsSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    season: Literal['S100030']
    data_version: str
    source_name: str = Field(min_length=2, max_length=100)
    source_url: HttpUrl
    region: Literal['CN']
    rank_scope: str = Field(min_length=1, max_length=100)
    lineup_definition: str = Field(min_length=10, max_length=1000)
    period_start: datetime
    period_end: datetime
    samples: list[LineupSample] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def valid_period(self):
        if self.period_start.tzinfo is None or self.period_end.tzinfo is None:
            raise ValueError('Statistics times must have an explicit timezone')
        if self.period_start >= self.period_end or self.period_end > datetime.now(timezone.utc):
            raise ValueError('Invalid statistics period')
        if len({s.lineup_id for s in self.samples}) != len(self.samples):
            raise ValueError('Duplicate lineup IDs')
        return self


@lru_cache(maxsize=1)
def load_statistics() -> StatisticsSnapshot | None:
    path = Path(os.getenv('STATISTICS_PATH', str(ROOT / 'data' / 'statistics.json')))
    if not path.exists():
        return None
    return StatisticsSnapshot.model_validate_json(path.read_text(encoding='utf-8'))


def rankings(metric: str = 'top4_rate', min_samples: int = 30) -> dict:
    data = get_catalog()
    snapshot = load_statistics()
    definitions = [
        {'name': '前四率', 'meaning': '结算名次为1–4名的玩家记录占比，更接近“稳定进入前四”的目标。'},
        {'name': '登顶率', 'meaning': '结算第一名的玩家记录占比；不等于每个战斗回合的胜率。'},
        {'name': '平均名次', 'meaning': '结算名次的平均值，越低越好；应和样本量、分段与版本一起看。'},
        {'name': '样本量', 'meaning': '该构筑的玩家结算记录数量；不是整个游戏的总对局数，也不代表所有玩家。'},
    ]
    base = {'version': data['meta']['version'], 'season': 'S100030', 'definitions': definitions, 'metric': metric,
            'note': '同赛季、同资料版本、同分段与统计区间的数据才有可比性。匹配分、官网收录分级和主观T级均不等于胜率。'}
    if snapshot is None:
        return {**base, 'status': 'unavailable', 'rows': [], 'message': '尚未接入可验证的2026画之灵对局样本，因此不填入胜率或编造排行榜。',
                'source_checks': [{'name': '金铲铲官网公开阵容库', 'result': '已收录攻略，未提供可用的结算样本统计。', 'url': next(s['url'] for s in data['sources'] if s['id'] == 'tencent-lineups')},
                                  {'name': '已检查的第三方统计页面', 'result': '公开页面展示自然之力赛季，未混用到画之灵。', 'url': 'https://www.dataj.cc/comp'}]}
    if snapshot.data_version != data['meta']['version']:
        return {**base, 'status': 'version_mismatch', 'rows': [], 'message': '统计数据与当前资料版本不一致，已停止展示排行榜。'}
    valid_ids = {l['id'] for l in data['lineups']}
    if any(s.lineup_id not in valid_ids for s in snapshot.samples):
        return {**base, 'status': 'invalid_mapping', 'rows': [], 'message': '统计构筑与当前阵容库尚未完成映射。'}
    rows = []
    for sample in snapshot.samples:
        n = sum(sample.placement_counts)
        if n < min_samples:
            continue
        rows.append({'lineup_id': sample.lineup_id, 'sample_count': n, 'top4_rate': sum(sample.placement_counts[:4]) / n,
                     'first_rate': sample.placement_counts[0] / n, 'average_placement': sum((i+1)*c for i,c in enumerate(sample.placement_counts)) / n})
    rows.sort(key=lambda r: r[metric], reverse=metric != 'average_placement')
    return {**base, 'status': 'stale' if (datetime.now(timezone.utc) - snapshot.period_end).days > 7 else 'available',
            'rows': rows, 'source': snapshot.model_dump(mode='json', exclude={'samples'}), 'message': '以下为已注明来源的样本统计，不能保证个人选择该阵容后的结果。'}
