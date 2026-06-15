#!/usr/bin/env python3
"""Simple DB tailer for native-agent/cpam_cache.db
Prints new rows (id, received_at) and parsed JSON from `raw`.
"""
import sqlite3
import time
import json
import os
import sys

DB = os.path.join(os.path.dirname(__file__), 'cpam_cache.db')

if not os.path.exists(DB):
    print(f"DB not found: {DB}")
    sys.exit(1)

def tail(db_path, poll=1.0):
    conn = sqlite3.connect(db_path, timeout=5)
    cur = conn.cursor()
    last_id = 0
    try:
        row = cur.execute('SELECT id FROM events ORDER BY id DESC LIMIT 1').fetchone()
        if row:
            last_id = row[0]
    except Exception:
        last_id = 0

    print(f"Starting tail from id > {last_id}")
    try:
        while True:
            try:
                rows = cur.execute('SELECT id, raw, received_at FROM events WHERE id > ? ORDER BY id', (last_id,)).fetchall()
            except sqlite3.OperationalError:
                # DB locked or schema not ready yet
                time.sleep(poll)
                continue
            for r in rows:
                _id, raw, ts = r
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = raw
                print(f"[{_id}] {ts} -> {parsed}")
                last_id = _id
            time.sleep(poll)
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        conn.close()

if __name__ == '__main__':
    tail(DB)
