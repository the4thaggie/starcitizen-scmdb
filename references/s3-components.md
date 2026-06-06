# S3 Component Blueprint Reference (Patch 4.8.1)

Reference for Large ships (Constellation, Cutter, Merchantman, etc.) with S3 component slots.

## Quantum Drives (S3)

| Component | Grade | Class | Speed (Mm/s) | Fuel/jump | Faction | Unlock Tier | Rep | Pool Size |
|-----------|-------|-------|--------------|---------|---------|-------------|-----|-----------|
| TS-2 | A | Military | 395 | 0.142 | Covalex | Master | 237,750 | 9 |
| Agni | B | Industrial | 383 | 0.036 | FTL Courier | Jr. Contractor | 800 | 6 |
| Balandin | B | Military | 339 | 0.135 | Covalex | Master | 237,750 | 9 |
| Pontes | C | Military | 282 | 0.122 | None | N/A | N/A | Buy only |
| Erebos | A | Civilian | 344 | 0.050 | None | N/A | N/A | Buy only |
| Kama | C | Industrial | 319 | 0.039 | None | N/A | N/A | Buy only |

## Power Plants (S3)

_(Data sourced from crafting_blueprints.json)_

## Shields (S3)

_(Data sourced from crafting_blueprints.json)_

## Coolers (S3)

_(Data sourced from crafting_blueprints.json)_

## Faction Tier Ladders

### Covalex (11 tiers)
Trainee(0) → Neutral(0) → Rookie(50) → Junior(250) → Jr. Contractor(800) → Contractor(2,200) → Member(5,250) → Sr. Contractor(5,800) → Experienced(27,750) → Senior(77,750) → Master(237,750)

### FTL Courier (6 tiers)
Neutral(0) → Jr. Contractor(800) → Head Contractor(38,000) → Veteran Contractor(15,000) → Contractor(2,200) → Sr. Contractor(5,800)

---

## Grind Recommendations for S3

**Easiest S3 Quantum Drive grind:**
- **Agni (Industrial)** — FTL Courier Jr. Contractor (800 rep), 6-pool. Best option if you accept Industrial class.
- Trade-off: 12 Mm/s slower than TS-2, but significantly better fuel efficiency (0.036 vs 0.142)

**S3 Military (same tier):**
- **TS-2 vs Balandin** — Both require Covalex Master (237,750 rep), 9-pool drop. TS-2 is faster but same grind.

**Buy-only options:**
- **Pontes** — S3 Military, no grind, cheapest path. Grade C, 282 Mm/s.
- **Erebos** — S3 Civilian, no grind. Grade A, 344 Mm/s.

---

## Size Matching Rules

When querying blueprints:
- **Always specify `--size N`** to filter by component slot size
- **Verify component class matches ship role:**
  - Military — combat ships (Vanguard, Hornet, etc.)
  - Industrial — mining/hauling ships (Prospector, MOLE, Caterpillar)
  - Civilian — general purpose ships (Constellation, Freelancer)
  - Stealth — stealth-capable ships (Sabre, etc.)

_This file is auto-generated from SCMDB data. Last updated: patch 4.8.1-live.11875683_