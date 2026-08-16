# Ledger Module

Read the root `AGENTS.md` and `docs/architecture/module-boundaries.md` first.

Own FIFO holdings, buy/sell records, sale fills, pending purchases, and the
Holdings Web feature. Allowed paths are this directory,
`infrastructure/database/ledger.py`, `routes/ledger.py`, ledger tests, and
`apps/web/src/features/holdings/`.

Do not change inventory synchronization, listing state, pricing/domain rules,
shared Web files, route registration, or root configuration without a
coordinator contract request. Run the full Python tests for data changes. Use
`feat(ledger): ...` or `fix(ledger): ...`; do not merge.
