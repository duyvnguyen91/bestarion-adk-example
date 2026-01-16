import requests
from google.adk.agents import Agent

# Best model for fast iteration
MODEL = "gemini-2.0-flash"

def fetch_btc_snapshot() -> dict:
    """
    Fetch a simple BTC/USDT snapshot from Binance.
    """
    resp = requests.get(
        "https://api.binance.com/api/v3/ticker/24hr",
        params={"symbol": "BTCUSDT"},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "last_price": float(data["lastPrice"]),
        "high_24h": float(data["highPrice"]),
        "low_24h": float(data["lowPrice"]),
        "change_pct": float(data["priceChangePercent"]),
        "volume": float(data["volume"]),
    }

root_agent = Agent(
    name="BTCMorningAnalyst",
    model="gemini-2.0-flash",
    tools=[fetch_btc_snapshot],
    instruction="""
    You are a professional BTC technical analyst.

    Rules:
    - You MAY call fetch_btc_snapshot if no BTC data is provided
    - Use fetched data ONLY
    - Do not guess indicators you do not have
    - If indicators are missing, state that clearly

    Output format:

    🌅 BTC Market Outlook

    BTC/USD:
    - Trend:
    - Support:
    - Resistance:
    - Bias:
    - Notes:
    """
)
