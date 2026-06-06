#!/usr/bin/env python3
"""
Exact blueprint lookup helper for SCMDB crafting_blueprints.json.

Resolves blueprint records by stable identifiers instead of fuzzy matching.
Preferred keys:
  - guid: exact blueprint GUID
  - name: exact productName
  - tag: exact tag

Usage:
    python3 scripts/query/blueprint_lookup.py --name "Yeager"
    python3 scripts/query/blueprint_lookup.py --guid "<guid>"
    python3 scripts/query/blueprint_lookup.py --tag "<tag>"

Output:
  - found: true / false / "multiple"
  - matching record(s) with stable fields
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def load_blueprints() -> dict:
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    bp_path = REPO_ROOT / "data" / "raw" / version / "crafting_blueprints.json"
    if not bp_path.exists():
        sys.exit("ERROR: Run scripts/update_cache.sh first.")
    with open(bp_path) as f:
        return json.load(f)


def exact_lookup(bp_data: dict, *, guid: str | None = None, name: str | None = None,
                 tag: str | None = None) -> list[dict]:
    bps = bp_data.get("blueprints", [])
    matches = []
    for b in bps:
        if guid and b.get("guid") != guid:
            continue
        if name:
            prod = (b.get("productName") or "").lower()
            bp_tag = (b.get("tag") or "").lower()
            needle = name.lower()
            if needle != prod and needle != bp_tag:
                continue
        if tag and (b.get("tag") or "").lower() != tag.lower():
            continue
        matches.append(b)
    return matches


def summarize(bp: dict) -> dict:
    return {
        "guid": bp.get("guid"),
        "name": bp.get("productName") or bp.get("tag"),
        "product_name": bp.get("productName"),
        "tag": bp.get("tag"),
        "manufacturer": bp.get("manufacturer"),
        "type": bp.get("type"),
        "subtype": bp.get("subtype"),
        "tier_count": len(bp.get("tiers", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guid", help="Exact blueprint GUID")
    parser.add_argument("--name", help="Exact blueprint product name")
    parser.add_argument("--tag", help="Exact blueprint tag")
    args = parser.parse_args()

    if not any([args.guid, args.name, args.tag]):
        sys.exit("ERROR: provide --guid, --name, or --tag")

    bp_data = load_blueprints()
    matches = exact_lookup(bp_data, guid=args.guid, name=args.name, tag=args.tag)

    if not matches:
        print(json.dumps({"found": False, "query": vars(args)}))
        return

    if len(matches) == 1:
        record = matches[0]
        print(json.dumps({
            "found": True,
            "match": summarize(record),
            "record": record,
        }, indent=2))
        return

    print(json.dumps({
        "found": "multiple",
        "count": len(matches),
        "results": [summarize(bp) for bp in matches],
    }, indent=2))


if __name__ == "__main__":
    main()
