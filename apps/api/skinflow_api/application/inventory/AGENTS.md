# Inventory Module

Read the root `AGENTS.md` and `docs/architecture/module-boundaries.md` first.

Own inventory synchronization, grouping, asset selection, and the Inventory
Web feature. Allowed paths are this directory, `infrastructure/database/inventory.py`,
`infrastructure/platforms/steam/inventory.py`, `apps/api/tests/test_inventory*.py`,
and `apps/web/src/features/inventory/`.

Do not edit Scan, Listings, Ledger, Settings/Auth, domain rules, shared Web
files, route registration, or root configuration without a coordinator
contract request. Run focused tests plus Ruff and the Web checks relevant to
your change. Use `feat(inventory): ...` or `fix(inventory): ...`; do not merge.
