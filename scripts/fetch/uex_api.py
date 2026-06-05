#!/usr/bin/env python3
"""
Fetches commodity prices and terminal data from the UEX API.
Supplements resources data with live community-reported prices.

API base: https://api.uexcorp.space/2.0/
Authentication: Bearer token from UEX_API_TOKEN environment variable.

TODO: implement fetch logic
  - GET /commodities_prices — current buy/sell prices for mineable materials
  - GET /terminals — terminal locations for selling mined materials
  - Write price data into data/resources/<version>.json price fields
"""

import os
import sys

UEX_API_BASE = "https://api.uexcorp.space/2.0"


def get_token() -> str:
    token = os.environ.get("UEX_API_TOKEN", "").strip()
    if not token:
        print("ERROR: UEX_API_TOKEN not set. See .env.example.", file=sys.stderr)
        sys.exit(1)
    return token
