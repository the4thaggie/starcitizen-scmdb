#!/usr/bin/env python3
"""
Scrapes mining resource/location data from SCMDB.net using Claude in Chrome.
Writes output to data/resources/<version>.json.

TODO: implement scraping logic
  - Navigate to https://scmdb.net/?page=mine
  - Iterate through all location cards
  - For each location: open detail card, extract Ship Mining table
  - For each material row: click to expand hidden detail row
    Fields: material | chance% | quality range | difficulty | quality score (0-1000)
  - Validate against schemas/resources.schema.json
"""
