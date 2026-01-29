#!/usr/bin/env python3
"""
Fetch trading statistics from QuantConnect API and generate dashboard data.
"""

import json
import os
import sys
import time
from datetime import datetime
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


def api_request(endpoint: str, user_id: str, api_token: str, method: str = "GET", data: dict = None) -> dict:
    """Make authenticated request to QuantConnect API."""
    url = f"https://www.quantconnect.com/api/v2/{endpoint}"
    headers = get_auth_headers(user_id, api_token)

    # QuantConnect also needs userId in the request for some endpoints
    if "?" in url:
        url += f"&userId={user_id}"
    else:
        url += f"?userId={user_id}"

    req = urllib.request.Request(url, headers=headers, method=method)

    if data:
        req.data = json.dumps(data).encode('utf-8')

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else "No response body"
        print(f"API Error {e.code}: {e.reason}")
        print(f"Response: {body}")
        return {"success": False, "errors": [f"HTTP {e.code}: {e.reason}"]}
    except urllib.error.URLError as e:
        print(f"Connection Error: {e.reason}")
        return {"success": False, "errors": [str(e.reason)]}


def fetch_authenticate(user_id: str, api_token: str) -> bool:
    """Test authentication with QuantConnect API."""
    result = api_request("authenticate", user_id, api_token)
    return result.get("success", False)


def fetch_projects(user_id: str, api_token: str) -> list:
    """Fetch all projects from QuantConnect."""
    result = api_request("projects/read", user_id, api_token)
    if not result.get("success"):
        print(f"Failed to fetch projects: {result.get('errors', 'Unknown error')}")
        return []
    return result.get("projects", [])


def fetch_live_list(user_id: str, api_token: str) -> list:
    """Fetch all live/paper trading algorithms."""
    result = api_request("live/list", user_id, api_token)
    if not result.get("success"):
        print(f"Failed to fetch live algorithms: {result.get('errors', 'Unknown error')}")
        return []
    return result.get("live", [])


def fetch_live_details(project_id: int, deploy_id: str, user_id: str, api_token: str) -> dict:
    """Fetch detailed live trading results."""
    result = api_request(f"live/read&projectId={project_id}&deployId={deploy_id}", user_id, api_token)
    if not result.get("success"):
        # Try alternative endpoint format
        result = api_request(f"live/read&projectId={project_id}", user_id, api_token)
    if not result.get("success"):
        print(f"Failed to fetch live details: {result.get('errors', 'Unknown error')}")
        return {}
    return result.get("live", result.get("LiveResults", {}))


def fetch_backtests(project_id: int, user_id: str, api_token: str) -> list:
    """Fetch all backtests for a project."""
    result = api_request(f"backtests/read&projectId={project_id}", user_id, api_token)
    if not result.get("success"):
        return []
    return result.get("backtests", [])


def fetch_backtest_details(project_id: int, backtest_id: str, user_id: str, api_token: str) -> dict:
    """Fetch detailed backtest results including equity curve."""
    result = api_request(f"backtests/read&projectId={project_id}&backtestId={backtest_id}", user_id, api_token)
    if not result.get("success"):
        return {}
    return result.get("backtest", {})


def extract_performance_stats(result: dict, is_live: bool = False) -> dict:
    """Extract key performance metrics from backtest/live result."""
    stats = result.get("statistics", {}) or {}
    runtime_stats = result.get("runtimeStatistics", {}) or {}

    # For live results, stats might be nested differently
    if not stats and "Statistics" in result:
        stats = result["Statistics"]
    if not runtime_stats and "RuntimeStatistics" in result:
        runtime_stats = result["RuntimeStatistics"]

    # Parse equity curve from charts
    equity_data = []
    charts = result.get("charts", {}) or result.get("Charts", {}) or {}

    if "Strategy Equity" in charts:
        equity_series = charts["Strategy Equity"].get("series", {}) or charts["Strategy Equity"].get("Series", {})
        equity_key = "Equity" if "Equity" in equity_series else next(iter(equity_series), None)
        if equity_key:
            values = equity_series[equity_key].get("values", []) or equity_series[equity_key].get("Values", [])
            for point in values:
                if isinstance(point, dict):
                    equity_data.append({
                        "x": point.get("x", point.get("X", 0)),
                        "y": point.get("y", point.get("Y", 0))
                    })

    # Extract key metrics
    def safe_float(val, default=0.0):
        if val is None:
            return default
        try:
            if isinstance(val, str):
                val = val.replace("%", "").replace("$", "").replace(",", "").strip()
            return float(val)
        except (ValueError, TypeError):
            return default

    return {
        "totalReturn": safe_float(stats.get("Total Net Profit") or runtime_stats.get("Total Net Profit") or stats.get("Net Profit")),
        "sharpeRatio": safe_float(stats.get("Sharpe Ratio")),
        "maxDrawdown": safe_float(stats.get("Drawdown") or stats.get("Max Drawdown")),
        "winRate": safe_float(stats.get("Win Rate")),
        "profitFactor": safe_float(stats.get("Profit-Loss Ratio")),
        "totalTrades": int(safe_float(stats.get("Total Trades") or stats.get("Total Orders") or 0)),
        "equityCurve": equity_data,
        "startDate": result.get("created") or result.get("launched") or result.get("Launched"),
        "endDate": result.get("completed") or runtime_stats.get("Updated") or result.get("Stopped"),
    }


