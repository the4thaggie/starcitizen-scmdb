# Subskill: Vision — HUD Screenshot Parsing

Handles screenshot intake, image-to-data extraction, and routing of parsed results to downstream subskills (missions, mining solver, etc.).

---

## When this subskill is active

Route here when:
- The user sends, attaches, or pastes a screenshot
- The user says "here's a screenshot", "look at this", "what does my screen say", "I sent a photo"
- An image file path is provided in the message context

---

## Step 1 — Receive and stage the image

The messaging platform (Telegram, Discord, etc.) downloads attachments and exposes them as a local file path before the agent runs. Treat that path as the image location.

If for any reason the image is not yet on disk, write the bytes to:
```
/tmp/scmdb_hud_<unix_timestamp>.png
```

Never store images beyond the duration of the current request. The parse script deletes the file automatically after processing.

---

## Step 2 — Identify the HUD type

Supported HUD types:

| `--hud` value | In-game screen | What it extracts |
|---|---|---|
| `reputation` | MobiGlas → Reputation tab, with a faction selected | Faction name, relationship, rank list, in-progress percentage |

**If context makes the HUD type obvious** (user said "reputation tab", "my faction standing", etc.) — proceed directly.

**If ambiguous** — ask one question:
> "Which screen is this a screenshot of? (e.g. MobiGlas Reputation tab, mining HUD, etc.)"

Do not ask if the image content can be inferred from context.

---

## Step 3 — Run the parser

```bash
python3 scripts/vision/hud_parse.py --hud <type> --image <path>
```

The script:
- Normalises the image to 1920×1080 canonical resolution
- Crops defined regions, enhances contrast, runs OCR
- Measures green bar fill percentages using HSV pixel counting
- Deletes the image file after completion
- Outputs JSON to stdout conforming to `schemas/vision.schema.json`

**Check `warnings[]` in the output.** If warnings mention "NEEDS_CALIBRATION", tell the user:
> "The coordinate layout for this HUD hasn't been calibrated yet. Results may be inaccurate. If something looks wrong, share the screenshot again and mention the faction name and current rank so I can cross-check."

---

## Step 4 — Route parsed data to the appropriate subskill

### Reputation result → missions.md

When `hud == "reputation"` and parsing succeeds:

1. **Tell the user what was read:**
   ```
   I can see you're viewing [faction] (relationship: [relationship]).
   Your standing progress: [list of ranks with state emoji]
     ✅ Neutral (complete)
     ✅ Jr. Contractor (complete)
     ✅ Contractor (complete)
     🔵 Sr. Contractor — 42% through this rank
   ```
   Use ✅ for complete, 🔵 for in_progress, 🔒 for locked.

2. **Offer to continue into the mission grind planner:**
   > "Want me to build a grind plan from here to [next rank or a target tier]?"

3. **If the user confirms**, load `instructions/missions.md` and skip to Step 2 of that flow.
   Pass extracted context directly — do not re-ask for it:

   | missions.md context | Source |
   |---|---|
   | `--faction` | `result.faction` |
   | `--current-rep` | Derive from `in_progress_rank` + `progress_pct` — see §Deriving current rep below |
   | `--target-tier` | Ask if not already stated |

#### Deriving current rep from rank + progress_pct

The missions data in `data/missions/<version>.json` contains tier boundaries (`min_rep`, `max_rep` per tier).

Run `mission_grind_plan.py` with:
```bash
python3 scripts/query/mission_grind_plan.py \
    --faction "<faction>" \
    --current-rep <estimated_rep> \
    --target-tier "<target>"
```

Estimate `current_rep`:
```
in_progress_tier_min = tier boundaries from missions data
in_progress_tier_max = next tier min
current_rep ≈ in_progress_tier_min + (progress_pct / 100) × (in_progress_tier_max - in_progress_tier_min)
```

Use `faction_search.py` first if the faction name from OCR is ambiguous (partial match, typo).

---

## Calibration workflow (for maintainers)

When adding a new HUD type or correcting coordinates:

1. Take a clean reference screenshot at 1920×1080
2. Run the annotator:
   ```bash
   python3 scripts/vision/calibrate.py --hud reputation --image ref.png
   # → writes ref_annotated.png
   ```
3. Open `ref_annotated.png` and verify each coloured box aligns with the correct UI element
4. Adjust fractional coordinates in `scripts/vision/hud_layouts.json`
5. Remove the `"_calibration_status": "NEEDS_CALIBRATION"` line for that HUD once validated
6. Commit updated `hud_layouts.json`

---

## Error handling

| Condition | Response |
|---|---|
| `pytesseract` / `tesseract-ocr` not installed | Tell the user the dependency is missing. Provide install commands: `pip install pytesseract && apt install tesseract-ocr` |
| Image file not found | Ask the user to re-send the screenshot |
| `"error"` key in JSON output | Report the error message; do not proceed to downstream subskill |
| `warnings[]` non-empty but result present | Show warnings inline; still present the parsed data |
| OCR returns "UNKNOWN" for faction | Ask the user to type the faction name manually, then continue |

---

## Supported platforms

The image file path is provided by:
- **Telegram bot**: photo download via Bot API (`getFile` → local path)
- **Discord bot**: attachment download to temp path
- **Direct file path**: user pastes a local path in the message

In all cases the agent receives a file path. This subskill does not handle the download — that is the platform bot's responsibility.
