#!/usr/bin/env python3
"""
Fetches static reference data from the UEX Corp API (api.uexcorp.uk/2.0).
Static data = changes only on game patch, safe to commit to the repo.
All endpoints used here are public — no authentication required.

Usage:
    python3 scripts/fetch/uex_api.py

Fetches:
    - All commodities           → data/uex/commodities.json
    - Refinery terminals        → data/uex/refinery_terminals.json
    - Refinery methods          → data/uex/refinery_methods.json
    - Refinery terminal IDs     → data/uex/refinery_terminal_ids.json
    - Refinery yield bonuses    → data/uex/refinery_yields.json
"""

import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
OUT_DIR = REPO_ROOT / "data" / "uex"

BASE_URL = "https://api.uexcorp.uk/2.0"
RATE_DELAY = 0.5


HEADERS = {
    "User-Agent": "starcitizen-scmdb/1.0 (github.com/the4thaggie/starcitizen-scmdb)",
    "Accept": "application/json",
}


def get(path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def save(dest: Path, data) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        json.dump(data, f, indent=2)
    count = len(data) if isinstance(data, (list, dict)) else "?"
    print(f"      → {dest.relative_to(REPO_ROOT)}  ({count} items, {dest.stat().st_size // 1024} KB)")


def main():
    print("=== UEX API Fetch ===")

    # 1. All commodities — name/code/ID mapping, is_raw/is_mineral flags
    print("\n  Fetching commodities...")
    comm_path = OUT_DIR / "commodities.json"
    if comm_path.exists():
        print("    SKIP (exists)")
    else:
        data = get("commodities")
        save(comm_path, data.get("data", []))

    time.sleep(RATE_DELAY)

    # 2. Refinery terminals (is_refinery=1)
    print("\n  Fetching refinery terminals...")
    ref_path = OUT_DIR / "refinery_terminals.json"
    if ref_path.exists():
        print("    SKIP (exists)")
    else:
        data = get("terminals", {"type": "commodity", "is_refinery": 1})
        terminals = data.get("data", [])
        # Filter to meaningful fields
        slim = [
            {
                "id": t["id"],
                "name": t.get("name"),
                "code": t.get("code"),
                "star_system_name": t.get("star_system_name"),
                "planet_name": t.get("planet_name"),
                "moon_name": t.get("moon_name"),
                "space_station_name": t.get("space_station_name"),
                "outpost_name": t.get("outpost_name"),
                "is_player_owned": t.get("is_player_owned", 0),
                "max_container_size": t.get("max_container_size"),
            }
            for t in terminals
        ]
        save(ref_path, slim)

    time.sleep(RATE_DELAY)

    # 3. Refinery methods (yield/cost/speed ratings)
    print("\n  Fetching refinery methods...")
    meth_path = OUT_DIR / "refinery_methods.json"
    if meth_path.exists():
        print("    SKIP (exists)")
    else:
        data = get("refineries_methods")
        save(meth_path, data.get("data", []))

    time.sleep(RATE_DELAY)

    # 4. Refinery terminals with IDs (needed for distance calculations)
    print("\n  Fetching refinery terminals with IDs...")
    ref_id_path = OUT_DIR / "refinery_terminal_ids.json"
    if ref_id_path.exists():
        print("    SKIP (exists)")
    else:
        data = get("terminals", {"type": "refinery"})
        terminals = data.get("data", [])
        slim = [
            {
                "id": t["id"],
                "name": t.get("name"),
                "code": t.get("terminal_code") or t.get("code"),
                "nickname": t.get("nickname"),
                "star_system_name": t.get("star_system_name"),
                "planet_name": t.get("planet_name"),
                "orbit_name": t.get("orbit_name"),
                "moon_name": t.get("moon_name"),
                "space_station_name": t.get("space_station_name"),
                "outpost_name": t.get("outpost_name"),
            }
            for t in terminals
        ]
        save(ref_id_path, slim)

    time.sleep(RATE_DELAY)

    # 5. Per-terminal refinery yield bonuses per commodity
    print("\n  Fetching refinery yields...")
    yields_path = OUT_DIR / "refinery_yields.json"
    if yields_path.exists():
        print("    SKIP (exists)")
    else:
        data = get("refineries_yields")
        save(yields_path, data.get("data", []))

    print("\nDone.")
    print("Note: Commodity prices are fetched live at query time via scripts/query/commodity_prices.py")


if __name__ == "__main__":
    main()
