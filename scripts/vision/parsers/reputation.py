"""
Parser for the MobiGlas Reputation tab screenshot.

Extracts:
  - faction name (title heading)
  - relationship label (Ally / Neutral / Enemy / etc.)
  - rank list with per-rank green-bar fill percentage
  - which rank is currently in-progress and at what percentage

Coordinate system: all fractions are relative to the MobiGlas panel crop,
not the full screen. The panel is extracted by _base.extract_mobiglas() which
handles letterbox stripping and horizontal centering for any aspect ratio.

Output JSON contract: schemas/vision.schema.json → ReputationResult
"""

from datetime import datetime, timezone

from ._base import (
    crop_frac,
    enhance_for_ocr,
    extract_mobiglas,
    load_image,
    load_layout,
    measure_green_fill,
    run_ocr,
)

_COMPLETE_THRESHOLD = 98
_LOCKED_THRESHOLD   = 2


def parse(image_path: str) -> dict:
    """
    Parse a MobiGlas Reputation tab screenshot.

    Args:
        image_path: Absolute path to screenshot (PNG/JPG). Caller handles cleanup.

    Returns:
        dict conforming to ReputationResult in schemas/vision.schema.json.
    """
    layout   = load_layout("reputation")
    img      = load_image(image_path)
    mg_img, content_bounds, mg_bounds = extract_mobiglas(img)

    warnings: list[str] = []

    # Sanity-check: warn if MobiGlas crop looks implausibly small (detection failed)
    mg_w = mg_bounds[2] - mg_bounds[0]
    mg_h = mg_bounds[3] - mg_bounds[1]
    if mg_w < 400 or mg_h < 200:
        warnings.append(
            f"MobiGlas crop is unusually small ({mg_w}×{mg_h}px). "
            "Letterbox detection or panel geometry may be off — check _mobiglas constants."
        )

    # ── Faction name ──────────────────────────────────────────────────────────
    faction_name = run_ocr(
        enhance_for_ocr(crop_frac(mg_img, **_region(layout, "faction_title"))),
        single_line=True,
    )
    if not faction_name:
        faction_name = "UNKNOWN"
        warnings.append("OCR returned empty for faction_title region. Check calibration.")

    # ── Relationship label ────────────────────────────────────────────────────
    relationship = run_ocr(
        enhance_for_ocr(crop_frac(mg_img, **_region(layout, "relationship"))),
        single_line=True,
    )
    if not relationship:
        relationship = "UNKNOWN"
        warnings.append("OCR returned empty for relationship region. Check calibration.")

    # ── Standing rows ─────────────────────────────────────────────────────────
    st    = layout["standing"]
    green = layout["bar_green"]
    ranks: list[dict] = []

    for i in range(st["max_rows"]):
        row_y = st["first_row_y"] + i * st["row_height"]

        # Label: below the bar, uses configurable y-offset within cell
        label_y  = row_y + st["row_height"] * st.get("label_y_offset_within_row", 0.30)
        label_h  = st["row_height"] * st.get("label_h_within_row", 0.55)
        rank_name = run_ocr(
            enhance_for_ocr(crop_frac(mg_img, st["label_x"], label_y, st["label_w"], label_h)),
            single_line=True,
        )
        if not rank_name:
            break  # no more visible rows

        # Bar: thin strip near the TOP of each cell
        bar_y = row_y + st["row_height"] * st.get("bar_y_offset_within_row", 0.08)
        fill_pct = measure_green_fill(
            mg_img,
            x=st["bar_x"], y=bar_y,
            w=st["bar_w"], h=st["bar_h_frac"],
            bar_green=green,
        )

        if fill_pct >= _COMPLETE_THRESHOLD:
            state, fill_pct = "complete", 100
        elif fill_pct <= _LOCKED_THRESHOLD:
            state, fill_pct = "locked", 0
        else:
            state = "in_progress"

        ranks.append({"name": rank_name, "state": state, "progress_pct": fill_pct})

    if not ranks:
        warnings.append("No rank rows detected. Check calibration for the 'standing' region.")

    in_progress = next((r for r in ranks if r["state"] == "in_progress"), None)

    if layout.get("_calibration_status", "").startswith("NEEDS_CALIBRATION"):
        warnings.append(
            "hud_layouts.json reputation regions are not calibrated. "
            "Results may be inaccurate. Run scripts/vision/calibrate.py."
        )

    return {
        "hud": "reputation",
        "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "faction": faction_name,
        "relationship": relationship,
        "standing": {
            "in_progress_rank": in_progress["name"] if in_progress else None,
            "progress_pct": in_progress["progress_pct"] if in_progress else None,
            "ranks": ranks,
        },
        "warnings": warnings,
    }


def _region(layout: dict, key: str) -> dict:
    """Extract crop kwargs (x, y, w, h) from a layout sub-dict, stripping _note fields."""
    return {k: v for k, v in layout[key].items() if not k.startswith("_")}
