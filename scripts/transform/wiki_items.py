#!/usr/bin/env python3
"""
Transforms raw SC Wiki API JSON into compact, AI-queryable files.

Usage:
    python3 scripts/transform/wiki_items.py

Input:  data/wiki/raw/quantum_drives.json
        data/wiki/raw/mining_lasers.json
        data/wiki/raw/ships.json
Output: data/wiki/quantum_drives.json   — indexed by name
        data/wiki/mining_lasers.json    — indexed by name (base variant only)
        data/wiki/ships.json            — indexed by slug
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
RAW_DIR  = REPO_ROOT / "data" / "wiki" / "raw"
OUT_DIR  = REPO_ROOT / "data" / "wiki"


def load_raw(filename: str) -> list:
    path = RAW_DIR / filename
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run scripts/fetch/wiki_api.py first.")
    with open(path) as f:
        return json.load(f)


def power_draw(item: dict) -> float | None:
    try:
        return item["resource_network"]["usage"]["power"]["max"]
    except (KeyError, TypeError):
        return None


def em_signature(item: dict) -> float | None:
    try:
        return item["emission"]["em_min"]
    except (KeyError, TypeError):
        return None


def repair_time(item: dict) -> float | None:
    try:
        return item["resource_network"]["repair"]["time_to_repair"]
    except (KeyError, TypeError):
        return None


# ── Quantum Drives ────────────────────────────────────────────────────────────

def transform_qd(item: dict) -> dict:
    qd = item.get("quantum_drive", {})
    sj = qd.get("standard_jump", {})
    tt = qd.get("travel_time_10gm", {})
    mfr = item.get("manufacturer") or {}

    return {
        "name": item.get("name"),
        "uuid": item.get("uuid"),
        "grade": item.get("grade"),           # A/B/C/D — quality tier
        "class": item.get("class"),           # Military/Civilian/Industrial/Stealth
        "size": item.get("size"),
        "mass_kg": item.get("mass"),
        "manufacturer": mfr.get("name") if isinstance(mfr, dict) else mfr,
        "is_craftable": item.get("is_craftable", False),
        "base_stats": {
            "health_hp": (item.get("durability") or {}).get("health"),
            "power_draw": power_draw(item),
            "em_signature": em_signature(item),
            "repair_time_s": repair_time(item),
        },
        "performance": {
            "drive_speed_mms": round(sj.get("drive_speed", 0) / 1_000_000, 2),
            "drive_speed_formatted": sj.get("drive_speed_formatted"),
            "cooldown_s": sj.get("cooldown_time"),
            "spool_up_s": sj.get("spool_up_time"),
            "fuel_per_jump": qd.get("quantum_fuel_requirement"),
            "fuel_efficiency": qd.get("fuel_efficiency"),
            "fuel_per_gm_scu": qd.get("fuel_consumption_scu_per_gm"),
            "travel_time_10gm": tt.get("formatted") if isinstance(tt, dict) else None,
            "disconnect_range_km": round(qd.get("disconnect_range", 0) / 1000, 1),
        },
        "web_url": item.get("web_url"),
    }


# ── Mining Lasers ─────────────────────────────────────────────────────────────

def transform_laser(item: dict) -> dict:
    ml = item.get("mining_laser", {})
    lp = ml.get("laser_power", {})
    mfr = item.get("manufacturer") or {}
    modifier_map = ml.get("modifier_map") or {
        m["name"]: m["value"] for m in ml.get("modifiers", [])
    }

    return {
        "name": item.get("name"),
        "uuid": item.get("uuid"),
        "grade": item.get("grade"),
        "class": item.get("class"),
        "size": item.get("size"),
        "manufacturer": mfr.get("name") if isinstance(mfr, dict) else mfr,
        "is_craftable": item.get("is_craftable", False),
        "module_slots": ml.get("module_slots", 0),
        "power_min": lp.get("min"),
        "power_max": lp.get("max"),
        "power_transfer": ml.get("power_transfer"),
        "optimal_range_m": ml.get("optimal_range"),
        "maximum_range_m": ml.get("maximum_range"),
        "extraction_throughput": ml.get("extraction_throughput"),
        "modifiers": modifier_map,
        "power_draw": power_draw(item),
        "web_url": item.get("web_url"),
    }


# ── Ships ─────────────────────────────────────────────────────────────────────

def transform_ship(item: dict) -> dict:
    speed = item.get("speed", {})
    quantum = item.get("quantum", {})
    fuel = item.get("fuel", {})
    mfr = item.get("manufacturer") or {}

    return {
        "name": item.get("name"),
        "game_name": item.get("game_name"),
        "uuid": item.get("uuid"),
        "manufacturer": mfr.get("name") if isinstance(mfr, dict) else mfr,
        "role": item.get("role"),
        "career": item.get("career"),
        "ore_capacity_scu": item.get("ore_capacity"),
        "cargo_capacity_scu": item.get("cargo_capacity"),
        "crew_min": (item.get("crew") or {}).get("min"),
        "crew_max": (item.get("crew") or {}).get("max"),
        "health_hp": item.get("health"),
        "mass_kg": item.get("mass_total"),
        "speed": {
            "scm_ms": speed.get("scm"),
            "max_ms": speed.get("max"),
        },
        "quantum": {
            "speed_mms": round(quantum.get("quantum_speed", 0) / 1_000_000, 2),
            "spool_s": quantum.get("quantum_spool_time"),
            "fuel_capacity": quantum.get("quantum_fuel_capacity"),
        },
        "fuel": {
            "capacity": fuel.get("capacity"),
            "intake_rate": fuel.get("intake_rate"),
        },
        "insurance": item.get("insurance", {}),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def write(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    size_kb = path.stat().st_size // 1024
    count = len(data) if isinstance(data, (dict, list)) else "?"
    print(f"  → {path.relative_to(REPO_ROOT)}  ({count} items, {size_kb} KB)")


def main():
    print("=== Transform: SC Wiki items ===")

    # ── Quantum drives ──
    raw_qds = load_raw("quantum_drives.json")
    print(f"  Quantum drives raw: {len(raw_qds)}")

    # Keep base variants only (skip skins/collector editions with same class_name prefix)
    seen_class = set()
    qds_out = {}
    for item in raw_qds:
        if not item.get("is_base_variant", True):
            continue
        name = item.get("name")
        if not name or not item.get("quantum_drive"):
            continue
        # Deduplicate by name — wiki can have multiple entries (different slugs, same item)
        if name not in qds_out:
            qds_out[name] = transform_qd(item)

    write(OUT_DIR / "quantum_drives.json", qds_out)

    # ── Mining lasers ──
    raw_lasers = load_raw("mining_lasers.json")
    print(f"  Mining lasers raw: {len(raw_lasers)}")

    lasers_out = {}
    for item in raw_lasers:
        if not item.get("is_base_variant", True):
            continue
        name = item.get("name")
        if not name or not item.get("mining_laser"):
            continue
        if name not in lasers_out:
            lasers_out[name] = transform_laser(item)

    write(OUT_DIR / "mining_lasers.json", lasers_out)

    # ── Ships ──
    raw_ships = load_raw("ships.json")
    print(f"  Ships raw: {len(raw_ships)}")

    ships_out = {}
    for item in raw_ships:
        name = item.get("name", "").lower()
        ships_out[name] = transform_ship(item)

    write(OUT_DIR / "ships.json", ships_out)

    print("Done.")


if __name__ == "__main__":
    main()
