"""
Shared image processing utilities for HUD parsers.

Coordinate system
-----------------
All element coordinates in hud_layouts.json are expressed as fractions (0.0–1.0)
of the *MobiGlas panel crop* — NOT the full screen or full image.

Parse pipeline per call:
  1. load_image(path)            → PIL Image, normalised to 1080px tall (AR preserved)
  2. find_content_bounds(img)    → strips letterbox/pillarbox black bars
  3. compute_mobiglas_bounds()   → estimates panel position from content geometry
  4. img.crop(mg_bounds)         → MobiGlas crop used for all OCR and bar work
  5. crop_frac(mg_img, x,y,w,h) → element crops (fractions of MobiGlas)

Aspect ratio handling
---------------------
The MobiGlas panel has a fixed height relative to the screen height, and is
horizontally centered regardless of screen width (ultrawide gets more background
on the sides). Normalising to height-1080 makes the vertical fractions constant
across all 16:9+ resolutions. Horizontal centering is derived at runtime.

Dependencies: Pillow, pytesseract + system tesseract-ocr
  pip install Pillow pytesseract
  apt install tesseract-ocr   (Linux) / brew install tesseract (macOS)
"""

import colorsys
import json
import os
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat

CANONICAL_HEIGHT = 1080

_LAYOUTS_PATH = Path(__file__).parent.parent / "hud_layouts.json"
_LAYOUTS: dict | None = None


def load_layout(hud_name: str) -> dict:
    global _LAYOUTS
    if _LAYOUTS is None:
        with open(_LAYOUTS_PATH) as f:
            _LAYOUTS = json.load(f)
    return _LAYOUTS[hud_name]


def load_mobiglas_config() -> dict:
    global _LAYOUTS
    if _LAYOUTS is None:
        with open(_LAYOUTS_PATH) as f:
            _LAYOUTS = json.load(f)
    return _LAYOUTS["_mobiglas"]


# ── Image loading ─────────────────────────────────────────────────────────────

def load_image(path: str) -> Image.Image:
    """
    Load screenshot and normalise to CANONICAL_HEIGHT (1080px), preserving aspect ratio.
    A 3440×1440 ultrawide becomes 2580×1080. A 1920×1080 16:9 stays 1920×1080.
    """
    img = Image.open(path).convert("RGB")
    if img.height != CANONICAL_HEIGHT:
        scale = CANONICAL_HEIGHT / img.height
        img = img.resize((int(img.width * scale), CANONICAL_HEIGHT), Image.LANCZOS)
    return img


# Backwards-compat alias used by existing code.
load_and_normalise = load_image


# ── Content-area detection (letterbox / pillarbox) ────────────────────────────

def find_content_bounds(
    img: Image.Image,
    black_threshold: int = 15,
    min_band_px: int = 30,
) -> tuple[int, int, int, int]:
    """
    Detect game content area by stripping solid black letterbox/pillarbox bands.

    Returns (left, top, right, bottom) in image pixel coordinates.
    Falls back to full image if no qualifying dark bands are found.

    Parameters
    ----------
    black_threshold : int
        Mean channel value below which a row/column counts as 'black'.
    min_band_px : int
        Minimum consecutive dark rows/cols to qualify as a letterbox band
        (thin non-black strips like YouTube title bars are ignored).
    """
    W, H = img.size

    def row_dark(y: int) -> bool:
        mean = ImageStat.Stat(img.crop((0, y, W, y + 1))).mean
        return all(c < black_threshold for c in mean[:3])

    def col_dark(x: int, y0: int, y1: int) -> bool:
        mean = ImageStat.Stat(img.crop((x, y0, x + 1, y1))).mean
        return all(c < black_threshold for c in mean[:3])

    def scan_dark_edge(
        seq: range, is_dark_fn, min_band: int
    ) -> int:
        """
        Scan a sequence of positions inward from one edge.
        Returns the first index that ends a qualifying dark band (≥ min_band thick).
        Falls back to the first position if nothing qualifies.
        """
        run_start: int | None = None
        last_qualifying_end = seq.start

        for i in seq:
            if is_dark_fn(i):
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None:
                    band_len = abs(i - run_start)
                    if band_len >= min_band:
                        last_qualifying_end = i
                    run_start = None
                    # Stop scanning once we pass the first qualifying band and
                    # are clearly into non-black content (5+ consecutive bright rows).
                    if last_qualifying_end > seq.start:
                        break
        return last_qualifying_end

    top    = scan_dark_edge(range(H),          row_dark,                         min_band_px)
    bottom = scan_dark_edge(range(H - 1, -1, -1), row_dark,                     min_band_px)
    bottom = H - (bottom - 0) if bottom != 0 else H   # convert back to absolute

    # Re-derive bottom correctly: scan_dark_edge returns an absolute index going forward.
    # Redo with a cleaner reverse scan:
    bottom = H
    run_start = None
    last_q = H
    for y in range(H - 1, -1, -1):
        if row_dark(y):
            if run_start is None:
                run_start = y
        else:
            if run_start is not None:
                band_len = run_start - y
                if band_len >= min_band_px:
                    last_q = y + 1
                run_start = None
                if last_q < H:
                    break
    bottom = last_q

    left = 0
    run_start = None
    last_q = 0
    for x in range(W):
        if col_dark(x, top, bottom):
            if run_start is None:
                run_start = x
        else:
            if run_start is not None:
                if (x - run_start) >= min_band_px:
                    last_q = x
                run_start = None
                if last_q > 0:
                    break
    left = last_q

    right = W
    run_start = None
    last_q = W
    for x in range(W - 1, -1, -1):
        if col_dark(x, top, bottom):
            if run_start is None:
                run_start = x
        else:
            if run_start is not None:
                if (run_start - x) >= min_band_px:
                    last_q = x + 1
                run_start = None
                if last_q < W:
                    break
    right = last_q

    return left, top, right, bottom


