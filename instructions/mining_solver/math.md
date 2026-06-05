# Mining Solver — Math Reference

> [Design Doc §10](../../DesignDoc.md#10-subskill-mining-solver) · back to: [index.md](index.md)

Load this file when the user asks *why* a stat is what it is, or needs to understand the
underlying mechanics (e.g., "why is my window so narrow?", "what does instability actually do?").

---

## How modifiers stack

All laser and module modifiers are **additive** with each other, then applied as a
**percentage** to the rock's base value.

```
net_instability  = rock.instability  × (1 + Σ instability_pct  / 100)
net_resistance   = rock.resistance   × (1 + Σ resistance_pct   / 100)
```

Example — Arbor MH1 (-35% instab) on an Ouratite rock (instability 600):
```
net_instability = 600 × (1 + (-35) / 100) = 600 × 0.65 = 390
```

A negative total modifier reduces the stat (good for instability, good for resistance).
A positive total modifier increases the stat (bad for instability/resistance, good for window size).

---

## Optimal charge window (the green zone)

The green zone is where you must keep the rock's charge to fracture it without overcharging.

**Base window size** (ship mining):
```
base_window = globalParams.ship.optimalWindowSize      # 0.10 = 10% of rock capacity
            × globalParams.ship.optimalWindowFactor    # 0.75
            = 0.075  (7.5%)
```

**After rock thinness** (some rocks have a narrower natural window):
```
thinness_factor = globalParams.ship.optimalWindowThinnessCurveFactor  # 0.7
window_after_thinness = base_window / (1 + rock.optimalWindowThinness × thinness_factor × 0.1)
```

`optimalWindowThinness` values:
- 0 or negative → window is not narrowed (or widened)
- 1–2 → moderate narrowing
- 3+ → significantly narrow window

**After laser + module modifiers:**
```
net_window = window_after_thinness × (1 + Σ opt_window_size_pct / 100)
net_window = min(net_window, globalParams.ship.optimalWindowMaxSize)  # cap at 0.50 = 50%
```

**Window position** (where on the 0–100% charge scale the green zone sits):
```
midpoint = rock.optimalWindowMidpoint  # e.g., 0.40 for Ouratite, 0.50 for Agricium
window_min = (midpoint - net_window / 2) × 100  %
window_max = (midpoint + net_window / 2) × 100  %
```

---

## What instability actually does in-game

Instability makes the charge level **oscillate** while you hold the laser on the rock.
High instability = the charge bounces up and down within (and sometimes outside) the window.

- **Low instability (0–100):** Charge stays almost where you put it. Easy to hold in window.
- **Moderate (100–300):** Noticeable oscillation. Requires active throttle adjustments.
- **High (300–500):** Rapid oscillation. Active modules (Surge, Lifeline) become necessary.
- **Very high (500+):** Near-uncontrollable without active modules. Bursting recommended.

Instability modifiers from lasers/modules are applied *before* the charge simulation.
The rock's `instabilityWavePeriod` (3s) and `instabilityWaveVariance` (1s) control timing.

---

## What resistance actually does

Resistance slows the rate at which the rock's charge builds when the laser is on it.

- **Negative resistance** (e.g., -0.4 for Tungsten): Rock charges *faster* than baseline — use low power.
- **Zero resistance:** Neutral charge rate.
- **Positive resistance** (e.g., 0.6 for Ouratite): Rock charges *slower* — requires patient sustained input.
- **Very high resistance** (> 0.8 net): May barely build charge with some lasers.

The `resistanceCurveFactor` (0.6 for ship) shapes how resistance scales non-linearly.

---

## Rock capacity and charge time

```
power_capacity = rock_mass × globalParams.ship.powerCapacityPerMass  # 10.0
               = e.g., 8000 × 10 = 80,000

decay_rate = rock_mass × globalParams.ship.decayPerMass  # 0.2
           = 8000 × 0.2 = 1,600 per second (when laser is off)
```

The laser must build charge to `power_capacity` while keeping it in the green zone.
Net effective charge rate = laser.DPS × (1 - net_resistance) — reduced by resistance.

---

## Quick reference: modifier signs

| Want to... | Look for modifier with... |
|---|---|
| Reduce instability | `instability_pct` < 0 |
| Reduce resistance | `resistance_pct` < 0 |
| Widen the green zone | `opt_window_size_pct` > 0 |
| Narrows the green zone | `opt_window_size_pct` < 0 (avoid for hard rocks) |

Active modules apply for `charges` uses then are depleted. Passive modules are always on.
Module slot count per laser = `laser.module_slots` — check before recommending a combo.
