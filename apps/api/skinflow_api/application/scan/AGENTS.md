# Scan Module

Read the root `AGENTS.md` and `docs/architecture/module-boundaries.md` first.

Own candidate sources, market snapshots, scan filters, scan jobs, SSE events,
and the Scan Web feature. Allowed paths are this directory, the BUFF/CSQAQ/
悠悠平台 adapters, `market_detail.py`, `market_gateway.py`, `routes/scan.py`,
the Scan/platform parser tests, and `apps/web/src/features/scan/`.

Do not edit Steam inventory/listing/session code, other modules, shared Web
files, route registration, or root configuration without a coordinator
contract request. Run focused tests plus Ruff and the Web checks relevant to
your change. Use `feat(scan): ...` or `fix(scan): ...`; do not merge.
