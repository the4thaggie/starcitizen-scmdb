#!/usr/bin/env python3
"""
Fetches item and vehicle data from the Star Citizen Wiki API.
Saves raw responses to data/wiki/raw/ for the transform step.

API base: https://api.star-citizen.wiki/api/v2/
No authentication required.

Usage:
    python3 scripts/fetch/wiki_api.py

Fetches:
    - All quantum drives   → data/wiki/raw/quantum_drives.json
    - All mining lasers    → data/wiki/raw/mining_lasers.json
    - Mining ships         → data/wiki/raw/ships.json
"""

import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
RAW_DIR = REPO_ROOT / "data" / "wiki" / "raw"

BASE_URL = "https://api.star-citizen.wiki/api/v2"
HEADERS = {
    "User-Agent": "starcitizen-scmdb/1.0 (github.com/the4thaggie/starcitizen-scmdb)",
    "Accept": "application/json",
}
PAGE_SIZE = 100
RATE_LIMIT_DELAY = 0.5  # seconds between requests


def get(path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_all_pages(path: str, params: dict = None) -> list:
    """Fetch all pages of a paginated endpoint."""
    params = dict(params or {})
    params["page[size]"] = PAGE_SIZE
    params["page[number]"] = 1

    all_items = []
    while True:
        data = get(path, params)
        items = data.get("data", [])
        all_items.extend(items)

        meta = data.get("meta", {})
        current = meta.get("current_page", 1)
        last = meta.get("last_page", 1)

        print(f"    page {current}/{last} — {len(items)} items")

        if current >= last:
            break
        params["page[number]"] = current + 1
        time.sleep(RATE_LIMIT_DELAY)

    return all_items


def save(dest: Path, data: list | dict) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        json.dump(data, f, indent=2)
    print(f"      → {dest.relative_to(REPO_ROOT)}  ({dest.stat().st_size // 1024} KB)")


def main():
    print("=== SC Wiki API Fetch ===")

    # Quantum drives — all sizes
    print("\n  Fetching quantum drives...")
    qd_path = RAW_DIR / "quantum_drives.json"
    if qd_path.exists():
        print("    SKIP (exists)")
    else:
        items = fetch_all_pages("items", {"filter[type]": "QuantumDrive"})
        save(qd_path, items)

    time.sleep(RATE_LIMIT_DELAY)

    # Mining lasers
    print("\n  Fetching mining lasers (WeaponMining)...")
    laser_path = RAW_DIR / "mining_lasers.json"
    if laser_path.exists():
        print("    SKIP (exists)")
    else:
        items = fetch_all_pages("items", {"filter[type]": "WeaponMining"})
        save(laser_path, items)

    time.sleep(RATE_LIMIT_DELAY)

    # Mining ships — fetch each by name
    print("\n  Fetching mining ships...")
    ships_path = RAW_DIR / "ships.json"
    if ships_path.exists():
        print("    SKIP (exists)")
    else:
        ships = []
        for ship_name in ["Prospector", "Golem", "MOLE"]:
            print(f"    GET {ship_name}...")
            data = get("vehicles", {"filter[name]": ship_name})
            ship_results = data.get("data", [])
            # Take base variant (filter out collector's editions etc.)
            base = next(
                (s for s in ship_results if s.get("name", "").lower() == ship_name.lower()),
                ship_results[0] if ship_results else None,
            )
            if base:
                ships.append(base)
            time.sleep(RATE_LIMIT_DELAY)
        save(ships_path, ships)

    print("\nDone.")


if __name__ == "__main__":
    main()