# ── MobiGlas panel location ───────────────────────────────────────────────────

def compute_mobiglas_bounds(
    content_left: int,
    content_top: int,
    content_right: int,
    content_bottom: int,
    mg_config: dict | None = None,
) -> tuple[int, int, int, int]:
    """
    Estimate MobiGlas panel bounds within the game content area.

    The panel is:
    - height = fixed fraction of content height  (same pixels at any AR)
    - top    = fixed fraction of content height from content top
    - width  = panel_height × fixed_aspect_ratio
    - center = horizontal center of content area

    Returns (left, top, right, bottom) in image pixel coordinates.
    """
    if mg_config is None:
        mg_config = load_mobiglas_config()

    content_w  = content_right  - content_left
    content_h  = content_bottom - content_top
    content_cx = content_left + content_w / 2

    mg_h = content_h * mg_config["height_frac_of_content"]
    mg_w = mg_h      * mg_config["width_to_height_ratio"]
    mg_t = content_top + content_h * mg_config["top_frac_of_content"]

    mg_left   = content_cx - mg_w / 2
    mg_right  = content_cx + mg_w / 2
    mg_bottom = mg_t + mg_h

    # Clamp to content area
    return (
        max(content_left,   int(mg_left)),
        max(content_top,    int(mg_t)),
        min(content_right,  int(mg_right)),
        min(content_bottom, int(mg_bottom)),
    )


def extract_mobiglas(
    img: Image.Image,
    mg_config: dict | None = None,
) -> tuple[Image.Image, tuple[int, int, int, int], tuple[int, int, int, int]]:
    """
    Full pipeline: strip letterbox → locate MobiGlas → return crop.

    Returns:
        mg_crop       : cropped MobiGlas panel image
        content_bounds: (left, top, right, bottom) of game content
        mg_bounds     : (left, top, right, bottom) of MobiGlas panel
    Both bounds are in normalised-image pixel coordinates.
    """
    if mg_config is None:
        mg_config = load_mobiglas_config()
    content_bounds = find_content_bounds(img)
    mg_bounds      = compute_mobiglas_bounds(*content_bounds, mg_config)
    return img.crop(mg_bounds), content_bounds, mg_bounds


# ── Element cropping ──────────────────────────────────────────────────────────

def crop_frac(img: Image.Image, x: float, y: float, w: float, h: float) -> Image.Image:
    """
    Crop using fractional (0.0–1.0) coordinates relative to *img* dimensions.
    When called on a MobiGlas crop, coordinates are MobiGlas-panel-relative.
    """
    iw, ih = img.size
    return img.crop((
        int(x       * iw),
        int(y       * ih),
        int((x + w) * iw),
        int((y + h) * ih),
    ))


# ── OCR helpers ───────────────────────────────────────────────────────────────

def enhance_for_ocr(img: Image.Image, scale: int = 3) -> Image.Image:
    """
    Prepare a region crop for Tesseract.
    SC HUD text is light on dark background → invert, upscale, sharpen, threshold.
    """
    gray     = ImageOps.grayscale(img)
    gray     = ImageEnhance.Contrast(gray).enhance(2.5)
    inverted = ImageOps.invert(gray)
    enlarged = inverted.resize(
        (inverted.width * scale, inverted.height * scale),
        Image.LANCZOS,
    )
    sharpened = enlarged.filter(ImageFilter.SHARPEN)
    return sharpened.point(lambda p: 255 if p > 140 else 0, "L")


def run_ocr(img: Image.Image, single_line: bool = True) -> str:
    """Run Tesseract OCR. Raises ImportError if pytesseract is not installed."""
    try:
        import pytesseract
    except ImportError as exc:
        raise ImportError(
            "pytesseract is required for HUD parsing. "
            "Install: pip install pytesseract && apt install tesseract-ocr"
        ) from exc
    config = (
        "--psm 7 -c tessedit_char_whitelist="
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,-'"
        if single_line else "--psm 6"
    )
    return pytesseract.image_to_string(img, config=config).strip()


# ── Green bar measurement ─────────────────────────────────────────────────────

def measure_green_fill(
    img: Image.Image,
    x: float, y: float, w: float, h: float,
    bar_green: dict,
) -> int:
    """
    Count HSV-matched green pixels in a fractional region of *img*.
    Fractions are relative to *img* (pass the MobiGlas crop, not the full image).
    Returns 0–100 (integer).
    """
    region = crop_frac(img, x, y, w, h)
    pixels = list(region.getdata())
    if not pixels:
        return 0

    h_min = bar_green["h_min_deg"] / 360.0
    h_max = bar_green["h_max_deg"] / 360.0
    s_min = bar_green["s_min"]
    v_min = bar_green["v_min"]

    green_count = sum(
        1 for r, g, b in pixels
        if (lambda hue, sat, val: h_min <= hue <= h_max and sat >= s_min and val >= v_min)(
            *colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        )
    )
    return round(green_count / len(pixels) * 100)


def cleanup(path: str) -> None:
    """Delete the image file. Silently ignores missing files."""
    try:
        os.unlink(path)
    except OSError:
        pass
