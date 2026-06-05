#!/usr/bin/env python3
"""
Downloads raw SCMDB data files for the current patch version.
Writes to data/raw/<version>/ (gitignored).
Updates data/VERSION on success.

Usage:
    python3 scripts/fetch/scmdb_raw.py
"""

import json
import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://scmdb.net/data"
REPO_ROOT = Path(__file__).parent.parent.parent


HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url: str) -> list | dict:
    return json.loads(fetch(url))


def get_current_version() -> tuple[str, str]:
    versions = fetch_json(f"{BASE_URL}/game-versions.json")
    if not versions:
        raise RuntimeError("Empty version list from game-versions.json")
    latest = versions[0]
    return latest["version"], latest["file"]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  GET {url}")
    dest.write_bytes(fetch(url, timeout=60))
    size_kb = dest.stat().st_size // 1024
    print(f"      → {dest.relative_to(REPO_ROOT)}  ({size_kb} KB)")


def main():
    print("=== SCMDB Raw Fetch ===")

    print("Checking live version...")
    version, filename = get_current_version()
    print(f"Current patch: {version}")

    raw_dir = REPO_ROOT / "data" / "raw" / version

    files = [
        (f"{BASE_URL}/{filename}",                              raw_dir / "merged.json"),
        (f"{BASE_URL}/crafting_blueprints-{version}.json",     raw_dir / "crafting_blueprints.json"),
        (f"{BASE_URL}/crafting_items-{version}.json",          raw_dir / "crafting_items.json"),
        (f"{BASE_URL}/mission-history-{version}.json",         raw_dir / "mission_history.json"),
        (f"{BASE_URL}/mining_data-{version}.json",             raw_dir / "mining_data.json"),
    ]

    any_downloaded = False
    for url, dest in files:
        if dest.exists():
            print(f"  SKIP (exists): {dest.name}")
            continue
        try:
            download(url, dest)
            any_downloaded = True
        except urllib.error.HTTPError as e:
            print(f"  WARN {e.code}: {url}", file=sys.stderr)
        except Exception as e:
            print(f"  WARN: {url} — {e}", file=sys.stderr)

    version_file = REPO_ROOT / "data" / "VERSION"
    version_file.write_text(version + "\n")
    if any_downloaded:
        print(f"Updated data/VERSION → {version}")
    else:
        print("All files already present. data/VERSION unchanged.")


if __name__ == "__main__":
    main()
