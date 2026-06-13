# Employee Monitor (CPAM) — Secure analytics prototype

Lightweight prototype for the C++ & Python Activity Monitor (CPAM). This repository contains a minimal Windows native agent skeleton, a Chrome/Chromium extension companion, and a small FastAPI ingestion endpoint to receive logs.

**Status:** Phases 1–3 have working prototype paths; the Phase 4 admin dashboard has started.

## Current Status (2026-06-14)

- Phase 1 implemented (prototype): native Windows foreground capture, local WebSocket loopback, SQLite cache, and Chrome extension.
- Phase 2 implemented (development prototype): protected async FastAPI ingestion, SQLAlchemy persistence, Alembic baseline, domain normalization, and native-agent batched HTTP upload with retry/backoff.
- Phase 3 started: bcrypt admin credentials, JWT authentication, HTTP-only admin cookie, ingestion rate limiting, idle events, and recent-usage aggregation.
- Phase 4 started: vanilla JavaScript dashboard at `/admin/` showing Active/Idle/Offline device status, active/idle time, and leading applications/domains.
- Remaining production work: PostgreSQL validation, TLS deployment, distributed rate limiting, robust interval/session modeling, and dashboard expansion.
- Tools: PowerShell build helper and a Python `tools/view_cache.py` viewer showing pending/delivered cache events and upload attempts.

## What it can do right now

- Capture foreground window changes via Win32 APIs (`GetForegroundWindow`, `GetWindowTextW`).
- Host a minimal WebSocket server on `ws://127.0.0.1:8585` and accept JSON text frames from the browser extension.
- Protect newly cached foreground-window, browser-tab, idle-transition, and heartbeat events with machine-bound Windows DPAPI in local SQLite.
- Batch pending cache events to protected FastAPI `/api/v1/logs`, mark successful deliveries, and retry failures with exponential backoff.
- Receive and persist event batches using async FastAPI and SQLAlchemy (development DB default: `backend/dev.db`).
- Normalize URLs to base domains using `backend/app/utils/normalizer.py` during ingestion.
- Sign administrators in with bcrypt-verified credentials and an HTTP-only JWT cookie.
- Summarize recent active, idle, application, and domain usage in the admin dashboard.
- Inspect cached events with `tools/view_cache.py`.

## Quick verification (dev)

Start the backend (dev SQLite by default):

```bash
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
python backend/app/main.py
# or: uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Build and run the native agent on Windows (PowerShell helper included):

```powershell
cd native-agent
./build.ps1  # run in PowerShell with an appropriate CMake generator
# then run the produced native-agent executable (e.g. build\Release\native-agent.exe)
```

Load the Chrome extension (unpacked):

1. Open Chrome/Edge → Extensions → Developer mode → Load unpacked.
2. Select the `browser-extension` directory.
3. Switch tabs in the browser; the extension will try to send `tab_activated`/`tab_updated` events to `ws://127.0.0.1:8585`.

Inspect the local cache:

```bash
python tools/view_cache.py --db cpam_cache.db --limit 50
```

Set the same `CPAM_INGEST_TOKEN` for the backend and native agent. The agent sends to `http://127.0.0.1:8000/api/v1/logs` by default; override it with `CPAM_BACKEND_URL`. The backend creates tables on startup for development and persists events to `backend/dev.db` or the async SQLAlchemy `DATABASE_URL` you configure.

The development admin defaults are `admin` / `change-me`. Change `CPAM_ADMIN_PASSWORD`, `CPAM_JWT_SECRET`, and `CPAM_INGEST_TOKEN` before using the project beyond local development.

Apply migrations when `CPAM_CREATE_TABLES=false`:

```bash
alembic upgrade head
```

## Files of interest

- [native-agent/src/main.cpp](native-agent/src/main.cpp) — Win32 polling, WebSocket server, and SQLite cache insertion.
- [native-agent/build.ps1](native-agent/build.ps1) — PowerShell helper to configure and build the agent on Windows.
- [browser-extension/manifest.json](browser-extension/manifest.json) and [browser-extension/background.js](browser-extension/background.js) — extension files that send tab events to the loopback WS.
- [backend/app/main.py](backend/app/main.py) — FastAPI app entrypoint (mounts `/api/v1/logs`).
- [backend/app/models.py](backend/app/models.py) and [backend/app/crud.py](backend/app/crud.py) — async SQLAlchemy model and bulk insert helper.
- [backend/app/utils/normalizer.py](backend/app/utils/normalizer.py) — domain extractor.
- [tools/view_cache.py](tools/view_cache.py) — inspect `cpam_cache.db`.

## Next steps (prioritized)

1. Validate migrations and ingestion against PostgreSQL.
2. Replace in-memory rate limiting with a shared production store.
3. Add durable device enrollment and token rotation.
4. Improve interval/session modeling and productivity classification rules.
5. Expand the dashboard with device status, charts, filters, and classification controls.

**Repository layout**

- [native-agent/CMakeLists.txt](native-agent/CMakeLists.txt) — CMake project for the Win32 native agent.
- [native-agent/src/main.cpp](native-agent/src/main.cpp) — foreground polling, simple WebSocket loopback server, SQLite cache.
- [browser-extension/manifest.json](browser-extension/manifest.json) — Chrome MV3 manifest.
- [browser-extension/background.js](browser-extension/background.js) — service worker that sends active-tab events to the loopback WebSocket.
- [backend/requirements.txt](backend/requirements.txt) — Python dependencies for the FastAPI scaffold.
- [backend/app/main.py](backend/app/main.py) — minimal FastAPI ingestion endpoint `/api/v1/logs`.

Prerequisites

- Windows (for the native agent build and Win32 APIs).
- CMake (>= 3.10) and a C++17-capable toolchain (Visual Studio / MinGW).
- Python 3.9+ and `pip` for the backend.

Quick start — Backend

1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
python -m pip install -r backend/requirements.txt
```

2. Run the FastAPI app (development):

```bash
python backend/app/main.py
# or: uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Native agent — Build & run (Windows)

1. Open a developer command prompt or PowerShell with a CMake-capable toolchain.
2. From the `native-agent` folder, configure and build:

```powershell
cd native-agent
cmake -S . -B build -G "Visual Studio 17 2022"    # choose generator for your toolchain
cmake --build build --config Release
# (or use a MinGW/Clang generator appropriate to your setup)
```

3. Run the produced executable (e.g., `build/Release/native-agent.exe`). The agent will:

- Poll the active window using Win32 APIs and print foreground changes.
- Host a loopback WebSocket server on `ws://127.0.0.1:8585` to accept frames from the browser extension.
- Persist received JSON frames into the local SQLite file `cpam_cache.db`.

Chrome extension — load unpacked

1. Open Chrome/Edge → Extensions → Developer mode → Load unpacked.
2. Select the `browser-extension` directory from this repo.
3. The extension will attempt to connect to `ws://127.0.0.1:8585` and send `tab_activated` / `tab_updated` events when tabs change.

End-to-end test (dev)

1. Start the backend (`backend/app/main.py`) to accept HTTP ingestion.
2. Start `native-agent.exe` on a Windows VM or machine.
3. Load the extension in Chrome and switch tabs. Observe:
   - `native-agent` console logs for foreground changes.
   - `cpam_cache.db` contains rows inserted from extension frames.
   - Successfully uploaded cache rows show a delivery timestamp in `tools/view_cache.py`.
   - The backend `log_entries` table contains normalized, persisted events.
