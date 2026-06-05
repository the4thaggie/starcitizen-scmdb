#!/usr/bin/env python3
"""
Parse game HUD data from a Star Citizen screenshot.

The agent calls this after receiving a screenshot from the user. The script
prints JSON to stdout, then deletes the image (unless --no-cleanup).

Usage:
    python3 scripts/vision/hud_parse.py --hud reputation --image /tmp/sc_hud_123.png

    # Keep file for debugging:
    python3 scripts/vision/hud_parse.py --hud reputation --image shot.png --no-cleanup

Supported HUD types:
    reputation  — MobiGlas Reputation tab
                  → faction name, relationship, rank list, in-progress percentage

Output (JSON to stdout):
    {
      "hud": "reputation",
      "parsed_at": "2026-06-05T12:00:00Z",
      "faction": "Adagio Holdings",
      "relationship": "Ally",
      "standing": {
        "in_progress_rank": "Sr. Contractor",
        "progress_pct": 42,
        "ranks": [
          { "name": "Neutral",        "state": "complete",    "progress_pct": 100 },
          { "name": "Jr. Contractor", "state": "complete",    "progress_pct": 100 },
          { "name": "Contractor",     "state": "complete",    "progress_pct": 100 },
          { "name": "Sr. Contractor", "state": "in_progress", "progress_pct": 42  }
        ]
      },
      "warnings": []
    }

Error output (non-zero exit + JSON):
    { "error": "<message>", "hud": "reputation" }

Dependencies:
    pip install Pillow pytesseract
    apt install tesseract-ocr   (Linux) / brew install tesseract (macOS)
"""

import argparse
import json
import os
import sys

# Allow running from repo root or from scripts/vision/
sys.path.insert(0, os.path.dirname(__file__))

from parsers import reputation as _rep

PARSERS = {
    "reputation": _rep,
}


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Parse a Star Citizen HUD screenshot to JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See DesignDoc.md §16 for the full vision pipeline design.",
    )
    ap.add_argument(
        "--hud",
        required=True,
        choices=list(PARSERS),
        help="Which HUD type to parse.",
    )
    ap.add_argument(
        "--image",
        required=True,
        metavar="PATH",
        help="Path to the screenshot file (PNG or JPG).",
    )
    ap.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Do not delete the image after parsing (default: image is deleted).",
    )
    args = ap.parse_args()

    if not os.path.isfile(args.image):
        _exit_error(f"Image not found: {args.image}", args.hud)

    try:
        result = PARSERS[args.hud].parse(args.image)
    except ImportError as exc:
        _exit_error(str(exc), args.hud)
    except Exception as exc:
        _exit_error(f"Parse failed: {exc}", args.hud)
    finally:
        if not args.no_cleanup:
            _delete(args.image)

    print(json.dumps(result, indent=2))


def _exit_error(message: str, hud: str) -> None:
    print(json.dumps({"error": message, "hud": hud}, indent=2))
    sys.exit(1)


def _delete(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


if __name__ == "__main__":
    main()
