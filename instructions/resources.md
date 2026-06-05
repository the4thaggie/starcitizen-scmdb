# Resources Subskill — Workflow

> [Design Doc §9](../DesignDoc.md#9-subskill-resources) · called from: [fabricator.md](fabricator.md) · escalates to: [mining_solver/index.md](mining_solver/index.md)

Handles: mining location lookup, material availability by system, crack difficulty, and route planning.

---

## Step 1 — Collect context

| Item | Question | Default |
|---|---|---|
| `materials` | "Which material(s) are you looking for?" | Must have — if called from fabricator.md, already known |
| `system` | "Which system are you currently in?" | No filter — show all, flag it |
| `ship` | "What mining ship are you flying?" | "unknown" — conservative profile used, flag it |

If called from `instructions/fabricator.md`, materials are already known — skip to Step 2.

---

## Step 2 — Run mining locations script

```bash
python3 scripts/query/mining_locations.py \
  --materials "<mat1,mat2,mat3>" \
  --system <Stanton|Pyro|Nyx> \
  --ship <prospector|golem|mole|unknown>
```

**Output keys:**

| Key | Use |
|---|---|
| `ship_profile_note` | Include in context for user — describes ship capability assumed |
| `materials.<name>.rarity` | Inform user of material difficulty to find |
| `materials.<name>.instability` | Higher = harder to manage power window |
| `materials.<name>.resistance` | Higher = harder to crack; negative = easier |
| `materials.<name>.crack_assessment` | Plain-language crack difficulty — surface directly |
| `materials.<name>.top_locations[]` | Best locations for this material in chosen system |
| `recommended_route[]` | The optimal multi-stop route |
| `recommended_route[].materials_here[]` | What you're collecting at this stop |
| `recommended_route[].overall_risk` | Risk level for this stop |
| `recommended_route[].notes[]` | Surface any warnings here — especially crack difficulty |
| `warnings[]` | Surface all of these to the user before the route |

---

## Step 3 — Present the route

Lead with warnings if any, then present as a numbered route:

```
Stop 1 — Lagrange A (Stanton) [Risk: low]
  Mine: Borase (1.24 SCU) + Tungsten (0.50 SCU)
  Notes: Both within stock Prospector capability. No atmosphere.

Stop 2 — Yela Asteroid Belt (Stanton) [Risk: low]
  Mine: Ouratite (0.50 SCU)
  Notes: Instability 600 — high. Manage power window carefully.
         Active modules (Surge, Vaux) will help stabilize.
```

After the route, summarize material properties:
- For each material: rarity, instability, resistance, crack_assessment
- Flag if any material exceeds the ship's capability

---

## Step 4 — Mining difficulty guidance

**When instability is high (≥ 500):**
> "[Material] has instability [n]. Keep your laser power in the green window and reduce power quickly if the instability indicator rises. Active modules like the Surge or Vaux help absorb instability spikes. If you don't have active modules, use very short power bursts."

**When resistance is high (≥ 0.6):**
> "[Material] has resistance [n]. Stock laser may struggle to crack it. An upgraded laser head or a charge gadget placed on the rock before fracturing will help. If the rock won't fracture, it may require more laser power than your current loadout provides."

**When resistance is negative:**
> "[Material] has negative resistance ([n]) — this means the rock cracks more easily than average. You'll need less power than usual; be careful not to overcharge."

---

## Branching rules

**If system not specified:**
Run without `--system` and show the full list, but note:
> "I'm showing all systems. Which system are you in? I can narrow this to reduce travel."

**If ship is "unknown":**
> "I'm using conservative estimates. If you tell me your mining ship, I can give more accurate crack assessments."

**If a material's `crack_assessment` contains "difficult":**
Prompt the mining solver:
> "Cracking [material] may require an upgraded loadout. Want me to check if your current laser + modules can handle it?" 
If yes → load `instructions/mining_solver/index.md`.

**If no locations found in the specified system:**
> "I couldn't find [material] in [system]. It appears in: [list other systems]. Would you like locations from those instead?"
Re-run without `--system`.

---

## Step 5 — Material acquisition plan (offer after route is presented)

After presenting the mining route, collect two more context items before running:

| Item | Question | Default |
|---|---|---|
| `refinery_pref` | "Do you prefer the **nearest** refinery, **best yield**, best **economy** (yield minus cost), or **fastest** turnaround?" | `yield` |
| `refine_what` | "Do you want to refine **everything**, just what you need for the craft (**needed**), or let me decide per-material based on economics (**selective**)?" | `selective` |

Then run:
```bash
python3 scripts/query/material_acquisition_plan.py \
  --blueprint "<name>" \
  --ship <prospector|golem|mole> \
  --location "<mining location>" \
  --system <Stanton|Pyro|Nyx> \
  --refinery-pref <nearest|yield|economy|speed> \
  --refine-what <all|needed|selective>
```

**Output keys to present:**

| Key | Use |
|---|---|
| `materials[].refined_needed_scu` | How much refined material the blueprint needs |
| `materials[].yield_scenarios` | Raw ore needed under high/medium/low yield — show as table |
| `materials[].trip_scenarios[]` | Worst/middle/best trips per material — key insight |
| `materials[].economics.refined_sell_price_per_scu` | Value of refined output |
| `materials[].economics.worth_refining` | Whether economics support refining vs selling raw |
| `total_trip_estimates` | Combined trips for ALL materials — usually fewer than per-material |
| `refineries_ranked[0]` | Best refinery under chosen preference |
| `refineries_ranked[].net_yields` | Net yield % per material at each terminal |
| `refineries_ranked[].recommended_methods` | Methods aligned to preference |
| `refineries_ranked[].travel_min` | Quantum travel time in minutes (nearest pref only) |
| `selective_refining` | Per-material refine/sell-raw/dump decision with reasoning |
| `caveats[]` | Always surface all caveats — yield/fee values are approximations |

**Present as:**
```
MATERIAL ACQUISITION PLAN — Yeager  (Prospector, Stanton, yield preference)

RAW ORE NEEDED  (to produce required refined quantities)
Material  │ Need refined │ High yield │ Medium yield │ Low yield │ Best refinery bonus
──────────────────────────────────────────────────────────────────────────────────────
Borase    │ 1.24 SCU    │ 1.57 SCU  │ 1.72 SCU    │ 1.94 SCU  │ MIC-L5 +9% → 1.41 SCU
Tungsten  │ 0.50 SCU    │ 0.63 SCU  │ 0.69 SCU    │ 0.78 SCU  │ no bonus   → 0.63 SCU
Ouratite  │ 0.50 SCU    │ 0.63 SCU  │ 0.69 SCU    │ 0.78 SCU  │ no bonus   → 0.63 SCU

MINING TRIPS  (total all materials combined: fits in 1 Prospector run)
  Worst case (low yield, sparse rocks):  2.7 SCU raw → 1 trip
  Middle case (medium yield):            2.7 SCU raw → 1 trip
  Best case  (high yield):               2.7 SCU raw → 1 trip
  Note: Ouratite comes from a different location (Yela/Aberdeen) — plan a 2nd stop.

BEST REFINERY — MIC-L5 (Stanton, by yield)
  Methods: Dinyx Solventation / Ferron Exchange / Pyrometric Chromalysis (all high yield)
  Borase yield: 88% (base 79% + MIC-L5 +9%)  → need 1.41 SCU raw for 1.24 refined
  Tungsten:     79%  Ouratite: 79%

SELL PRICES (live)
  Borase refined:   31,000 aUEC/SCU  @ MIC-L1
  Tungsten refined: 11,000 aUEC/SCU  @ Nyx Gateway
  Ouratite refined: 46,000 aUEC/SCU  @ TDD New Babbage

REFINING DECISION (selective mode)
  ✓ Refine Borase   — refined value 31k >> raw (not traded directly)
  ✓ Refine Tungsten — refined value 11k >> raw (not traded directly)
  ✓ Refine Ouratite — refined value 46k >> raw (not traded directly)

⚠ CAVEATS: yield/fee percentages are approximations. Verify exact fee in-game before submitting the refinery job.
```

**Multi-location note:**
If materials come from different locations (check Step 2 route), remind the user:
> "Borase and Tungsten are at Lagrange A; Ouratite is at Yela Belt or Aberdeen. Plan two stops — collect each at its location before heading to the refinery."

**Refinery method guidance:**
- `yield` pref → Dinyx Solventation (high yield, low cost, slow): best if not time-pressured
- `speed` pref → Cormack or XCR Reaction (fast but low yield, costs vary)
- `economy` pref → Dinyx Solventation (high yield, low cost = best net value)
- User specifies method → pass `--method "<name>"` to override

**Data availability:**
All UEX price and refinery endpoints used by this skill are public. No account or API key is required. Prices are community-reported and typically update within 30 minutes of in-game changes.
