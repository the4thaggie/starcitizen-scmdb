"""
Parser for the Argo MOLE (and Prospector/Golem) mining HUD screenshot.

Extracts the RESULTS panel on the right side of the screen:
  - Primary ore being targeted (name at top of RESULTS)
  - Rock stats: mass, resistance %, instability, difficulty label
  - Rock composition: per-material percentage, name, and per-SCU price
  - Cargo status: current / max SCU and cargo contents list

Why OCR-the-panel, not crop-individual-fields
---------------------------------------------
The composition block has a variable number of rows (1–6+ materials) and the
cargo contents list also varies. Cropping fixed regions for each would miss
rows outside the expected count. Instead, we OCR the entire RESULTS panel as
a multi-line block (Tesseract --psm 6) and parse the text with regex.

Output JSON contract: schemas/vision.schema.json → MiningResult

Supported ships: MOLE, Prospector, Golem (all share the same RESULTS layout).
"""

import re
from datetime import datetime, timezone

from ._base import (
    compute_right_panel_bounds,
    crop_frac,
    enhance_for_ocr,
    find_content_bounds,
    load_image,
    load_layout,
    run_ocr,
)

# ── Compiled regexes (order-independent; applied to each line) ─────────────────
_RE_MASS     = re.compile(r'MASS\s*[:.]\s*(\d[\d\s]*\d|\d)', re.IGNORECASE)
_RE_RES      = re.compile(r'RES\s*[:.]\s*(\d+)\s*%', re.IGNORECASE)
_RE_INST     = re.compile(r'INST\s*[:.]\s*([\d.]+)', re.IGNORECASE)
_RE_DIFF     = re.compile(r'\b(EASY|MEDIUM|HARD|VERY\s*HARD|IMPOSSIBLE)\b', re.IGNORECASE)
_RE_COMP_HDR = re.compile(r'COMP\s*[.:]?\s*([\d.]+)\s*SCU', re.IGNORECASE)
_RE_COMP_ROW = re.compile(
    r'([\d.]+)\s*%\s+'            # percentage  e.g.  "6.44%"
    r'(.+?)\s{2,}'                # material name     "LARANITE (RAW)"  (2+ spaces before value)
    r'(\d+)',                     # per-SCU value     "698"
)
_RE_CARGO    = re.compile(r'CARGO\s+([\d.]+)\s*/\s*([\d.]+)\s*SCU', re.IGNORECASE)
_RE_CARGO_IT = re.compile(r'(.+?)\s+([\d.]+)\s*SCU\s*$', re.IGNORECASE)

# OCR threshold: lower than default to capture the green/orange text common in the mining HUD
_OCR_THRESHOLD = 100


def parse(image_path: str) -> dict:
    """
    Parse a MOLE (or Prospector/Golem) mining HUD screenshot.

    Args:
        image_path: Absolute path to screenshot (PNG/JPG). Caller handles cleanup.

    Returns:
        dict conforming to MiningResult in schemas/vision.schema.json.
    """
    layout = load_layout("mining")
    img    = load_image(image_path)

    content_bounds  = find_content_bounds(img)
    panel_bounds    = compute_right_panel_bounds(*content_bounds, layout["_results_panel"])
    panel_crop      = img.crop(panel_bounds)

    pw = panel_bounds[2] - panel_bounds[0]
    ph = panel_bounds[3] - panel_bounds[1]

    warnings: list[str] = []
    if pw < 100 or ph < 100:
        warnings.append(
            f"Results panel crop is unusually small ({pw}×{ph}px). "
            "Check _mining_hud panel constants or content detection."
        )

    # OCR the whole panel as a multi-line block (--psm 6 layout analysis)
    panel_enhanced = _enhance_mining(panel_crop)
    raw_text       = run_ocr(panel_enhanced, single_line=False)

    rock, cargo, parse_warnings = _parse_results_text(raw_text)
    warnings.extend(parse_warnings)

    return {
        "hud": "mining",
        "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rock": rock,
        "cargo": cargo,
        "warnings": warnings,
    }


