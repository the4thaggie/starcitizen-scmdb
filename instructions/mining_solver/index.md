# Mining Solver Subskill — Entry Point

> [Design Doc §10](../../DesignDoc.md#10-subskill-mining-solver) · math: [math.md](math.md) · formats: [output_formats.md](output_formats.md)

Handles: laser selection, module configuration, rock crackability, net stats, loadout recommendations.
If math is requested, also load `math.md`. For final formatted output, also load `output_formats.md`.

---

## Step 0 — Identify the archetype

Ask if not clear from context:
> "Are you ship mining (Prospector, Golem, MOLE), vehicle mining (ROC), or hand mining?"

- **Ship mining** → continue below
- **ROC / hand mining** → note that the solver supports these archetypes in data but query scripts
  currently focus on ship mining; provide what you can and flag the limitation

---

## Step 1 — Collect context

| Item | Question | Default |
|---|---|---|
| `ship` | "Which ship are you in — Prospector, Golem, or MOLE?" | Must ask |
| `laser` | "What mining laser are you running?" | Offer list (Step 2a) |
| `modules` | "What modules do you have installed, if any?" | None — continue without |
| `rock_material` | "What material are you targeting, or what's the hardest element in the rock?" | Must ask for crackability |
| `rock_mass` | "What's the rock mass? (Check your ship's scanner)" | 3000 (small), 8000 (medium), 20000 (large) |
| `gadgets` | "Are you using any gadgets?" | No — never assume gadget use |

**If laser is unknown:** Jump to Step 2a before asking about modules.

---

## Step 2a — List available equipment (when user doesn't know their loadout)

```bash
python3 scripts/query/mining_solver.py --ship <ship> --list-equipment
```

**Output keys:**

| Key | Use |
|---|---|
| `ship.note` | Surface — explains fixed-laser constraint for Golem |
| `available_lasers[].name` | Present as options |
| `available_lasers[].module_slots` | Note how many module slots each has |
| `available_lasers[].modifiers` | Key stats to compare (instability, window, resistance) |
| `passive_modules[]` | List for user to pick from |
| `active_modules[]` | List — note charges are limited |
| `gadgets[]` | List — but ask before recommending (not all players carry them) |

Present lasers as a table: Name | Slots | Instab mod | Window mod | Resist mod

---

## Step 2b — Recommend a loadout (when user asks "what should I use?")

```bash
python3 scripts/query/mining_solver.py \
  --ship <ship> \
  --rock-material "<material>" \
  --recommend
```

**Output keys:**

| Key | Use |
|---|---|
| `recommended_laser.name` | State as recommendation |
| `recommended_laser.module_slots` | How many modules can be added |
| `recommended_modules[].name` | Module recommendation |
| `recommended_modules[].type` | Passive (always active) or active (limited charges) |
| `recommended_modules[].charges` | For active modules — mention charge count |
| `rationale[]` | Surface all rationale bullets to the user |

---

## Step 3 — Compute net stats for a specific loadout

```bash
python3 scripts/query/mining_solver.py \
  --ship <ship> \
  --laser "<laser name>" \
  --modules "<module1>" "<module2>" \
  --rock-mass <mass> \
  --rock-material "<material>"
```

**Output keys:**

| Key | Use |
|---|---|
| `net_stats.instability` | Net instability after all modifiers |
| `net_stats.resistance` | Net resistance after all modifiers |
| `net_stats.window_size_pct` | Green zone width as % of rock capacity |
| `net_stats.window_min_pct` | Green zone start |
| `net_stats.window_max_pct` | Green zone end |
| `net_stats.effective_dps` | Laser output DPS |
| `net_stats.difficulty` | `easy` \| `moderate` \| `hard` \| `very hard` |
| `net_stats.crackable` | Boolean |
| `net_stats.assessment[]` | Surface all — explains why difficulty rating |
| `warnings[]` | Surface any — module slot overages, missing equipment |
| `tips[]` | Surface all — practical in-game advice |

If math detail is needed (e.g., user asks "why is the window so narrow?"), load `math.md`.

---

## Step 4 — Present results

Load `output_formats.md` for the exact table format.

Always state:
> "These stats use [material] as the rock element. Real rocks are mixed compositions — your actual stats will vary. The SCMDB solver at scmdb.net/?page=solver gives exact numbers for a specific rock composition."

---

## Branching rules

**Golem:** Fixed Pitman laser — skip laser selection, go straight to module selection.
> "The Golem runs a fixed Pitman Mining Laser — only modules are configurable."

**MOLE multi-crew:** Each laser operates independently. Ask:
> "How many operators are running lasers — 1, 2, or 3?"
Then run the solver per-laser, not combined. Combined DPS = n × single laser DPS.

**Rock mass unknown:** Use the qualitative defaults (small/medium/large) and note the assumption.
> "I'm using medium rock mass (8,000 kg) as a baseline. Your actual crack time will scale with rock mass."

**Material not found:**
> "I don't have '[material]' in my mining data. Could you check the exact spelling? Common ones: Ouratite, Borase, Tungsten, Bexalite, Laranite, Quantainium."

**Gadgets:** Never recommend gadgets without asking first.
> "Gadgets like OptiMax or Waveshift can significantly ease the crack. Do you carry gadgets? (If yes, I can factor them in.)"
