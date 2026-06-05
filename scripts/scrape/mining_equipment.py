#!/usr/bin/env python3
"""
Scrapes mining equipment constants from the SCMDB mining solver UI using Claude in Chrome.
Writes output to data/mining/equipment.json (patch-stable constants).
Also writes data/mining/<version>.json for any per-patch solver variables.

TODO: implement scraping logic
  - Navigate to https://scmdb.net/?page=mining_solver (confirm URL)
  - For each ship: select, record laser hardpoint count
  - For each laser/head option: record name, module slot count, base stats
  - For each module: record name, type (passive/active), charges, stat modifiers
  - For each gadget: record name and effect
  - Drive the solver UI with known inputs, record Stats panel output to calibrate formulas
  - Validate against schemas/mining.schema.json
"""