def main():
    # Get credentials from environment
    user_id = os.environ.get("QC_USER_ID")
    api_token = os.environ.get("QC_API_TOKEN")
    project_id = os.environ.get("QC_PROJECT_ID")  # Optional: specific project

    if not user_id or not api_token:
        print("Error: QC_USER_ID and QC_API_TOKEN environment variables required")
        print("\nTo set them:")
        print("  Windows: set QC_USER_ID=12345 && set QC_API_TOKEN=your_token")
        print("  Linux/Mac: export QC_USER_ID=12345 && export QC_API_TOKEN=your_token")
        sys.exit(1)

    print(f"Fetching data for user {user_id}...")

    # Test authentication first
    if not fetch_authenticate(user_id, api_token):
        print("Authentication failed. Please check your credentials.")
        sys.exit(1)

    print("Authentication successful!")

    dashboard_data = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "projects": []
    }

    # Fetch live algorithms first (user's primary interest)
    print("Fetching live/paper trading algorithms...")
    live_algos = fetch_live_list(user_id, api_token)
    print(f"Found {len(live_algos)} live/paper trading algorithms")

    # Process live algorithms
    live_project_ids = set()
    for algo in live_algos:
        pid = algo.get("projectId")
        if pid:
            live_project_ids.add(pid)

            project_data = {
                "id": pid,
                "name": algo.get("projectName", f"Project {pid}"),
                "backtests": [],
                "live": None
            }

            # Fetch detailed live results
            deploy_id = algo.get("deployId", "")
            print(f"  Fetching live details for: {project_data['name']}")

            live_details = fetch_live_details(pid, deploy_id, user_id, api_token)
            if live_details:
                project_data["live"] = extract_performance_stats(live_details, is_live=True)
                project_data["live"]["status"] = algo.get("status", "Unknown")
                project_data["live"]["deployId"] = deploy_id
            else:
                # Use basic info from list if details fail
                project_data["live"] = {
                    "status": algo.get("status", "Unknown"),
                    "deployId": deploy_id,
                    "totalReturn": 0,
                    "sharpeRatio": 0,
                    "maxDrawdown": 0,
                    "winRate": 0,
                    "equityCurve": []
                }

            dashboard_data["projects"].append(project_data)

    # Optionally fetch backtests for projects without live trading
    if not project_id:
        projects = fetch_projects(user_id, api_token)
        for project in projects:
            pid = project["projectId"]
            if pid in live_project_ids:
                continue  # Already processed as live

            pname = project.get("name", f"Project {pid}")
            print(f"  Processing backtests for: {pname}")

            project_data = {
                "id": pid,
                "name": pname,
                "backtests": [],
                "live": None
            }

            backtests = fetch_backtests(pid, user_id, api_token)
            for bt in sorted(backtests, key=lambda x: x.get("created", ""), reverse=True)[:3]:
                bt_id = bt.get("backtestId")
                if bt_id and bt.get("completed"):
                    details = fetch_backtest_details(pid, bt_id, user_id, api_token)
                    if details:
                        stats = extract_performance_stats(details)
                        stats["name"] = bt.get("name", "Unnamed Backtest")
                        stats["id"] = bt_id
                        project_data["backtests"].append(stats)

            if project_data["backtests"]:
                dashboard_data["projects"].append(project_data)

    # Write output
    output_path = os.path.join(os.path.dirname(__file__), "data", "dashboard.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(dashboard_data, f, indent=2)

    print(f"\nData saved to {output_path}")
    print(f"Found {len(dashboard_data['projects'])} projects with results")

    # Summary
    live_count = sum(1 for p in dashboard_data["projects"] if p.get("live"))
    print(f"  - {live_count} with live/paper trading")
    print(f"  - {len(dashboard_data['projects']) - live_count} with backtests only")


if __name__ == "__main__":
    main()
