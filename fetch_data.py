#!/usr/bin/env python3
"""
Fetch trading statistics from QuantConnect API and generate dashboard data.
"""

import json
import os
import sys
from datetime import datetime
from hashlib import sha256
from base64 import b64encode
import urllib.request
import urllib.error


def get_auth_header(user_id: str, api_token: str) -> str:
    """Generate Basic auth header for QuantConnect API."""
    credentials = f"{user_id}:{api_token}"
    encoded = b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def api_request(endpoint: str, user_id: str, api_token: str) -> dict:
    """Make authenticated request to QuantConnect API."""
    url = f"https://www.quantconnect.com/api/v2/{endpoint}"
    auth = get_auth_header(user_id, api_token)

    req = urllib.request.Request(url, headers={
        "Authorization": auth,
        "Content-Type": "application/json"
    })

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"API Error {e.code}: {e.reason}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection Error: {e.reason}")
        sys.exit(1)


def fetch_projects(user_id: str, api_token: str) -> list:
    """Fetch all projects from QuantConnect."""
    result = api_request("projects/read", user_id, api_token)
    if not result.get("success"):
        print(f"Failed to fetch projects: {result.get('errors', 'Unknown error')}")
        sys.exit(1)
    return result.get("projects", [])


def fetch_backtests(project_id: int, user_id: str, api_token: str) -> list:
    """Fetch all backtests for a project."""
    result = api_request(f"backtests/read?projectId={project_id}", user_id, api_token)
    if not result.get("success"):
        print(f"Failed to fetch backtests: {result.get('errors', 'Unknown error')}")
        return []
    return result.get("backtests", [])


def fetch_backtest_details(project_id: int, backtest_id: str, user_id: str, api_token: str) -> dict:
    """Fetch detailed backtest results including equity curve."""
    result = api_request(
        f"backtests/read?projectId={project_id}&backtestId={backtest_id}",
        user_id, api_token
    )
    if not result.get("success"):
        print(f"Failed to fetch backtest details: {result.get('errors', 'Unknown error')}")
        return {}
    return result.get("backtest", {})


def fetch_live_results(project_id: int, user_id: str, api_token: str) -> dict:
    """Fetch live trading results for a project."""
    result = api_request(f"live/read?projectId={project_id}", user_id, api_token)
    if not result.get("success"):
        # Live algorithm might not exist, that's okay
        return {}
    return result.get("live", {})


def extract_performance_stats(result: dict) -> dict:
    """Extract key performance metrics from backtest/live result."""
    stats = result.get("statistics", {}) or {}
    runtime_stats = result.get("runtimeStatistics", {}) or {}

    # Parse equity curve from charts
    equity_data = []
    charts = result.get("charts", {}) or {}

    if "Strategy Equity" in charts:
        equity_series = charts["Strategy Equity"].get("series", {})
        if "Equity" in equity_series:
            for point in equity_series["Equity"].get("values", []):
                if isinstance(point, dict):
                    equity_data.append({
                        "x": point.get("x", 0),
                        "y": point.get("y", 0)
                    })

    # Extract key metrics
    def safe_float(val, default=0.0):
        if val is None:
            return default
        try:
            # Remove % sign if present
            if isinstance(val, str):
                val = val.replace("%", "").replace("$", "").replace(",", "")
            return float(val)
        except (ValueError, TypeError):
            return default

    return {
        "totalReturn": safe_float(stats.get("Total Net Profit") or runtime_stats.get("Total Net Profit")),
        "sharpeRatio": safe_float(stats.get("Sharpe Ratio")),
        "maxDrawdown": safe_float(stats.get("Drawdown") or stats.get("Max Drawdown")),
        "winRate": safe_float(stats.get("Win Rate")),
        "profitFactor": safe_float(stats.get("Profit-Loss Ratio")),
        "totalTrades": int(safe_float(stats.get("Total Trades") or stats.get("Total Orders"))),
        "equityCurve": equity_data,
        "startDate": result.get("created") or result.get("launched"),
        "endDate": result.get("completed") or runtime_stats.get("Updated"),
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

    dashboard_data = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "projects": []
    }

    # If specific project requested, only fetch that one
    if project_id:
        project_ids = [int(project_id)]
        projects = [{"projectId": int(project_id), "name": f"Project {project_id}"}]
    else:
        projects = fetch_projects(user_id, api_token)
        project_ids = [p["projectId"] for p in projects]

    for project in projects:
        pid = project["projectId"]
        pname = project.get("name", f"Project {pid}")
        print(f"  Processing: {pname}")

        project_data = {
            "id": pid,
            "name": pname,
            "backtests": [],
            "live": None
        }

        # Fetch backtests
        backtests = fetch_backtests(pid, user_id, api_token)

        # Get the most recent completed backtest with details
        for bt in sorted(backtests, key=lambda x: x.get("created", ""), reverse=True)[:3]:
            bt_id = bt.get("backtestId")
            if bt_id and bt.get("completed"):
                details = fetch_backtest_details(pid, bt_id, user_id, api_token)
                if details:
                    stats = extract_performance_stats(details)
                    stats["name"] = bt.get("name", "Unnamed Backtest")
                    stats["id"] = bt_id
                    project_data["backtests"].append(stats)

        # Fetch live results
        live = fetch_live_results(pid, user_id, api_token)
        if live and live.get("status") in ["Running", "RuntimeError", "Stopped"]:
            project_data["live"] = extract_performance_stats(live)
            project_data["live"]["status"] = live.get("status")

        if project_data["backtests"] or project_data["live"]:
            dashboard_data["projects"].append(project_data)

    # Write output
    output_path = os.path.join(os.path.dirname(__file__), "data", "dashboard.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(dashboard_data, f, indent=2)

    print(f"\nData saved to {output_path}")
    print(f"Found {len(dashboard_data['projects'])} projects with results")


if __name__ == "__main__":
    main()
