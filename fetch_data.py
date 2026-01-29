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
    """Generate authentication headers for QuantConnect API."""
    from base64 import b64encode

    timestamp = str(int(time.time()))
    hash_bytes = sha256(f"{api_token}:{timestamp}".encode('utf-8')).hexdigest()
    credentials = f"{user_id}:{hash_bytes}"
    encoded = b64encode(credentials.encode()).decode()

    return {
        "Timestamp": timestamp,
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json"
    }


def api_request(endpoint: str, user_id: str, api_token: str) -> dict:
    """Make authenticated request to QuantConnect API."""
    url = f"https://www.quantconnect.com/api/v2/{endpoint}"
    headers = get_auth_headers(user_id, api_token)

    if "?" in url:
        url += f"&userId={user_id}"
    else:
        url += f"?userId={user_id}"

    req = urllib.request.Request(url, headers=headers)

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


def fetch_live_list(user_id: str, api_token: str) -> list:
    """Fetch all live/paper trading algorithms with their statistics."""
    result = api_request("live/list", user_id, api_token)
    if not result.get("success"):
        print(f"Failed to fetch live algorithms: {result.get('errors', 'Unknown error')}")
        return []
    return result.get("live", [])


def fetch_portfolio(project_id: int, user_id: str, api_token: str) -> dict:
    """Fetch live portfolio (holdings and cash)."""
    result = api_request(f"live/portfolio/read?projectId={project_id}", user_id, api_token)
    if not result.get("success"):
        return {}
    return result.get("portfolio", {})


def safe_float(val, default=0.0):
    """Safely convert value to float."""
    if val is None:
        return default
    try:
        if isinstance(val, str):
            val = val.replace("%", "").replace("$", "").replace(",", "").strip()
        return float(val)
    except (ValueError, TypeError):
        return default


def extract_live_stats(algo: dict, portfolio: dict) -> dict:
    """Extract performance stats from live algorithm list response."""
    stats = algo.get("statistics", {}) or {}

    # Get equity value
    equity = safe_float(algo.get("equity", 0))

    # Calculate total return if we have starting capital info
    # Try to get from statistics or estimate from portfolio
    total_return = safe_float(stats.get("Total Net Profit") or stats.get("Net Profit"))

    # Get other stats
    sharpe = safe_float(stats.get("Sharpe Ratio"))
    drawdown = safe_float(stats.get("Drawdown") or stats.get("Max Drawdown"))
    win_rate = safe_float(stats.get("Win Rate"))
    total_trades = int(safe_float(stats.get("Total Trades") or stats.get("Total Orders") or 0))
    profit_factor = safe_float(stats.get("Profit-Loss Ratio") or stats.get("Profit Factor"))

    # Get cash from portfolio
    cash = 0
    if portfolio and "cash" in portfolio:
        for currency, cash_data in portfolio["cash"].items():
            cash += safe_float(cash_data.get("valueInAccountCurrency", 0))

    # Get holdings value
    holdings_value = 0
    holdings_list = []
    if portfolio and "holdings" in portfolio:
        for symbol, holding in portfolio["holdings"].items():
            value = safe_float(holding.get("marketValue", 0))
            holdings_value += value
            if value != 0:
                holdings_list.append({
                    "symbol": symbol,
                    "quantity": safe_float(holding.get("quantity", 0)),
                    "avgPrice": safe_float(holding.get("averagePrice", 0)),
                    "marketValue": value
                })

    return {
        "equity": equity,
        "cash": cash,
        "holdingsValue": holdings_value,
        "holdings": holdings_list,
        "totalReturn": total_return,
        "sharpeRatio": sharpe,
        "maxDrawdown": drawdown,
        "winRate": win_rate,
        "totalTrades": total_trades,
        "profitFactor": profit_factor,
        "launched": algo.get("launched"),
        "allStats": stats  # Include all stats for display
    }


def main():
    user_id = os.environ.get("QC_USER_ID")
    api_token = os.environ.get("QC_API_TOKEN")

    if not user_id or not api_token:
        print("Error: QC_USER_ID and QC_API_TOKEN environment variables required")
        sys.exit(1)

    print(f"Fetching data for user {user_id}...")

    if not fetch_authenticate(user_id, api_token):
        print("Authentication failed. Please check your credentials.")
        sys.exit(1)

    print("Authentication successful!")

    dashboard_data = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "projects": []
    }

    # Fetch live algorithms - this contains all the stats we need
    print("Fetching live/paper trading algorithms...")
    live_algos = fetch_live_list(user_id, api_token)
    print(f"Found {len(live_algos)} live/paper trading algorithms")

    for algo in live_algos:
        project_id = algo.get("projectId")
        project_name = algo.get("name") or algo.get("description") or f"Project {project_id}"

        print(f"  Processing: {project_name}")

        # Fetch portfolio for additional details
        portfolio = fetch_portfolio(project_id, user_id, api_token)

        # Extract stats from list response
        live_stats = extract_live_stats(algo, portfolio)
        live_stats["status"] = algo.get("status", "Unknown")
        live_stats["deployId"] = algo.get("deployId", "")
        live_stats["brokerage"] = algo.get("brokerage", "")

        project_data = {
            "id": project_id,
            "name": project_name,
            "live": live_stats
        }

        dashboard_data["projects"].append(project_data)

        # Print summary
        print(f"    Status: {live_stats['status']}")
        print(f"    Equity: ${live_stats['equity']:,.2f}")
        print(f"    Cash: ${live_stats['cash']:,.2f}")
        if live_stats['totalTrades'] > 0:
            print(f"    Total Trades: {live_stats['totalTrades']}")

    # Write output
    output_path = os.path.join(os.path.dirname(__file__), "data", "dashboard.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(dashboard_data, f, indent=2)

    print(f"\nData saved to {output_path}")
    print(f"Found {len(dashboard_data['projects'])} live algorithms")


if __name__ == "__main__":
    main()
