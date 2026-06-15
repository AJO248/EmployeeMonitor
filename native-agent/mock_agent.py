#!/usr/bin/env python3
"""
Mock native agent (Python) — replaces the C++ binary for Phase 1 testing.
- Hosts a WebSocket server on ws://127.0.0.1:8585
- Accepts JSON frames from the browser extension
- Stores frames in local SQLite `cpam_cache.db`
- Polls active foreground window (Windows-only via win32gui)
"""
import asyncio
import sqlite3
import json
import threading
import time
from datetime import datetime

try:
    import win32gui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import websockets
except ImportError:
    print("ERROR: websockets not installed. Install with: pip install websockets")
    exit(1)

DB = "cpam_cache.db"

def init_db():
    """Initialize SQLite with events table."""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, raw TEXT, received_at INTEGER);"
    )
    conn.commit()
    conn.close()
    print("SQLite DB initialized")

def insert_event(raw_json):
    """Insert a raw JSON event into the database."""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    ts = int(time.time())
    cur.execute("INSERT INTO events (raw, received_at) VALUES (?, ?)", (raw_json, ts))
    conn.commit()
    conn.close()

def foreground_poller():
    """Poll foreground window every second and print changes (Windows only)."""
    if not HAS_WIN32:
        return

    last_hwnd = None
    while True:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd != last_hwnd:
                last_hwnd = hwnd
                try:
                    title = win32gui.GetWindowText(hwnd)
                    print(f"FG: Title=\"{title}\"")
                except:
                    pass
        except:
            pass
        time.sleep(1)

async def handle_client(websocket, path):
    """Handle incoming WebSocket connections."""
    print(f"Client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            print(f"WS PAYLOAD: {message}")
            insert_event(message)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print(f"Client disconnected: {websocket.remote_address}")

async def ws_server():
    """Start the WebSocket server on 127.0.0.1:8585."""
    async with websockets.serve(handle_client, "127.0.0.1", 8585):
        print("WS Server listening on 127.0.0.1:8585")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    init_db()

    # Start foreground poller in background thread
    if HAS_WIN32:
        fg_thread = threading.Thread(target=foreground_poller, daemon=True)
        fg_thread.start()
    else:
        print("(win32gui not available; foreground polling skipped)")

    # Start WebSocket server
    try:
        asyncio.run(ws_server())
    except KeyboardInterrupt:
        print("\nShutdown.")
