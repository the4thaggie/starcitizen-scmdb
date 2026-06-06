# Mission linking and exact identity

Use this when a Star Citizen mission needs to be identified, compared, or linked.

## Rules

- Treat SCMDB JSON `id` as the authoritative mission identifier.
- Mission titles are **not globally unique**; the same title can exist in multiple systems or variants.
- Use `scripts/query/mission_lookup.py` first for exact identity checks.
- Prefer exact lookup by `--id` or `--debug-name`.
- Use `--title` only for exact-title confirmation, and always inspect the returned `systems` field.
- Do **not** infer a mission page URL from title/snippet alone.
- Only attach a URL if the exact `id` ↔ URL mapping has been verified from deterministic data.

## Practical workflow

1. Run `mission_lookup.py` with the strongest identifier available.
2. If the lookup returns multiple matches, compare `systems`, `debug_name`, and prerequisites.
3. If the answer is being presented to the user, include at least:
   - `id`
   - `title`
   - `systems`
   - `debug_name` when helpful
4. If a page link cannot be verified deterministically, return the exact record info without a link.

## Example pitfall

A title like `Large Covalex Shipment Needs Recovering` can exist as separate Stanton, Nyx, and Pyro variants. The title alone is not enough to select the correct page.