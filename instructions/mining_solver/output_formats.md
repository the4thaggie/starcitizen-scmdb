# Mining Solver — Output Formats

Load this file when formatting a final loadout recommendation or stats summary.

## Loadout summary card
<!-- TODO: define format after first solver scrape confirms stat field names -->
Fields to include: ship, laser(s), modules per laser, gadgets (if any), net stats block.

## Stats block
Fields from the SCMDB Stats panel (bottom-left of solver UI):
<!-- TODO: enumerate all stat fields and their units after scrape -->

## Rock breakability report
<!-- TODO: define format: rock params in → can break? → recommended power setting -->

## Yield estimate
<!-- TODO: define format: composition + mass → expected material output by type -->

## Archetype-specific formats
- Ship mining: full loadout card + stats block
- ROC/Geo: simplified — vehicle + attachment + relevant stats
- Hand mining: tool + attachment + relevant stats
