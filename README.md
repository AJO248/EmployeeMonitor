# EEAM Prototype (Phase 1)

This workspace contains a minimal Phase 1 prototype for the Enterprise Employee Activity Monitor (EEAM).

Components:

- `client/agent/Agent` — C# console app prototype that polls the foreground window and runs a local WebSocket server.
- `client/extension` — Chrome extension (Manifest V3) background service worker that sends tab events to the local WebSocket.
- `server/go` — Simple Go ingestion server with `/api/v1/logs` that enqueues events to a worker channel.
- `server/sql/schema.sql` — Minimal Postgres table schema for events.

Quick start (development):

1. Run the Go server:

```bash
cd server/go/cmd/eeam
go run .
```

2. Run the C# agent (Windows):

```powershell
cd client/agent/Agent
dotnet run
```

3. Load the Chrome extension:

- Open `chrome://extensions/` → Enable "Developer mode" → "Load unpacked" → Select `client/extension` folder.

The extension will attempt to connect to `ws://127.0.0.1:8765/ws/` and the C# agent will log incoming messages.

Next steps:

- Implement SQLite fallback and HTTP POSTing to the Go ingestion endpoint.
- Add tests and expand the Go server to persist events to Postgres.
