#!/usr/bin/env python3
"""
Debug script to see what data QuantConnect returns for live algorithms.
Run: python debug_live_data.py USER_ID API_TOKEN
"""

import sys
import json
import time
from hashlib import sha256
from base64 import b64encode
import urllib.request
import urllib.error


def get_auth_headers(user_id: str, api_token: str) -> dict:
    timestamp = str(int(time.time()))
    hash_bytes = sha256(f"{api_token}:{timestamp}".encode('utf-8')).hexdigest()
    credentials = f"{user_id}:{hash_bytes}"
    encoded = b64encode(credentials.encode()).decode()
    return {
        "Timestamp": timestamp,
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json"
    }


def api_get(endpoint: str, user_id: str, api_token: str) -> dict:
    url = f"https://www.quantconnect.com/api/v2/{endpoint}"
    if "?" in url:
        url += f"&userId={user_id}"
    else:
        url += f"?userId={user_id}"

    headers = get_auth_headers(user_id, api_token)
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "body": body}


def main(user_id: str, api_token: str):
    print("=" * 60)
    print("DEBUGGING QUANTCONNECT LIVE ALGORITHM DATA")
    print("=" * 60)

    # 1. Get live algorithm list
    print("\n[1] Fetching live algorithm list...")
    live_list = api_get("live/list", user_id, api_token)

    if not live_list.get("success"):
        print(f"Failed: {live_list}")
        return

    algos = live_list.get("live", [])
    print(f"Found {len(algos)} live algorithms")

    for algo in algos:
        project_id = algo.get("projectId")
        deploy_id = algo.get("deployId")

        print(f"\n{'=' * 60}")
        print(f"Algorithm: {algo.get('projectName', 'Unknown')}")
        print(f"Project ID: {project_id}")
        print(f"Deploy ID: {deploy_id}")
        print(f"Status: {algo.get('status')}")
        print(f"Launched: {algo.get('launched')}")

        # Print all keys in the list response
        print(f"\nKeys in list response: {list(algo.keys())}")

        # 2. Get detailed live results
        print(f"\n[2] Fetching live/read for project {project_id}...")
        live_read = api_get(f"live/read?projectId={project_id}", user_id, api_token)

        if live_read.get("success"):
            live_data = live_read.get("live", {})
            print(f"Keys in live/read response: {list(live_data.keys())}")

            # Check for statistics
            if "statistics" in live_data:
                print(f"\nStatistics: {json.dumps(live_data['statistics'], indent=2)[:1000]}")

            if "runtimeStatistics" in live_data:
                print(f"\nRuntime Statistics: {json.dumps(live_data['runtimeStatistics'], indent=2)[:1000]}")

            if "charts" in live_data:
                charts = live_data["charts"]
                print(f"\nAvailable charts: {list(charts.keys())}")
                if "Strategy Equity" in charts:
                    eq = charts["Strategy Equity"]
                    print(f"Strategy Equity series: {list(eq.get('series', {}).keys())}")
                    # Check if there's data
                    for series_name, series_data in eq.get("series", {}).items():
                        values = series_data.get("values", [])
                        print(f"  - {series_name}: {len(values)} data points")
                        if values:
                            print(f"    Sample: {values[-1] if values else 'empty'}")
        else:
            print(f"Failed: {live_read}")

        # 3. Try live/read with deploy ID
        print(f"\n[3] Fetching live/read with deployId...")
        live_read2 = api_get(f"live/read?projectId={project_id}&deployId={deploy_id}", user_id, api_token)
        if live_read2.get("success"):
            live_data2 = live_read2.get("live", {})
            print(f"Keys: {list(live_data2.keys())}")
        else:
            print(f"Failed: {live_read2.get('errors', live_read2)}")

        # 4. Try fetching live orders
        print(f"\n[4] Fetching live orders...")
        orders = api_get(f"live/orders/read?projectId={project_id}", user_id, api_token)
        if orders.get("success"):
            order_list = orders.get("orders", [])
            print(f"Found {len(order_list)} orders")
            if order_list:
                print(f"Sample order keys: {list(order_list[0].keys())}")
        else:
            print(f"Failed: {orders.get('errors', orders)}")

        # 5. Try fetching live portfolio
        print(f"\n[5] Fetching live portfolio...")
        portfolio = api_get(f"live/portfolio/read?projectId={project_id}", user_id, api_token)
        print(f"Portfolio response: {json.dumps(portfolio, indent=2)[:1500]}")

        # 6. Try live results endpoint
        print(f"\n[6] Fetching live/results...")
        results = api_get(f"live/results/read?projectId={project_id}&deployId={deploy_id}", user_id, api_token)
        if results.get("success"):
            print(f"Keys: {list(results.keys())}")
            if "LiveResults" in results:
                lr = results["LiveResults"]
                print(f"LiveResults keys: {list(lr.keys())}")
        else:
            print(f"Response: {json.dumps(results, indent=2)[:1000]}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python debug_live_data.py USER_ID API_TOKEN")
        sys.exit(1)

    main(sys.argv[1].strip(), sys.argv[2].strip())
