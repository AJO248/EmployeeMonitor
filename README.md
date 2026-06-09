# Employee Monitor (CPAM) — Phase 1 scaffold

Lightweight prototype for the C++ & Python Activity Monitor (CPAM). This repository contains a minimal Windows native agent skeleton, a Chrome/Chromium extension companion, and a small FastAPI ingestion endpoint to receive logs.

**Status:** Phase 1 scaffolding — capture + local cache + ingestion stub.

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

1. Start the backend (`backend/app/main.py`) to accept HTTP ingestion (future flush).
2. Start `native-agent.exe` on a Windows VM or machine.
3. Load the extension in Chrome and switch tabs. Observe:
   - `native-agent` console logs for foreground changes.
   - `cpam_cache.db` contains rows inserted from extension frames.
   - (Backend) When implemented, the agent will flush cached events to `/api/v1/logs`.

Notes & next steps

- The Phase 1 code is intentionally minimal and focused on prototyping capture and local storage. It is not production hardened.
- TODOs: encrypted on-disk cache, robust WebSocket library integration, batched flush to FastAPI with retry/backoff, authentication, and analytics aggregation.

Contributions

- Open issues or create pull requests for improvements. For major changes, open an issue first to discuss the design.

License

- No license specified (add one if you intend to open-source this project).
