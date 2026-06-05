#!/usr/bin/env python3
"""
Fetches LIVE sell prices for mining materials from the UEX Corp API.
Called at query time — prices update every ~30 minutes.
No authentication required.

Usage:
    python3 scripts/query/commodity_prices.py \
        --materials "Borase,Tungsten,Ouratite" \
        --system Stanton \
        --top 3

Output (JSON):
    {
      "fetched_at": "2026-06-05T...",
      "system_filter": "Stanton",
      "auth": false,
      "materials": {
        "Borase": {
          "raw": {          ← unrefined ore prices (what you sell straight from the ship)
            "commodity_name": "Borase (Ore)",
            "best_price_sell": 28000,
            "terminals": [ { name, system, location, price_sell, scu_stock, quality_avg } ]
          },
          "refined": {      ← refined commodity prices (after running through a refinery)
            "commodity_name": "Borase",
            "best_price_sell": 33000,
            "terminals": [ ... ]
          }
        }
      },
      "refinery_note": "Refining improves sell price but takes time and costs fees.",
      "refinery_methods": [ { name, yield, cost, speed } ],
      "nearby_refineries": [ { name, system, location } ]
    }
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
BASE_URL = "https://api.uexcorp.uk/2.0"
RATE_DELAY = 0.4


def make_headers() -> dict:
    h = {
        "User-Agent": "starcitizen-scmdb/1.0",
        "Accept": "application/json",
    }
    token = os.environ.get("UEX_API_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def api_get(path: str, params: dict = None) -> list | dict:
    url = f"{BASE_URL}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=make_headers())
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    return data.get("data", [])


def load_commodities() -> dict:
    """Return name-keyed commodity index from cached list."""
    path = REPO_ROOT / "data" / "uex" / "commodities.json"
    if not path.exists():
        sys.exit("ERROR: data/uex/commodities.json missing. Run scripts/fetch/uex_api.py first.")
    with open(path) as f:
        raw = json.load(f)
    return {c["name"]: c for c in raw}


def load_refinery_methods() -> list:
    path = REPO_ROOT / "data" / "uex" / "refinery_methods.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def load_refinery_terminals(system: str | None) -> list:
    path = REPO_ROOT / "data" / "uex" / "refinery_terminals.json"
    if not path.exists():
        return []
    with open(path) as f:
        terms = json.load(f)
    if system:
        terms = [t for t in terms if t.get("star_system_name") == system]
    # Deduplicate by name (multiple terminal entries per station)
    seen = set()
    result = []
    for t in terms:
        key = t.get("space_station_name") or t.get("outpost_name") or t.get("name")
        if key not in seen:
            seen.add(key)
            result.append({
                "name": t.get("name"),
                "system": t.get("star_system_name"),
                "location": (t.get("space_station_name") or t.get("outpost_name")
                             or t.get("moon_name") or t.get("planet_name")),
            })
    return result[:8]  # top 8 nearby refineries


def fetch_prices(commodity_name: str, system: str | None, top: int) -> dict | None:
    """Fetch live sell prices for a named commodity, filtered by system."""
    try:
        rows = api_get("commodities_prices", {"commodity_name": commodity_name})
    except Exception as e:
        return {"error": str(e)}

    # Filter by system if specified
    if system:
        rows = [r for r in rows if r.get("star_system_name") == system]

    # Keep only rows with a sell price
    sellable = [r for r in rows if (r.get("price_sell") or 0) > 0]
    if not sellable:
        return None

    # Sort by best sell price
    sellable.sort(key=lambda r: -(r.get("price_sell") or 0))

    def fmt_terminal(r: dict) -> dict:
        location = (r.get("space_station_name") or r.get("outpost_name")
                    or r.get("moon_name") or r.get("planet_name") or "?")
        return {
            "terminal": r.get("terminal_name"),
            "system": r.get("star_system_name"),
            "location": location,
            "price_sell": r.get("price_sell"),
            "price_sell_avg_week": r.get("price_sell_avg_week"),
            "quality_avg": r.get("quality_avg"),
            "scu_demand": r.get("scu_sell"),
            "game_version": r.get("game_version"),
            "last_updated": datetime.datetime.fromtimestamp(
                r["date_modified"], tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M UTC") if r.get("date_modified") else None,
        }

    best = sellable[0]
    return {
        "commodity_name": commodity_name,
        "best_price_sell": best.get("price_sell"),
        "game_version": best.get("game_version"),
        "terminals": [fmt_terminal(r) for r in sellable[:top]],
    }


def find_commodity_pair(name: str, index: dict) -> tuple[str | None, str | None]:
    """
    Return (raw_name, refined_name) for a material.
    E.g. "Borase" → ("Borase (Ore)", "Borase")
         "Borase Ore" → ("Borase (Ore)", "Borase")
    """
    # Normalise input
    clean = name.strip()
    clean_lower = clean.lower().replace(" ore", "").replace(" (raw)", "").replace(" (ore)", "").strip()

    # Find refined form (is_raw=0, is_mineral=1 or just is_raw=0 with matching name)
    refined_name = None
    raw_name = None

    for n, c in index.items():
        n_base = n.lower().replace(" ore", "").replace(" (raw)", "").replace(" (ore)", "").strip()
        if n_base == clean_lower:
            if c.get("is_raw", 0) == 1:
                raw_name = n
            else:
                # Prefer shorter name as the "refined" form
                if refined_name is None or len(n) < len(refined_name):
                    refined_name = n

    return raw_name, refined_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials", required=True,
                        help="Comma-separated material names, e.g. Borase,Tungsten,Ouratite")
    parser.add_argument("--system", default=None, help="Filter to system: Stanton | Pyro | Nyx")
    parser.add_argument("--top", type=int, default=3, help="Top N terminals per material (default: 3)")
    parser.add_argument("--raw-only", action="store_true",
                        help="Only show raw ore prices (skip refined lookup)")
    args = parser.parse_args()

    commodity_index = load_commodities()
    methods = load_refinery_methods()
    nearby_refineries = load_refinery_terminals(args.system)
    using_auth = bool(os.environ.get("UEX_API_TOKEN", "").strip())

    material_names = [m.strip() for m in args.materials.split(",")]
    results = {}

    for mat in material_names:
        raw_name, refined_name = find_commodity_pair(mat, commodity_index)

        entry: dict = {}

        if raw_name:
            prices = fetch_prices(raw_name, args.system, args.top)
            if prices:
                entry["raw"] = prices
            time.sleep(RATE_DELAY)

        if refined_name and not args.raw_only:
            prices = fetch_prices(refined_name, args.system, args.top)
            if prices:
                entry["refined"] = prices
            time.sleep(RATE_DELAY)

        if not entry:
            entry["error"] = f"No price data found for '{mat}' in {'system ' + args.system if args.system else 'any system'}"

        results[mat] = entry

    # Format refinery methods for output
    method_summary = [
        {
            "name": m["name"],
            "yield": ["low", "medium", "high"][m["rating_yield"] - 1],
            "cost": ["low", "medium", "high"][m["rating_cost"] - 1],
            "speed": ["slow", "medium", "fast"][m["rating_speed"] - 1],
        }
        for m in methods
    ]

    print(json.dumps({
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "system_filter": args.system or "all",
        "auth": using_auth,
        "note": "Prices update ~every 30 minutes. raw = sell ore directly; refined = refinery first (better price, costs time + fees).",
        "materials": results,
        "refinery_methods": method_summary,
        "nearby_refineries": nearby_refineries,
    }, indent=2))


if __name__ == "__main__":
    main()
