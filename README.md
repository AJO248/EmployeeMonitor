# Employee Monitor (CPAM)

CPAM (C++ & Python Activity Monitor) is a secure, lightweight activity tracking system. It includes a native Windows agent, a Python fallback agent, a browser companion extension, a FastAPI ingestion server, and a web-based administration dashboard.

## System Architecture

CPAM consists of four main components:
1. **Native Agent (C++ & Python)**: Runs on the client machine to monitor foreground window changes and idle status. It batches and securely transmits logs.
2. **Browser Companion (Chrome Extension)**: Monitors active browser tabs and sends updates to the native agent via a local loopback WebSocket server.
3. **Ingestion Server (FastAPI)**: A backend endpoint that securely receives batched activity logs and persists them into a database using SQLAlchemy.
4. **Admin Dashboard**: A web interface for reviewing activity logs, device status, and usage analytics.

### Security & Data Protection
- **DPAPI Encryption**: The local SQLite cache (`cpam_cache.db`) is encrypted using Windows Data Protection API (DPAPI). This ensures that intercepted data on disk cannot be easily read by unauthorized local users.
- **Protected Ingestion**: Log uploads are secured with a Bearer token (`CPAM_INGEST_TOKEN`).
- **Secure Admin Access**: The dashboard uses bcrypt for password hashing and issues HTTP-only JWT cookies for authentication.

## Getting Started

### 1. Start the Ingestion Server (FastAPI)

Ensure you have Python 3.9+ installed.

```bash
# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate

# Install dependencies
python -m pip install -r backend/requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env to set your secrets (e.g., CPAM_INGEST_TOKEN, CPAM_ADMIN_PASSWORD)

# Run the server
python -m backend.app.main
# or: uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
The ingestion server will run on `http://127.0.0.1:8000`.

### 2. Run the Native Agent

The agent captures window activity and hosts the local WebSocket loopback server.

#### Option A: Python Fallback Agent (Recommended for development without a C++ toolchain)

```bash
# Ensure you are in the virtual environment
.venv\Scripts\activate

# Run the Python agent
python native-agent/agent.py
```

#### Option B: C++ Native Agent

If you have a C++17-capable toolchain (like Visual Studio or MinGW), you can compile the native executable.

```powershell
cd native-agent
./build.ps1
# Run the built executable
build\Release\native-agent.exe
```

**Troubleshooting C++ Compilation**: If you encounter errors or do not have a Visual Studio toolchain installed, use the Python fallback agent (`agent.py`) instead. The Python agent provides the same functionality and uses the same DPAPI encryption.

### 3. Install the Browser Companion

1. Open Chrome or Edge and go to `chrome://extensions/` (or `edge://extensions/`).
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `browser-extension` folder from this repository.
4. The extension will automatically connect to the agent's WebSocket server at `ws://127.0.0.1:8585`.

### 4. Access the Admin Dashboard

1. Navigate to `http://127.0.0.1:8000/admin/` in your browser.
2. Log in using the credentials defined in your `.env` file (Default: `admin` / `change-me`).

## Testing and Verification

You can verify the end-to-end flow using the provided test scripts:

1. Run the test script to verify APIs, rate limiting, and data persistence:
   ```bash
   .venv\Scripts\python.exe tools/test_cpam.py
   ```
2. Manually inspect the local cache to verify DPAPI encryption:
   ```bash
   python tools/view_cache.py --db native-agent/cpam_cache.db --limit 50
   ```
