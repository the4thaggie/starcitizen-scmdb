#!/usr/bin/env python3
"""
Transforms mining_equipment-<version>.json into data/mining/equipment.json.
This file is ship-patch-stable: equipment stats change with patches, not daily.

Usage:
    python3 scripts/transform/mining_equipment.py [<version>]

Input:  data/raw/<version>/mining_equipment.json
Output: data/mining/equipment.json   (always overwrites — version tracked inside)
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# Ships with their archetype, laser slots, and any fixed/built-in equipment
SHIPS = {
    "prospector": {
        "name": "Prospector",
        "manufacturer": "MISC",
        "archetype": "ship",
        "laser_slots": 1,
        "laser_size": 1,
        "cargo_scu": 12,
        "note": "Solo ship miner. 1 configurable S1 laser slot.",
    },
    "golem": {
        "name": "Golem",
        "manufacturer": "Drake Interplanetary",
        "archetype": "ship",
        "laser_slots": 1,
        "laser_size": 1,
        "cargo_scu": 12,
        "fixed_laser": "Pitman Mining Laser",
        "note": "Solo ship miner. Fixed S1 Pitman laser — cannot swap laser head. Modules still configurable.",
    },
    "mole": {
        "name": "MOLE",
        "manufacturer": "Argo Astronautics",
        "archetype": "ship",
        "laser_slots": 3,
        "laser_size": 2,
        "cargo_scu": 96,
        "note": "Multi-crew S2 miner. Up to 3 operators, each controlling one S2 laser independently.",
    },
}


def normalize_laser(laser: dict) -> dict:
    mods = laser.get("modifiers", {})
    beam = laser.get("miningBeam", {})
    return {
        "name": laser["name"],
        "size": laser.get("size"),
        "grade": laser.get("grade"),
        "manufacturer": laser.get("manufacturer"),
        "module_slots": laser.get("moduleSlots", 0),
        "vehicle_built_in": laser.get("vehicleBuiltIn"),
        "dps": beam.get("damagePerSecond"),
        "full_damage_range_m": beam.get("fullDamageRange"),
        "modifiers": {
            "instability_pct": mods.get("instability", 0),
            "opt_window_size_pct": mods.get("optimalChargeWindowSize", 0),
            "resistance_pct": mods.get("resistance", 0),
            "opt_charge_rate_pct": mods.get("optimalChargeRate", 0),
            "filter_pct": mods.get("filter", 0),
        },
    }


def normalize_module(mod: dict) -> dict:
    mods = mod.get("modifiers", {})
    out = {
        "name": mod["name"],
        "type": mod.get("type"),   # "passive" | "active"
        "size": mod.get("size"),
        "grade": mod.get("grade"),
        "manufacturer": mod.get("manufacturer"),
        "modifiers": {
            "instability_pct": mods.get("instability", 0),
            "opt_window_size_pct": mods.get("optimalChargeWindowSize", 0),
            "resistance_pct": mods.get("resistance", 0),
        },
    }
    if mod.get("type") == "active":
        out["charges"] = mod.get("charges")
        out["lifetime_s"] = mod.get("lifetime")
        out["mining_damage_multiplier"] = mod.get("miningDamageMultiplier", 1.0)
    return out


def normalize_gadget(g: dict) -> dict:
    mods = g.get("modifiers", {})
    return {
        "name": g["name"],
        "manufacturer": g.get("manufacturer"),
        "modifiers": {
            "instability_pct": mods.get("instability", 0),
            "opt_window_size_pct": mods.get("optimalChargeWindowSize", 0),
            "resistance_pct": mods.get("resistance", 0),
        },
        "note": "Placed on the rock before fracturing. Ask user before recommending — not all players use gadgets.",
    }


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else (REPO_ROOT / "data" / "VERSION").read_text().strip()
    if not version or version == "UNINITIALIZED":
        sys.exit("ERROR: provide version or run fetch first.")

    print(f"=== Transform: mining equipment ({version}) ===")

    path = REPO_ROOT / "data" / "raw" / version / "mining_equipment.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run scripts/fetch/scmdb_raw.py first.")

    with open(path) as f:
        raw = json.load(f)

    lasers_raw = raw.get("lasers", [])
    modules_raw = raw.get("modules", [])
    gadgets_raw = raw.get("gadgets", [])
    global_params = raw.get("globalParams", {})

    lasers = [normalize_laser(l) for l in lasers_raw]
    modules = [normalize_module(m) for m in modules_raw]
    gadgets = [normalize_gadget(g) for g in gadgets_raw]

    # Split modules for clarity
    passive_modules = [m for m in modules if m["type"] == "passive"]
    active_modules = [m for m in modules if m["type"] == "active"]

    print(f"  Lasers: {len(lasers)}  Passive modules: {len(passive_modules)}  Active modules: {len(active_modules)}  Gadgets: {len(gadgets)}")

    out = {
        "version": version,
        "ships": SHIPS,
        "lasers": lasers,
        "passive_modules": passive_modules,
        "active_modules": active_modules,
        "gadgets": gadgets,
        "global_params": global_params,
        "notes": {
            "modifiers": "All modifier values are percentage adjustments to the rock's base stat (e.g., instability_pct: -35 means net instability = rock_instability × 0.65).",
            "module_slots": "Each laser has a fixed number of module slots. Modules fill these slots — total active + passive cannot exceed slot count.",
            "gadgets": "Placed on the rock itself, not the laser. Ask the user before suggesting gadgets — not all players carry them.",
            "golem_fixed_laser": "The Golem's Pitman laser cannot be swapped. Only modules are configurable for the Golem.",
            "mole_multi_crew": "Each MOLE laser is controlled independently by one operator. Stats are per-laser, not combined.",
        },
    }

    out_path = REPO_ROOT / "data" / "mining" / "equipment.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    size_kb = out_path.stat().st_size // 1024
    print(f"  → {out_path.relative_to(REPO_ROOT)}  ({size_kb} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
