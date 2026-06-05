# Mining Solver — Output Formats

Load this file when formatting a final loadout recommendation or stats summary for the user.

---

## Loadout summary (compute mode)

```
[Data: patch X.X.X] — Stats use [material] as primary element (worst-case).

Ship: Prospector   Laser: Arbor MH1 Mining Laser (1 module slot)
Modules: Lifeline Module (active, 3 charges)
Rock: Ouratite | Mass: 8,000 kg

NET STATS
  Instability:   390  (moderate — manageable with steady throttle)
  Resistance:   0.75  (elevated — charge builds slowly)
  Window:       10.1% wide  |  Position: 35–45% charge
  Effective DPS: 1,890

DIFFICULTY: Moderate ⚠
  • Net instability 390 — active Lifeline module will help stabilize
  • Resistance 0.75 — don't rush; steady input beats bursts

TIPS
  • Keep throttle in the green zone (35–45% charge indicator)
  • Activate Lifeline when charge starts oscillating out of control
  • If overcharge is imminent, cut throttle completely — don't try to back off gradually

Real rocks are mixed compositions. These stats use pure Ouratite (worst case).
For exact values on a specific rock: scmdb.net/?page=solver
```

---

## Recommendation format (recommend mode)

```
[Data: patch X.X.X] — Recommended Prospector loadout for Ouratite mining:

LASER:  Arbor MH1 Mining Laser
  → Best instability reduction (-35%) for this rock type
  → 1 module slot available

MODULE: Lifeline Module  (active, 3 charges per use)
  → Instability -20% when activated — use when charge starts bouncing

WHY:
  Ouratite has high instability (600) and moderate resistance (0.6).
  The Arbor MH1 handles instability best among S1 lasers.
  Lifeline as the active module provides a safety net for instability spikes.

GADGETS: Not included. Ask me if you carry gadgets — they can further ease the crack.
```

---

## Equipment list format (list mode)

When presenting available equipment for a ship, use this table layout:

```
PROSPECTOR — S1 Lasers (1 slot each unless noted)

Laser                    | Slots | Instab | Window | Resist | DPS
─────────────────────────────────────────────────────────────────
Arbor MH1 Mining Laser   |   1   |  -35%  |  +40%  |  +25%  | 1,890
Lancet MH1 Mining Laser  |   1   |  -10%  |  -60%  |   0%   | 2,520
Helix I Mining Laser     |   2   |    0%  |  -40%  |  -30%  | 3,150
Hofstede-S1              |   1   |  +10%  |  +60%  |  -30%  | 2,100
Klein-S1 Mining Laser    |   0   |  +35%  |  +20%  |  -45%  | 2,520
Pitman Mining Laser      |   2   |  +35%  |  +40%  |  +25%  | 3,150
Impact I Mining Laser    |   2   |  -10%  |  +20%  |  +10%  | 2,100

Negative values = helps (reduces instability/resistance, or rare for window)
Positive values = hurts instability/resistance; widens window (positive window = bigger green zone)
```

Passive modules table:
```
PASSIVE MODULES (always active while installed)

Module           | Instab | Window  | Resist
─────────────────────────────────────────────
Focus Module     |    0%  |  +30%   |   0%
Focus II Module  |    0%  |  +37%   |   0%
Focus III Module |    0%  |  +40%   |   0%
XTR Module       |    0%  |  +15%   |   0%
XTR-L Module     |    0%  |  +22%   |   0%
XTR-XL Module    |    0%  |  +25%   |   0%
Rieger Module    |    0%  |  -10%   |   0%  ← avoids overcharge (advanced use)
Vaux Module      |    0%  |    0%   |   0%  ← extraction speed buff only
FLTR Module      |    0%  |    0%   |   0%  ← filter buff only
```

Active modules table:
```
ACTIVE MODULES (limited charges — activate during mining)

Module           | Charges | Instab | Resist | Notes
──────────────────────────────────────────────────────────────────
Lifeline Module  |    3    |  -20%  |  -15%  | Best for hard rocks
Surge Module     |    7    |  +10%  |  -16%  | Resistance + more charges
Rime Module      |   10    |    0%  |  -25%  | Pure resistance reduction
Optimum Module   |    5    |  -10%  |    0%  | Mild instability control
Brandt Module    |    5    |    0%  |  +16%  | Increases resistance — avoid for hard rocks
Stampede Module  |    6    |  -10%  |    0%  | Similar to Optimum
```

---

## Difficulty badge

Always include a difficulty badge in summaries:

| Rating | Meaning | Typical action |
|---|---|---|
| Easy | Instab < 200, Resistance < 0.4, Window > 12% | Stock laser, no modules needed |
| Moderate | Instab 200–400 or Resistance 0.4–0.6 | One module recommended |
| Hard | Instab 400–700 or Resistance 0.6–0.8 | Best laser + 1-2 modules + potentially gadget |
| Very Hard | Instab > 700 or Resistance > 0.8 or Window < 4% | Requires optimal loadout; consider gadget; may be beyond solo Prospector |
