#!/usr/bin/env python3
"""Simple viewer for the local SQLite cache `cpam_cache.db`.

Usage: python tools/view_cache.py [--limit N]
"""
import argparse
import os
import sqlite3
from datetime import datetime


def human(ts):
    try:
        return datetime.fromtimestamp(int(ts)).isoformat()
    except Exception:
        return str(ts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cpam_cache.db")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"DB not found: {args.db}")
        return

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()
    columns = {row[1] for row in cur.execute("PRAGMA table_info(events)")}
    delivery_columns = (
        ", delivered_at, attempts"
        if {"delivered_at", "attempts"}.issubset(columns)
        else ", NULL AS delivered_at, 0 AS attempts"
    )
    cur.execute(
        f"SELECT id, raw, received_at{delivery_columns} FROM events ORDER BY id DESC LIMIT ?",
        (args.limit,),
    )
    rows = cur.fetchall()
    for row in rows:
        delivery = human(row[3]) if row[3] else "pending"
        raw = "<DPAPI-protected event>" if row[1].startswith("dpapi:") else row[1]
        print(
            f"#{row[0]} @ {human(row[2])} | delivery={delivery} | attempts={row[4]}\n"
            f"{raw}\n---\n"
        )


if __name__ == "__main__":
    main()
