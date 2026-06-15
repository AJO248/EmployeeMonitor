#!/usr/bin/env python3
"""
Fully functional Python native agent fallback for CPAM.
Hosts WebSocket server, polls foreground window/idle status, encrypts with DPAPI, and uploads to backend.
"""

import os
import sys
import time
import json
import sqlite3
import socket
import asyncio
import threading
import urllib.request
import urllib.error
import base64
import websockets

try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(dotenv_path)
except ImportError:
    pass

IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("dwTime", ctypes.c_ulong)
        ]

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.c_ulong),
            ("pbData", ctypes.POINTER(ctypes.c_ubyte))
        ]

    def protect_data(data: bytes, description: str = "CPAM cache event") -> bytes:
        in_blob = DATA_BLOB()
        in_blob.cbData = len(data)
        in_blob.pbData = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        out_blob = DATA_BLOB()
        
        CRYPTPROTECT_UI_FORBIDDEN = 0x1
        CRYPTPROTECT_LOCAL_MACHINE = 0x4
        flags = CRYPTPROTECT_UI_FORBIDDEN | CRYPTPROTECT_LOCAL_MACHINE
        
        success = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            ctypes.c_wchar_p(description),
            None,
            None,
            None,
            flags,
            ctypes.byref(out_blob)
        )
        if not success:
            raise OSError("CryptProtectData failed")
            
        result = bytes(out_blob.pbData[:out_blob.cbData])
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return result

    def unprotect_data(data: bytes) -> bytes:
        in_blob = DATA_BLOB()
        in_blob.cbData = len(data)
        in_blob.pbData = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        out_blob = DATA_BLOB()
        
        CRYPTPROTECT_UI_FORBIDDEN = 0x1
        
        success = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob)
        )
        if not success:
            raise OSError("CryptUnprotectData failed")
            
        result = bytes(out_blob.pbData[:out_blob.cbData])
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return result

    def get_process_name(pid):
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        process = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process:
            return ""
        buf = ctypes.create_unicode_buffer(32768)
        size = ctypes.c_ulong(len(buf))
        success = ctypes.windll.kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size))
        ctypes.windll.kernel32.CloseHandle(process)
        if success:
            return os.path.basename(buf.value)
        return ""

    def get_foreground_window_info():
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return "", ""
        title_buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, len(title_buf))
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        app_name = get_process_name(pid.value)
        return app_name, title_buf.value

    def is_device_idle(threshold_ms=300000):
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            tick = ctypes.windll.kernel32.GetTickCount()
            idle_ms = tick - lii.dwTime
            return idle_ms >= threshold_ms
        return False
else:
    def get_foreground_window_info():
        return "mock_app", "Mock Window Title"
    def is_device_idle(threshold_ms=300000):
        return False

