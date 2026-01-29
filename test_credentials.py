#!/usr/bin/env python3
"""
Test your QuantConnect API credentials locally.
Run: python test_credentials.py YOUR_USER_ID YOUR_API_TOKEN
"""

import sys
import json
import time
from hashlib import sha256
import urllib.request
import urllib.error


def get_auth_headers(user_id: str, api_token: str) -> dict:
    """Generate authentication headers for QuantConnect API.

    QuantConnect uses:
    - Timestamp header: current Unix timestamp
    - Authorization: Basic base64(userId:SHA256(apiToken:timestamp))
    """
    from base64 import b64encode

    timestamp = str(int(time.time()))

    # Hash: SHA256(apiToken:timestamp) - with colon separator
    hash_bytes = sha256(f"{api_token}:{timestamp}".encode('utf-8')).hexdigest()

    # Basic auth: base64(userId:hash)
    credentials = f"{user_id}:{hash_bytes}"
    encoded = b64encode(credentials.encode()).decode()

    return {
        "Timestamp": timestamp,
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json"
    }


def test_api(user_id: str, api_token: str):
    """Test QuantConnect API connection."""

    print(f"Testing connection for user ID: {user_id}")
    print(f"Token (first 8 chars): {api_token[:8]}...")
    print("-" * 50)

    # Test authentication endpoint
    url = f"https://www.quantconnect.com/api/v2/authenticate?userId={user_id}"
    headers = get_auth_headers(user_id, api_token)
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            print("Authentication response:")
            print(json.dumps(data, indent=2))

            if data.get("success"):
                print("\n[OK] Authentication successful!")
            else:
                print(f"\n[FAIL] Authentication failed: {data.get('errors', 'Unknown error')}")
                return False

    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else "No response body"
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"Response: {body}")
        return False
    except urllib.error.URLError as e:
        print(f"Connection Error: {e.reason}")
        return False

    print("-" * 50)

    # Test projects endpoint
    url = f"https://www.quantconnect.com/api/v2/projects/read?userId={user_id}"
    headers = get_auth_headers(user_id, api_token)
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

            if data.get("success"):
                projects = data.get("projects", [])
                print(f"[OK] Found {len(projects)} projects:")
                for p in projects[:10]:
                    print(f"  - {p.get('name')} (ID: {p.get('projectId')})")
            else:
                print(f"[FAIL] Failed to fetch projects: {data.get('errors', 'Unknown error')}")

    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else "No response body"
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"Response: {body}")

    print("-" * 50)

    # Test live algorithms endpoint
    url = f"https://www.quantconnect.com/api/v2/live/list?userId={user_id}"
    headers = get_auth_headers(user_id, api_token)
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

            if data.get("success"):
                live_algos = data.get("live", [])
                print(f"[OK] Found {len(live_algos)} live/paper trading algorithms:")
                for algo in live_algos:
                    print(f"  - {algo.get('projectName', 'Unknown')} | Status: {algo.get('status')} | Project ID: {algo.get('projectId')}")
            else:
                print(f"[FAIL] Failed to fetch live algorithms: {data.get('errors', 'Unknown error')}")

    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else "No response body"
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"Response: {body}")

    print("-" * 50)
    print("\nIf all tests passed, your credentials are working!")
    print("You can now push the updated code and run the GitHub Action.")

    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_credentials.py USER_ID API_TOKEN")
        print("\nExample: python test_credentials.py 123456 abc123def456...")
        sys.exit(1)

    user_id = sys.argv[1].strip()
    api_token = sys.argv[2].strip()

    success = test_api(user_id, api_token)
    sys.exit(0 if success else 1)
