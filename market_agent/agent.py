import requests
import os
import yfinance as yf
import pandas as pd
import uuid
from google.adk.agents import Agent, LlmAgent
from google.adk.sessions import InMemorySessionService
# from google.adk.apps import App
from google.adk.runners import Runner
from google.genai.types import Content, Part
from dotenv import load_dotenv

load_dotenv()

# Best model for fast iteration
MODEL = "gemini-2.0-flash"
ALPHAVANTAGE_API_KEY = os.environ["ALPHAVANTAGE_API_KEY"]

def fetch_xau_ohlc(limit: int = 200) -> list:
    df = yf.download(
        "GC=F",
        period="1y",
        interval="1d",
        progress=False,
    )

    if df.empty:
        raise RuntimeError("Yahoo Finance returned no XAU/USD data")

    # Handle MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df = df.tail(limit)
    candles = []

    for i in range(len(df)):
        candles.append({
            "open": float(df['Open'].iloc[i]),
            "high": float(df['High'].iloc[i]),
            "low": float(df['Low'].iloc[i]),
            "close": float(df['Close'].iloc[i]),
        })

    return candles

def fetch_fx_ohlc(from_symbol: str, to_symbol: str = "USD", limit: int = 200) -> list:
    resp = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "FX_DAILY",
            "from_symbol": from_symbol,
            "to_symbol": to_symbol,
            "interval": "daily",
            "apikey": ALPHAVANTAGE_API_KEY,
            "outputsize": "compact",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    key = f"Time Series FX (Daily)"
    if key not in data:
        raise RuntimeError(f"Alpha Vantage FX error: {data}")

    series = data[key]

    candles = []
    for _, v in sorted(series.items())[-limit:]:
        candles.append({
            "open": float(v["1. open"]),
            "high": float(v["2. high"]),
            "low": float(v["3. low"]),
            "close": float(v["4. close"]),
        })

    return candles

def fetch_crypto_ohlc(symbol: str, interval: str = "4h", limit: int = 200) -> list:
    resp = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    candles = []
    for k in data:
        candles.append({
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
        })
    return candles

def calculate_ema(values: list[float], period: int) -> float:
    k = 2 / (period + 1)
    ema = values[0]
    for price in values[1:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 2)

def calculate_rsi(values: list[float], period: int = 14) -> float:
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def fetch_crypto_snapshot(symbol: str) -> dict:
    candles = fetch_crypto_ohlc(symbol)
    closes = [c["close"] for c in candles]

    return {
        "symbol": symbol,
        "last_price": closes[-1],
        "ema20": calculate_ema(closes[-20:], 20),
        "ema50": calculate_ema(closes[-50:], 50),
        "rsi14": calculate_rsi(closes),
        "high_recent": max(c["high"] for c in candles[-20:]),
        "low_recent": min(c["low"] for c in candles[-20:]),
    }

def fetch_fx_snapshot(from_symbol: str, to_symbol: str = "USD") -> dict:
    candles = fetch_fx_ohlc(from_symbol, to_symbol)
    closes = [c["close"] for c in candles]

    return {
        "pair": f"{from_symbol}/{to_symbol}",
        "price": closes[-1],
        "ema20": calculate_ema(closes[-20:], 20),
        "ema50": calculate_ema(closes[-50:], 50),
        "rsi14": calculate_rsi(closes),
        "high_recent": max(c["high"] for c in candles[-20:]),
        "low_recent": min(c["low"] for c in candles[-20:]),
    }

def fetch_xau_snapshot() -> dict:
    candles = fetch_xau_ohlc()
    closes = [c["close"] for c in candles]

    return {
        "pair": "XAU/USD",
        "price": closes[-1],
        "ema20": calculate_ema(closes[-20:], 20),
        "ema50": calculate_ema(closes[-50:], 50),
        "rsi14": calculate_rsi(closes),
        "high_recent": max(c["high"] for c in candles[-20:]),
        "low_recent": min(c["low"] for c in candles[-20:]),
    }

