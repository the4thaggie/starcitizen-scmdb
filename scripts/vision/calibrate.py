#!/usr/bin/env python3
"""
Visual calibration helper for HUD region coordinates.

Overlays three levels of bounding boxes onto a reference screenshot:
  1. Content bounds (blue)    — game content after letterbox stripping
  2. MobiGlas bounds (green)  — estimated panel location
  3. Element regions (colors) — individual HUD fields within the panel

Use this to verify coordinates before processing real user screenshots.

Usage:
    python3 scripts/vision/calibrate.py --hud reputation --image ref.png
    # → ref_annotated.png  (saved next to the input file)

Dependencies: Pillow (pip install Pillow)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from parsers._base import (
    CANONICAL_HEIGHT,
    compute_mobiglas_bounds,
    compute_right_panel_bounds,
    find_content_bounds,
    load_image,
    load_layout,
    load_mobiglas_config,
)
from PIL import ImageDraw


def main() -> None:
    ap = argparse.ArgumentParser(description="Annotate HUD region coordinates on a screenshot.")
    ap.add_argument("--hud",   required=True, help="HUD type (e.g. reputation)")
    ap.add_argument("--image", required=True, help="Path to reference screenshot")
    args = ap.parse_args()

    img           = load_image(args.image)
    W, H          = img.size
    mg_config     = load_mobiglas_config()
    content_bounds = find_content_bounds(img)
    mg_bounds      = compute_mobiglas_bounds(*content_bounds, mg_config)
    mg_l, mg_t, mg_r, mg_b = mg_bounds
    mg_w = mg_r - mg_l
    mg_h = mg_b - mg_t

    draw = ImageDraw.Draw(img)

    # ── Level 1: content bounds (blue) ────────────────────────────────────────
    cl, ct, cr, cb = content_bounds
    draw.rectangle([cl, ct, cr - 1, cb - 1], outline="blue", width=3)
    draw.text((cl + 4, ct + 4), "content", fill="blue")

    # ── Level 2: MobiGlas bounds (lime) ───────────────────────────────────────
    draw.rectangle([mg_l, mg_t, mg_r - 1, mg_b - 1], outline="lime", width=3)
    draw.text((mg_l + 4, mg_t + 4), "MobiGlas", fill="lime")

    # ── Level 3: element regions (MobiGlas-relative → image coords) ──────────
    def mg_rect(label: str, x: float, y: float, w: float, h: float, colour: str) -> None:
        """Convert MobiGlas-relative fractions to image pixel coords and draw."""
        left   = mg_l + int(x       * mg_w)
        top    = mg_t + int(y       * mg_h)
        right  = mg_l + int((x + w) * mg_w)
        bottom = mg_t + int((y + h) * mg_h)
        draw.rectangle([left, top, right, bottom], outline=colour, width=2)
        draw.text((left + 2, top + 1), label, fill=colour)

    layout = load_layout(args.hud)

    if args.hud == "mining":
        # For the mining HUD we only need to verify the RESULTS panel bounds —
        # OCR parses the whole panel, so no per-field boxes needed.
        rp = layout["_results_panel"]
        rp_bounds = compute_right_panel_bounds(*content_bounds, rp)
        rl, rt, rr, rb = rp_bounds
        draw.rectangle([rl, rt, rr - 1, rb - 1], outline="orange", width=3)
        draw.text((rl + 4, rt + 4), "RESULTS panel (full OCR block)", fill="orange")

    elif args.hud == "reputation":
        ft  = layout["faction_title"]
        mg_rect("faction_title", ft["x"], ft["y"], ft["w"], ft["h"], "cyan")

        rel = layout["relationship"]
        mg_rect("relationship", rel["x"], rel["y"], rel["w"], rel["h"], "yellow")

        st = layout["standing"]
        for i in range(st["max_rows"]):
            row_y = st["first_row_y"] + i * st["row_height"]

            # Label region
            label_y = row_y + st["row_height"] * st.get("label_y_offset_within_row", 0.30)
            label_h = st["row_height"] * st.get("label_h_within_row", 0.55)
            mg_rect(f"label[{i}]", st["label_x"], label_y, st["label_w"], label_h, "lime")

            # Bar region
            bar_y = row_y + st["row_height"] * st.get("bar_y_offset_within_row", 0.08)
            mg_rect(f"bar[{i}]", st["bar_x"], bar_y, st["bar_w"], st["bar_h_frac"], "orange")

    out_path = os.path.splitext(args.image)[0] + "_annotated.png"
    img.save(out_path)

    print(f"Annotated image saved: {out_path}")
    print(f"Input size (normalised): {W}×{H}")
    print(f"Content bounds: {content_bounds}")
    print(f"MobiGlas bounds: {mg_bounds}  ({mg_w}×{mg_h}px)")

    # Report detected aspect ratio
    cl, ct, cr, cb = content_bounds
    content_ar = (cr - cl) / (cb - ct)
    ref_ar = W / H
    print(f"Content AR: {content_ar:.3f}  (image AR: {ref_ar:.3f})")
    if abs(content_ar - ref_ar) > 0.05:
        print(f"  → Letterbox/pillarbox detected")


if __name__ == "__main__":
    main()
