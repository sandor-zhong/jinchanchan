"""Import a matching-season, sourced placement-count JSON supplied by the operator."""
import argparse
import json
import os
import tempfile
from pathlib import Path

from app.catalog import ROOT, get_catalog
from app.statistics import StatisticsSnapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    snapshot = StatisticsSnapshot.model_validate_json(args.path.read_text(encoding='utf-8'))
    data = get_catalog()
    if snapshot.data_version != data['meta']['version']:
        raise ValueError('Statistics must match the current data version')
    if not {s.lineup_id for s in snapshot.samples} <= {l['id'] for l in data['lineups']}:
        raise ValueError('Statistics contain unknown lineup IDs')
    target = ROOT / 'data' / 'statistics.json'
    fd, temporary = tempfile.mkstemp(dir=target.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(snapshot.model_dump_json(indent=2))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(json.dumps({'imported_lineups': len(snapshot.samples), 'source': snapshot.source_name}, ensure_ascii=False))


if __name__ == '__main__':
    main()
