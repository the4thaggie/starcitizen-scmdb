#!/usr/bin/env bash
# Full cache refresh — fetch raw SCMDB data then transform into AI-ready JSON.
# Run when the game patches and data/VERSION is stale.
#
# Requirements:
#   - Internet access (scmdb.net)
#   - .env with UEX_API_TOKEN (for UEX price fetch step)
#   - Python 3.x
#   - Claude in Chrome active + logged into scmdb.net (for mining solver scrape)

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source "$REPO_ROOT/.env" 2>/dev/null || {
  echo "WARNING: .env not found — UEX fetch will be skipped."
}

echo "=== SCMDB Cache Update ==="

echo ""
echo "--- Step 1: Fetch raw SCMDB data files ---"
python3 "$REPO_ROOT/scripts/fetch/scmdb_raw.py"

VERSION="$(cat "$REPO_ROOT/data/VERSION")"
echo "Version: $VERSION"

echo ""
echo "--- Step 2: Transform missions ---"
python3 "$REPO_ROOT/scripts/transform/missions.py" "$VERSION"

echo ""
echo "--- Step 3: Transform fabricator ---"
python3 "$REPO_ROOT/scripts/transform/fabricator.py" "$VERSION"

echo ""
echo "--- Step 4: Transform resources ---"
python3 "$REPO_ROOT/scripts/transform/resources.py" "$VERSION"

echo ""
echo "--- Step 5: Fetch UEX prices (TODO) ---"
# python3 "$REPO_ROOT/scripts/fetch/uex_api.py"

echo ""
echo "--- Step 6: Fetch SC Wiki data ---"
python3 "$REPO_ROOT/scripts/fetch/wiki_api.py"

echo ""
echo "--- Step 6b: Transform SC Wiki data ---"
python3 "$REPO_ROOT/scripts/transform/wiki_items.py"

echo ""
echo "--- Step 7: Transform mining equipment ---"
python3 "$REPO_ROOT/scripts/transform/mining_equipment.py" "$VERSION"

echo ""
echo "=== Done. Review data/ then commit: ==="
echo "  git add data/VERSION data/missions/$VERSION.json"
echo "  git commit -m \"chore: update data cache to $VERSION\""
