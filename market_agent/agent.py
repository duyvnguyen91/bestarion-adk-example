import requests
import os
from google.adk.agents import Agent, LlmAgent
from dotenv import load_dotenv

load_dotenv()

# Best model for fast iteration
MODEL = "gemini-2.0-flash"
ALPHAVANTAGE_API_KEY = os.environ["ALPHAVANTAGE_API_KEY"]

def fetch_fx_snapshot(from_symbol: str, to_symbol: str = "USD") -> dict:
    resp = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_symbol,
            "to_currency": to_symbol,
            "apikey": ALPHAVANTAGE_API_KEY,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    if "Realtime Currency Exchange Rate" not in data:
        raise RuntimeError(f"Alpha Vantage error: {data}")

    rate = data["Realtime Currency Exchange Rate"]

    return {
        "from": from_symbol,
        "to": to_symbol,
        "rate": float(rate["5. Exchange Rate"]),
        "bid": float(rate["8. Bid Price"]),
        "ask": float(rate["9. Ask Price"]),
        "last_refreshed": rate["6. Last Refreshed"],
    }

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

fx_agent = Agent(
    name="FXAnalyst",
    model=MODEL,
    tools=[fetch_fx_snapshot],
    instruction="""
    You are a professional FX analyst.

    Rules:
    - You MAY call fetch_fx_snapshot when needed
    - Analyze Forex only
    - Use fetched data ONLY
    - Do not invent technical indicators
    - If only spot price is available, limit analysis to:
    - Directional bias
    - Volatility
    - Spread quality

    Output format:

    🌅 FX Market Outlook

    <FOREX PAIR>:
    - Price:
    - Bias:
    - Volatility:
    - Notes:

    Bias must be ONE of:
    - Buy
    - Sell
    - Wait
    """
)

btc_agent = Agent(
    name="BTCAnalyst",
    model=MODEL,
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

root_agent = LlmAgent(
    name="MarketOrchestrator",
    model=MODEL,
    description="I coordinate market analysis for FX, and Crypto.",
    instruction="""
    You are a market orchestrator.

    You MUST delegate work to sub-agents using the tool `transfer_to_agent`.

    Routing rules:
    - If the user mentions BTC or Bitcoin → transfer_to_agent(agent_name="BTCAnalyst")
    - If the user mentions EUR/USD, or Forex → transfer_to_agent(agent_name="FXAnalyst")
    - If both are mentioned → call both agents, then summarize results

    STRICT RULES:
    - Do NOT answer market analysis yourself
    - ALWAYS delegate using transfer_to_agent
    - NEVER invent agent names
    """,
    sub_agents=[fx_agent, btc_agent] 
)
