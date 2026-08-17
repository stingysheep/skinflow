# Skinflow

Skinflow is a Windows-first, local CS2 semi-automatic trading workspace. It
helps one operator scan public market data, synchronize Steam inventory, build
listing previews, track listing reconciliation, and maintain a local FIFO
holdings ledger.

Skinflow is an operator tool, not an automated trading bot. Listing submission
always requires an explicit user action, and Steam mobile confirmations remain
manual.

## Capabilities

| Area | What it does | Steam session required |
| --- | --- | --- |
| Scan | Collects public BUFF, Steam, CSQAQ, and Youpin market data; applies filters and streams progress. | No |
| Inventory | Synchronizes individual Steam assets, trade availability, and grouped inventory. | Yes |
| Listings | Creates previews, submits selected items in the background, reconciles active/pending/cancelled states, and supports batch cancellation. | Yes |
| Holdings | Records purchases and sales with FIFO accounting, plus local maintenance of open holdings. | No |
| Desktop shell | Hosts the local API and WebView2 interface, handles local startup authentication, and remembers window size. | Required for Steam login |

## Requirements

- Windows 10/11 with Microsoft Edge WebView2 Runtime for desktop use
- Python 3.13
- Node.js 24
- npm 11

## Install

Clone the repository, then install the Python development dependencies and the
Web workspace dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm ci
```

Install the optional desktop dependency when you need Steam login or the
desktop shell:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
```

## Run In Browser Development Mode

Use two PowerShell windows from the repository root.

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn skinflow_api.main:app --app-dir apps/api --host 127.0.0.1 --port 58150
```

Start the Web client:

```powershell
npm run dev:web
```

Open the Vite URL printed by npm, normally
`http://127.0.0.1:5173`. The API health endpoint is
`http://127.0.0.1:58150/api/health` and the API documentation is
`http://127.0.0.1:58150/api/docs`.

Browser development mode supports public market scanning, but deliberately
does not open Steam login. Use the desktop shell for Steam inventory and
listing operations.

## Run The Desktop Shell

Build the Web application, then start the desktop entry point:

```powershell
npm run build
.\.venv\Scripts\python.exe apps/desktop/launch.py
```

The desktop shell starts its own loopback-only API server and opens a WebView2
window. It uses a fresh local startup token for each launch, so Vite and a
separate Uvicorn process are not needed in this mode.

## Typical Workflow

1. Use **Scan** to inspect public market opportunities.
2. Start the desktop shell and sign in through the official Steam login window.
3. Refresh **Inventory** and select tradable assets.
4. Create and explicitly confirm a listing preview.
5. Watch the background submission progress and complete any Steam mobile
   confirmation yourself.
6. Use **Listings** to reconcile real Steam states, retry pending work, or
   cancel eligible listings.
7. Use **Holdings** to record purchases and actual sales. A submitted listing
   is not treated as a completed sale.

## Local Data And Privacy

- Local databases, logs, caches, build output, `.env` files, and `data/` are
  ignored by Git and must not be committed.
- In normal desktop mode, the Steam session file is stored locally as
  `data/steam_session.bin`, encrypted with Windows DPAPI for the current
  Windows user. Clearing the Steam session removes it. Development tests use
  an in-memory session.
- Steam credentials are never sent to this repository. Do not attach your
  local `data/` directory, log files, or screenshots containing account data
  to issues or releases.
- `SKINFLOW_CSQAQ_API_TOKEN` can be supplied through the user environment or a
  local `.env`; neither belongs in Git.
- Steam mobile confirmations are never performed automatically by Skinflow.

## Import A Legacy Ledger

The migration is idempotent and records the source SHA-256 plus migration
version. Run it once with explicit source and destination paths:

```powershell
.\.venv\Scripts\python.exe apps/api/scripts/migrate_legacy_ledger.py <legacy-ledger.db> data\skinflow.db
```

## Verify

Run the complete local check suite before integrating a module or creating a
release:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check apps
npm run test
npm run typecheck
npm run lint
npm run build
```

## Development Boundaries

Skinflow is developed by capability. Read [AGENTS.md](AGENTS.md) and
[docs/architecture/module-boundaries.md](docs/architecture/module-boundaries.md)
before making changes. Keep Inventory, Scan, Listings, Ledger, and
Settings/Auth work isolated; send shared API, routing, configuration, and
component contract changes through the coordinator.
