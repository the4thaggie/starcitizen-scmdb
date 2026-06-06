# Mining material lookup notes

Scope: exact-name behavior for mining locations and material acquisition planning.

## Rules
- Treat `--materials` as exact mining-data material names in the main flow.
- Do not substring-match a partial material name to select a record.
- If the user only remembers part of a name, return a short candidate menu instead of guessing.
- Canonicalize common display suffixes when comparing commodity names:
  - ` (Ore)`
  - ` Ore`
  - ` (Raw)`
  - ` Raw`
- System filters should be case-insensitive exact comparisons.
- Refinery terminal names should be compared exactly, case-insensitive.
- If a target cannot be resolved, return the exact missing token plus candidate names.

## Helpful commands
```bash
python3 scripts/query/mining_locations.py --materials 'Borase,Tungsten,Ouratite' --system Stanton --ship Prospector
python3 scripts/query/mining_locations.py --materials 'Bora' --system Stanton --ship Prospector
python3 scripts/query/material_acquisition_plan.py --guid <blueprint-guid> --blueprint <exact-name> --ship prospector --location '<terminal>' --system Stanton
```

## Verification pattern
- `python3 -m py_compile scripts/query/mining_locations.py scripts/query/material_acquisition_plan.py`
- Run one exact lookup and one partial-input failure path to confirm candidate hints are returned.
