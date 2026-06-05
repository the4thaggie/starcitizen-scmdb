# Mining Solver — Math

Load this file when the user needs actual calculations: breakability windows, instability, power curves, or yield estimates.

## Rock parameters
- **Rock Mass** — integer, affects energy required to fracture
- **Composition** — material mix affecting total yield value
- **Resistance** — derived from rock type; affects how much laser power is needed

## Laser power and the green zone
<!-- TODO: define the power window (min/max laser power), green zone calculation, overcharge behavior -->

## Module stat stacking rules
<!-- TODO: define additive vs. multiplicative stacking for passive modules -->

## Breakability check
<!-- TODO: define formula: can this loadout crack this rock? -->

## Instability and charge rate
<!-- TODO: define instability growth rate, active module effects on charge curve -->

## Yield calculation
<!-- TODO: define material extraction formula from composition + mass -->

## Multi-laser Mole considerations
<!-- TODO: combined power from multiple operators, green zone adjustment -->

## Safety rules for this section
- Do not invent constants not present in `data/mining/equipment.json` or `data/mining/<version>.json`.
- If a formula input is missing from cached data, state the gap explicitly rather than estimating.
