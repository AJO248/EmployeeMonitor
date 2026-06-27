#!/usr/bin/env python3
import time
import sys
import urllib.request
import urllib.error
import json

import os

try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(dotenv_path)
except ImportError:
    pass

backend_url = os.getenv("CPAM_BACKEND_URL", "http://127.0.0.1:8000")
if "/api/v1/logs" in backend_url:
    BASE_URL = backend_url.split("/api/v1/logs")[0]
else:
    BASE_URL = backend_url.rstrip("/")

INGEST_TOKEN = os.getenv("CPAM_INGEST_TOKEN", "development-ingest-token")
ADMIN_USER = os.getenv("CPAM_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("CPAM_ADMIN_PASSWORD", "change-me")

def make_request(url, method="GET", data=None, headers=None):
    headers = headers or {}
    req_data = None
    if data:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8")), response.headers
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_data = e.reason
        return e.code, err_data, e.headers
    except Exception as e:
        return 0, str(e), {}

def test_flow():
    print("1. Verifying health endpoint...")
    status, body, _ = make_request(f"{BASE_URL}/health")
    if status != 200 or body.get("status") != "ok":
        print(f"Health check failed: status={status}, body={body}")
        sys.exit(1)
    print("Health check OK.")

    print("\n2. Verifying admin login...")
    status, body, headers = make_request(
        f"{BASE_URL}/api/v1/auth/login",
        method="POST",
        data={"username": ADMIN_USER, "password": ADMIN_PASS}
    )
    if status != 200 or "access_token" not in body:
        print(f"Login failed: status={status}, body={body}")
        sys.exit(1)
    
    token = body["access_token"]
    print("Admin login OK.")

    # Parse cookies from login response to mimic browser session
    cookie_header = None
    for k, v in headers.items():
        if k.lower() == "set-cookie" and "cpam_access_token" in v:
            cookie_header = v.split(";")[0]
            break
            
    auth_headers = {"Authorization": f"Bearer {token}"}
    if cookie_header:
        auth_headers["Cookie"] = cookie_header

    print("\n3. Ingesting sample activity logs...")
    # We will send:
    # - code.exe (productive) at t=0
    # - chrome.exe with github.com (productive) at t=60000 (1 min later)
    # - chrome.exe with youtube.com (unproductive) at t=120000 (2 mins later)
    # - idle_started at t=180000 (3 mins later)
    # - idle_ended at t=240000 (4 mins later)
    # - active_heartbeat at t=300000 (5 mins later)
    now_ms = int(time.time() * 1000)
    device_id = "test-device-999"
    
    batch = {
        "device_id": device_id,
        "entries": [
            {"type": "foreground_changed", "app_name": "code.exe", "timestamp": now_ms - 300000},
            {"type": "tab_activated", "app_name": "chrome.exe", "url": "https://github.com/Gemini-AI", "timestamp": now_ms - 240000},
            {"type": "tab_updated", "app_name": "chrome.exe", "url": "https://www.youtube.com/watch?v=123", "timestamp": now_ms - 180000},
            {"type": "idle_started", "timestamp": now_ms - 120000},
            {"type": "idle_ended", "timestamp": now_ms - 60000},
            {"type": "active_heartbeat", "app_name": "code.exe", "timestamp": now_ms}
        ]
    }
    
    status, body, _ = make_request(
        f"{BASE_URL}/api/v1/logs",
        method="POST",
        data=batch,
        headers={"Authorization": f"Bearer {INGEST_TOKEN}"}
    )
    if status != 200 or body.get("status") != "ok":
        print(f"Log ingestion failed: status={status}, body={body}")
        sys.exit(1)
    print(f"Ingested {body.get('received')} entries successfully.")

    print("\n4. Verifying analytics, productivity score, and classifications...")
    status, body, _ = make_request(f"{BASE_URL}/api/v1/analytics/summary?hours=1", headers=auth_headers)
    if status != 200:
        print(f"Failed to fetch analytics summary: status={status}, body={body}")
        sys.exit(1)
    
    # Find our test device in summary
    dev_summary = None
    for dev in body:
        if dev.get("device_id") == device_id:
            dev_summary = dev
            break
            
    if not dev_summary:
        print(f"Device {device_id} not found in analytics summary: {body}")
        sys.exit(1)
        
    print(f"Device found: {json.dumps(dev_summary, indent=2)}")
    
    # Assertions
    score = dev_summary.get("productivity_score")
    active_sec = dev_summary.get("active_seconds")
    idle_sec = dev_summary.get("idle_seconds")
    
    print(f"Productivity Score: {score}%")
    print(f"Active Seconds: {active_sec}s")
    print(f"Idle Seconds: {idle_sec}s")
    
    if score is None or score <= 0.0:
        print("Error: Productivity score calculation should be positive.")
        sys.exit(1)
        
    # Check top apps classifications
    code_app = next((x for x in dev_summary.get("top_apps", []) if x["name"] == "code.exe"), None)
    if not code_app or code_app.get("classification") != "productive":
        print(f"Error: code.exe should be classified as productive: {code_app}")
        sys.exit(1)
        
    youtube_domain = next((x for x in dev_summary.get("top_domains", []) if x["name"] == "youtube.com"), None)
    if not youtube_domain or youtube_domain.get("classification") != "unproductive":
        print(f"Error: youtube.com should be classified as unproductive: {youtube_domain}")
        sys.exit(1)
        
    github_domain = next((x for x in dev_summary.get("top_domains", []) if x["name"] == "github.com"), None)
    if not github_domain or github_domain.get("classification") != "productive":
        print(f"Error: github.com should be classified as productive: {github_domain}")
        sys.exit(1)
        
    print("Analytics & productivity score verification passed successfully!")

    print("\n5. Verifying database-backed rate limiting...")
    # Send quick logs in a loop to trigger rate limit (limit is 120 per minute by default, or we can send 130 batches)
    print("Testing rate limit. Sending batches rapidly...")
    rate_limited = False
    for i in range(130):
        # Mini batch
        mini_batch = {
            "device_id": "rate-limit-test-device",
            "entries": [{"type": "active_heartbeat", "timestamp": int(time.time() * 1000)}]
        }
        status, res_body, _ = make_request(
            f"{BASE_URL}/api/v1/logs",
            method="POST",
            data=mini_batch,
            headers={"Authorization": f"Bearer {INGEST_TOKEN}"}
        )
        if status == 429:
            rate_limited = True
            print(f"Successfully triggered 429 rate limit at request {i}!")
            break
        elif status != 200:
            print(f"Unexpected status code during rate limit testing: status={status}, body={res_body}")
            sys.exit(1)
            
    if not rate_limited:
        print("Warning: Did not trigger 429 rate limit (is CPAM_INGEST_RATE_LIMIT_PER_MINUTE configured differently?)")
        sys.exit(1)

    print("\nAll integration checks passed successfully!")

if __name__ == "__main__":
    test_flow()
