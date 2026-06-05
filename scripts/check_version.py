#!/usr/bin/env python3
"""
Compares the live SCMDB patch version against the locally cached data/VERSION.

Exit codes:
  0 — versions match, cache is current
  1 — mismatch or cache uninitialized (prints live version)
  2 — network error
"""

import json
import sys
import urllib.request
from pathlib import Path

DATA_VERSION_FILE = Path(__file__).parent.parent / "data" / "VERSION"
VERSIONS_URL = "https://scmdb.net/data/game-versions.json"


def read_cached_version() -> str:
    text = DATA_VERSION_FILE.read_text().strip()
    return "" if text == "UNINITIALIZED" else text


def read_live_version() -> str:
    with urllib.request.urlopen(VERSIONS_URL, timeout=10) as resp:
        versions = json.loads(resp.read())
    if not versions:
        raise RuntimeError("Empty version list from game-versions.json")
    return versions[0]["version"]


def main():
    cached = read_cached_version()

    try:
        live = read_live_version()
    except Exception as e:
        print(f"ERROR reading live version: {e}", file=sys.stderr)
        sys.exit(2)

    if not cached:
        print(f"Cache UNINITIALIZED. Live version: {live}")
        print("Run:  bash scripts/update_cache.sh")
        sys.exit(1)

    if cached == live:
        print(f"Cache current: {cached}")
        sys.exit(0)
    else:
        print(f"STALE — cached: {cached}  live: {live}")
        print("Run:  bash scripts/update_cache.sh")
        sys.exit(1)


if __name__ == "__main__":
    main()
