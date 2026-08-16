# Listings Module

Read the root `AGENTS.md` and `docs/architecture/module-boundaries.md` first.

Own listing previews, submission, status polling, reconciliation, Steam
listing adapters, and the Listings Web feature. Allowed paths are this
directory, `infrastructure/database/listing.py`, Steam listing adapters,
`routes/listing.py`, listing tests, and `apps/web/src/features/listings/`.

Inventory page and asset grouping remain owned by Inventory. Coordinate before
changing `ListingPreviewDialog`, shared API clients, route registration, or
Ledger rules. Run focused tests plus Ruff and the Web checks relevant to your
change. Use `feat(listings): ...` or `fix(listings): ...`; do not merge.
