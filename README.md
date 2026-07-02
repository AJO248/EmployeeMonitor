# Employee Monitor (EM)

EmployeeMonitor is a secure, lightweight activity tracking system. It provides comprehensive activity monitoring by tracking active windows, user idle states, and active browser tabs, whilst offering a secure backend for data ingestion and a web-based dashboard for reviewing logs.

## System Architecture

The project consists of four tightly-integrated components:

1. **Native Agent (C++)**: Runs on the Windows client machine to monitor foreground window changes, idle status, and host a local WebSocket server for the browser extension. It locally caches and securely encrypts data (using Windows DPAPI) before batch-transmitting logs to the ingestion server.
2. **Browser Companion (Chrome/Edge Extension)**: A lightweight browser extension that monitors active tabs and securely relays the current URL/title to the native agent via a local WebSocket connection (`ws://127.0.0.1:8585`).
3. **Ingestion Server (FastAPI)**: A Python-based backend that securely receives batched activity logs, validates them using Pydantic, and persists them into a relational database using SQLAlchemy (SQLite/PostgreSQL support).
4. **Admin Dashboard (HTML/JS/CSS)**: A clean, vanilla web interface for administrators to review activity logs, analyze device status, and check usage analytics. Served automatically by the FastAPI backend.

## Security & Data Protection

- **Local Encryption (DPAPI)**: The agent caches logs locally in a SQLite database (`cpam_cache.db`). The data is encrypted at rest using the Windows Data Protection API (DPAPI). Only the user account that created the data can decrypt it.
- **Secure Ingestion**: Log uploads to the backend require a Bearer token (`EM_INGEST_TOKEN`) to prevent unauthorized log injection.
- **Admin Authentication**: The admin dashboard uses secure bcrypt password hashing and issues HTTP-only JWT cookies to maintain authenticated sessions securely.

---

## Setup & Installation Guide

### 1. Backend Server & Admin Dashboard

The backend is built with FastAPI and serves the admin dashboard statically.

**Prerequisites**:
- Python 3.9+

**Installation**:
```bash
# Clone the repository and enter the directory
cd EmployeeMonitor

# Create and activate a Python virtual environment
python -m venv .venv
.venv\Scripts\activate  # On Windows

# Install the backend requirements
python -m pip install -r backend/requirements.txt

# Configure Environment Variables
cp .env.example .env
# Edit .env and set your secrets, e.g., EM_INGEST_TOKEN, EM_ADMIN_PASSWORD
```

**Running the Server**:
```bash
# Start the Uvicorn server (automatically mounts the admin-frontend)
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
The ingestion API will run on `http://127.0.0.1:8000`.
The Admin Dashboard will be accessible at `http://127.0.0.1:8000/admin/`.

### 2. Native Windows Agent

The Native Agent monitors local activity and relays data to the backend.

**Prerequisites**:
- Windows OS
- CMake 3.10+
- A C++17 capable toolchain (e.g., Visual Studio Build Tools, MSVC)

**Building**:
```powershell
# Navigate to the native-agent directory
cd native-agent

# Run the provided PowerShell build script
.\build.ps1
```

**Running**:
After a successful build, the executable will be located in the `build/Release` folder:
```powershell
.\build\Release\native-agent.exe
```
*Note: Make sure the backend server is running and accessible so the agent can upload logs.*

### 3. Browser Companion Extension

The browser extension tracks active URLs and sends them to the native agent's WebSocket server.

**Installation (Chrome/Edge)**:
1. Open your browser and navigate to `chrome://extensions/` (or `edge://extensions/`).
2. Turn on **Developer mode** (usually a toggle in the top right corner).
3. Click **Load unpacked** and select the `browser-extension` folder from this repository.
4. The extension will automatically activate and attempt to connect to the native agent at `ws://127.0.0.1:8585`.

---

## Configuration

The project uses a `.env` file for centralized configuration. Ensure this file is present in the root directory before running the backend. Important variables include:
- `EM_INGEST_TOKEN`: The token used by the Native Agent to authorize log uploads.
- `EM_ADMIN_PASSWORD`: The password for the admin dashboard.
- Database connection strings and JWT secrets.

## Testing & Verification

1. **Verify Backend**: Navigate to `http://127.0.0.1:8000/health` to confirm the API is online.
2. **Access Dashboard**: Open `http://127.0.0.1:8000/admin/` and log in with your credentials.
3. **Verify Agent Integration**: Run the Native Agent, browse a few websites with the extension enabled, and verify that new logs populate in the Admin Dashboard.