xau_agent = Agent(
    name="XAUAnalyst",
    model=MODEL,
    tools=[fetch_xau_snapshot],
    instruction="""
    You are a professional XAU analyst.

    Rules:
    - You MAY call fetch_xau_snapshot when needed
    - Analyze Forex only
    - Use fetched data ONLY
    - Do not invent technical indicators
    - If only spot price is available, limit analysis to:
    - Directional bias
    - Volatility
    - Spread quality

    Interpretation rules:
    - Trend:
    - Bullish if price > EMA20 > EMA50 and RSI > 55
    - Bearish if price < EMA20 < EMA50 and RSI < 45
    - Otherwise Range
    - Volatility:
    - High if price is volatile (high recent range > 10%)
    - Low if price is stable (high recent range < 5%)
    - Spread quality:
    - Good if spread is narrow (less than 1 pip)
    - Bad if spread is wide (more than 10 pips)

    Output format:

    🌅 XAU Outlook

    <XAU PAIR>:
    - Price:
    - EMA20 / EMA50:
    - RSI14:
    - Trend:
    - Bias:
    - Notes:

    Bias must be ONE of:
    - Buy
    - Sell
    - Wait
    """
)

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

    Interpretation rules:
    - Trend:
    - Bullish if price > EMA20 > EMA50 and RSI > 55
    - Bearish if price < EMA20 < EMA50 and RSI < 45
    - Otherwise Range
    - Volatility:
    - High if price is volatile (high recent range > 10%)
    - Low if price is stable (high recent range < 5%)
    - Spread quality:
    - Good if spread is narrow (less than 1 pip)
    - Bad if spread is wide (more than 10 pips)

    Output format:

    🌅 FX Market Outlook

    <FOREX PAIR>:
    - Price:
    - EMA20 / EMA50:
    - RSI14:
    - Trend:
    - Bias:
    - Notes:

    Bias must be ONE of:
    - Buy
    - Sell
    - Wait
    """
)

crypto_agent = Agent(
    name="CryptoAnalyst",
    model=MODEL,
    tools=[fetch_crypto_snapshot],
    instruction="""
    You are a professional crypto technical analyst.

    Supported assets:
    - BTC/USD
    - ETH/USD

    Rules:
    - Detect asset from user query:
    - BTC → symbol BTCUSDT
    - ETH → symbol ETHUSDT
    - Call fetch_crypto_snapshot with the correct symbol
    - Use indicator data ONLY (EMA20, EMA50, RSI14)
    - Do NOT invent indicators

    Interpretation rules:
    - Trend:
    - Bullish if price > EMA20 > EMA50 and RSI > 55
    - Bearish if price < EMA20 < EMA50 and RSI < 45
    - Otherwise Range
    - Volatility:
    - High if price is volatile (high recent range > 10%)
    - Low if price is stable (high recent range < 5%)
    - Spread quality:
    - Good if spread is narrow (less than 1 pip)
    - Bad if spread is wide (more than 10 pips)

    Output format:

    🌅 Crypto Market Outlook

    <ASSET>/USD:
    - Price:
    - EMA20 / EMA50:
    - RSI14:
    - Trend:
    - Bias:
    - Notes:

    Bias must be ONE of:
    - Buy
    - Sell
    - Wait
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
    - If the user mentions BTC, ETH or Crypto → transfer_to_agent(agent_name="CryptoAnalyst")
    - If the user mentions EUR/USD, or Forex → transfer_to_agent(agent_name="FXAnalyst")
    - If the user mentions XAU/USD or XAU or Gold → transfer_to_agent(agent_name="XAUAnalyst")
    - If both are mentioned → call both agents, then summarize results

    STRICT RULES:
    - Do NOT answer market analysis yourself
    - ALWAYS delegate using transfer_to_agent
    - NEVER invent agent names
    """,
    sub_agents=[fx_agent, crypto_agent, xau_agent] 
)

session_service = InMemorySessionService()

runner = Runner(
    agent=root_agent,
    app_name="market_agent",
    session_service=session_service,
)

async def analyze_market(user_input: str) -> str:
    user_id = "http_user"
    session_id = str(uuid.uuid4())
    
    await session_service.create_session(
        app_name="market_agent",
        user_id=user_id,
        session_id=session_id,
    )

    message = Content(parts=[Part(text=user_input)])

    final_text = ""

    for event in runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response():
            for part in getattr(event.content, "parts", []):
                if hasattr(part, "text"):
                    final_text += part.text

    return final_text or "No output from agent"