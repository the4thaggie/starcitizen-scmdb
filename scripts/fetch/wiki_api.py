#!/usr/bin/env python3
"""
Fetches ship and component data from the Star Citizen Wiki API.
Supplements mining equipment data with canonical ship/component specs.

API base: https://api.star-citizen.wiki/api/
Docs: https://api.star-citizen.wiki (Swagger)
No authentication required.

TODO: implement fetch logic
  - GET /vehicles — ship specs relevant to mining (Prospector, Golem, Mole)
  - GET /items — component/equipment metadata as needed
  - Merge relevant fields into data/mining/equipment.json
"""