def init_database():
    conn = sqlite3.connect("cpam_cache.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            raw TEXT NOT NULL,
            received_at INTEGER NOT NULL,
            delivered_at INTEGER,
            attempts INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_pending ON events(delivered_at, id);")
    conn.commit()
    conn.close()

def protect_cache_value(raw: str) -> str:
    if IS_WINDOWS:
        try:
            encrypted = protect_data(raw.encode('utf-8'))
            return "dpapi:" + base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            print(f"DPAPI Encryption failed: {e}")
            return raw
    return raw

def unprotect_cache_value(stored: str) -> str:
    if stored.startswith("dpapi:") and IS_WINDOWS:
        try:
            encrypted = base64.b64decode(stored[6:])
            decrypted = unprotect_data(encrypted)
            return decrypted.decode('utf-8')
        except Exception as e:
            print(f"DPAPI Decryption failed: {e}")
            return ""
    return stored

def insert_raw_event(raw: str):
    protected = protect_cache_value(raw)
    conn = sqlite3.connect("cpam_cache.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO events (raw, received_at) VALUES (?, ?);", (protected, int(time.time())))
    conn.commit()
    conn.close()

def read_pending_events(batch_size=100):
    conn = sqlite3.connect("cpam_cache.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, raw FROM events WHERE delivered_at IS NULL ORDER BY id LIMIT ?;", (batch_size,))
    rows = cur.fetchall()
    events = []
    for row in rows:
        unprotected = unprotect_cache_value(row["raw"])
        if unprotected:
            events.append({"id": row["id"], "raw": unprotected})
    conn.close()
    return events

def update_delivery_state(events, delivered):
    conn = sqlite3.connect("cpam_cache.db")
    cur = conn.cursor()
    now = int(time.time())
    if delivered:
        cur.executemany(
            "UPDATE events SET delivered_at = ?, attempts = attempts + 1 WHERE id = ?;",
            [(now, ev["id"]) for ev in events]
        )
    else:
        cur.executemany(
            "UPDATE events SET attempts = attempts + 1 WHERE id = ?;",
            [(ev["id"],) for ev in events]
        )
    conn.commit()
    conn.close()

def flush_worker():
    retry_seconds = 5
    backend_url = os.getenv("CPAM_BACKEND_URL", "http://127.0.0.1:8000/api/v1/logs")
    ingest_token = os.getenv("CPAM_INGEST_TOKEN", "development-ingest-token")
    
    try:
        device_id = socket.gethostname()
    except Exception:
        device_id = os.getenv("COMPUTERNAME", "unknown-windows-device")
        
    while True:
        try:
            events = read_pending_events(batch_size=100)
            if not events:
                retry_seconds = 5
                time.sleep(5)
                continue
            
            batch = {
                "device_id": device_id,
                "entries": [json.loads(ev["raw"]) for ev in events]
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ingest_token}"
            }
            
            req = urllib.request.Request(
                backend_url,
                data=json.dumps(batch).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            
            success = False
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    if 200 <= response.status < 300:
                        success = True
            except Exception as e:
                pass
            
            update_delivery_state(events, success)
            
            if success:
                print(f"Uploaded {len(events)} cached event(s)")
                retry_seconds = 5
            else:
                print(f"Upload failed; retrying in {retry_seconds} seconds")
                time.sleep(retry_seconds)
                retry_seconds = min(retry_seconds * 2, 300)
        except Exception as e:
            print(f"Flush worker error: {e}")
            time.sleep(5)

def foreground_poller():
    previous_hwnd = None
    previous_idle = False
    last_heartbeat = time.time() - 60
    idle_threshold_ms = 5 * 60 * 1000
    
    while True:
        try:
            idle = is_device_idle(idle_threshold_ms)
            if idle != previous_idle:
                previous_idle = idle
                event = {
                    "type": "idle_started" if idle else "idle_ended",
                    "timestamp": int(time.time() * 1000)
                }
                insert_raw_event(json.dumps(event))
                print(f"Device became {'idle' if idle else 'active'}")
            
            if time.time() - last_heartbeat >= 60:
                event = {
                    "type": "idle_heartbeat" if idle else "active_heartbeat",
                    "timestamp": int(time.time() * 1000)
                }
                insert_raw_event(json.dumps(event))
                last_heartbeat = time.time()
                
            if IS_WINDOWS:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd != previous_hwnd:
                    previous_hwnd = hwnd
                    if hwnd:
                        app_name, title = get_foreground_window_info()
                        event = {
                            "type": "foreground_changed",
                            "app_name": app_name,
                            "title": title,
                            "timestamp": int(time.time() * 1000)
                        }
                        insert_raw_event(json.dumps(event))
                        print(f"Foreground: {app_name} - {title}")
        except Exception as e:
            print(f"Poller error: {e}")
        time.sleep(1)

async def handle_websocket(websocket, *args, **kwargs):
    try:
        async for message in websocket:
            insert_raw_event(message)
    except Exception:
        pass

async def main_async():
    init_database()
    
    # Run polling and flushing in background threads
    threading.Thread(target=foreground_poller, daemon=True).start()
    threading.Thread(target=flush_worker, daemon=True).start()
    
    async with websockets.serve(handle_websocket, "127.0.0.1", 8585):
        print("WebSocket server listening on 127.0.0.1:8585")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nShutdown.")
