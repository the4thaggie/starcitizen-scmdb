#!/usr/bin/env python3
"""
Scrapes blueprint/fabricator data from SCMDB.net using Claude in Chrome.
Writes output to data/fabricator/<version>.json.

TODO: implement scraping logic
  - Navigate to https://scmdb.net/?page=fabricator
  - Iterate through blueprint cards
  - For each blueprint: extract faction, rank requirements, mission prerequisites,
    material costs, and disassembly details
  - Handle "owned" state (available when logged in)
  - Validate against schemas/fabricator.schema.json
"""
