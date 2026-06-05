#!/usr/bin/env python3
"""
Scrapes mission data from SCMDB.net using Claude in Chrome.
Writes output to data/missions/<version>.json and updates data/VERSION.

TODO: implement scraping logic
  - Navigate to https://scmdb.net/?page=missions
  - Iterate through mission cards (filtered by each faction/type combination)
  - For each mission: click to open, extract all 4 tabs (Overview, Requirements, Calculator, Community)
  - Validate output against schemas/missions.schema.json
  - Write to data/missions/<version>.json
"""
