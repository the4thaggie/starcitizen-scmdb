# Resources Subskill — Workflow

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

## Step 5 — Sell prices (offer after route is presented)

After presenting the mining route, offer:
> "Want me to check current sell prices and refinery options for these materials?"

If yes, run:
```bash
python3 scripts/query/commodity_prices.py \
  --materials "<mat1,mat2,mat3>" \
  --system <Stanton|Pyro|Nyx> \
  --top 3
```

**Output keys:**

| Key | Use |
|---|---|
| `materials.<name>.refined.best_price_sell` | Best aUEC/SCU for refined material — the primary sell target |
| `materials.<name>.refined.terminals[]` | Top terminals: name, location, price, last_updated |
| `materials.<name>.raw` | Raw ore buy-back price (if available) — lower but no refinery wait |
| `refinery_methods[]` | Show as a table: name, yield, cost, speed — user picks based on patience |
| `nearby_refineries[]` | List the closest refineries in the system |
| `fetched_at` | Cite this — prices are live, not cached |
| `auth` | If false: note prices are community-reported, may lag by ~30 min |

**Present as:**
```
SELL PRICES (live — as of [fetched_at])

Material   │ Refined $/SCU │ Best Terminal             │ Raw $/SCU
──────────────────────────────────────────────────────────────────
Borase     │ 31,000        │ Admin - MIC-L1 (Stanton)  │ N/A
Tungsten   │ 11,000        │ Admin - Nyx Gateway       │ N/A
Ouratite   │ 46,000        │ TDD - New Babbage         │ N/A

REFINERY OPTIONS (for raw ore → refined commodity)
  Dinyx Solventation: high yield, low cost, slow    ← best value if not in a rush
  Ferron Exchange:    high yield, medium cost, slow ← alternative
  Gaskin Process:     medium yield, high cost, fast ← if you need the credits quickly

Nearby Stanton refineries: ARC-L1, ARC-L2, ARC-L3, ARC-L4, ARC-L5 (all Lagrange stations)
```

**Refinery method guidance:**
- For casual miners: recommend **Dinyx Solventation** (high yield, low cost — just takes longer)
- For time-pressured runs: recommend **Gaskin Process** or **Cormack** (fast, costs more)
- Never recommend high-cost + slow methods (Pyrometric Chromalysis) unless user asks

**Auth note:**
The skill works without a UEX API token for all price lookups. If `UEX_API_TOKEN` is set in `.env`,
it will be used for better rate limits. Neither the user nor the agent needs to log in to UEX for prices.