# ── Text parsing ──────────────────────────────────────────────────────────────

def _parse_results_text(text: str) -> tuple[dict, dict, list[str]]:
    warnings: list[str] = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    rock: dict = {
        "primary_material":  None,
        "mass_kg":           None,
        "resistance_pct":    None,
        "instability":       None,
        "difficulty":        None,
        "composition_scu":   None,
        "composition":       [],
    }
    cargo: dict = {
        "current_scu": None,
        "max_scu":     None,
        "contents":    [],
    }

    in_composition = False
    in_cargo       = False

    for i, line in enumerate(lines):
        # ── Faction / header markers ──────────────────────────────────────────
        if line.upper() == "RESULTS":
            # Primary material is on the next non-empty line
            for j in range(i + 1, min(i + 3, len(lines))):
                cand = lines[j]
                # Skip lines that look like field labels
                if not re.match(r'^(MASS|RES|INST|COMP|CARGO)\b', cand, re.IGNORECASE):
                    rock["primary_material"] = cand
                    break
            continue

        # ── Numeric fields ────────────────────────────────────────────────────
        m = _RE_MASS.search(line)
        if m:
            rock["mass_kg"] = int(re.sub(r'\s', '', m.group(1)))
            continue

        m = _RE_RES.search(line)
        if m:
            rock["resistance_pct"] = int(m.group(1))
            continue

        m = _RE_INST.search(line)
        if m:
            rock["instability"] = float(m.group(1))
            continue

        m = _RE_DIFF.search(line)
        if m:
            rock["difficulty"] = m.group(1).upper().replace("  ", " ")
            continue

        m = _RE_COMP_HDR.search(line)
        if m:
            rock["composition_scu"] = float(m.group(1))
            in_composition = True
            in_cargo       = False
            continue

        m = _RE_CARGO.search(line)
        if m:
            cargo["current_scu"] = float(m.group(1))
            cargo["max_scu"]     = float(m.group(2))
            in_composition = False
            in_cargo       = True
            continue

        # ── Variable-length blocks ────────────────────────────────────────────
        if in_composition:
            m = _RE_COMP_ROW.search(line)
            if m:
                rock["composition"].append({
                    "pct":      float(m.group(1)),
                    "material": m.group(2).strip(),
                    "value":    int(m.group(3)),
                })
                continue
            # A line that doesn't match a composition row ends the block
            if not re.match(r'^\d', line):
                in_composition = False

        if in_cargo:
            m = _RE_CARGO_IT.search(line)
            if m:
                name = m.group(1).strip()
                if name.upper() not in ("CARGO", "RESULTS"):
                    cargo["contents"].append({
                        "material": name,
                        "scu":      float(m.group(2)),
                    })

    # Sanity checks
    if rock["primary_material"] is None:
        warnings.append("Could not identify primary material. OCR may have missed the RESULTS header.")
    if rock["mass_kg"] is None:
        warnings.append("Could not read MASS value.")
    if not rock["composition"]:
        warnings.append(
            "No composition rows parsed. The COMP block may have been cut off or OCR noise is high."
        )

    return rock, cargo, warnings


# ── Image enhancement ─────────────────────────────────────────────────────────

def _enhance_mining(img):
    """
    Specialised OCR prep for the mining HUD.

    The panel mixes bright green, orange, and white text on a near-black
    background. We use a lower threshold (100 vs the default 140) so that
    green text — which has medium luminance after grayscale — is kept rather
    than discarded.
    """
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    gray     = ImageOps.grayscale(img)
    gray     = ImageEnhance.Contrast(gray).enhance(2.5)
    inverted = ImageOps.invert(gray)
    enlarged = inverted.resize(
        (inverted.width * 3, inverted.height * 3),
        Image.LANCZOS,
    )
    sharpened = enlarged.filter(ImageFilter.SHARPEN)
    return sharpened.point(lambda p: 255 if p > _OCR_THRESHOLD else 0, "L")
