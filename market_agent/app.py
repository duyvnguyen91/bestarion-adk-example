from fastapi import FastAPI
from pydantic import BaseModel
from agent import analyze_market
from telegram_notify import send_message

app = FastAPI()

class AnalyzeRequest(BaseModel):
    query: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze_endpoint(request: AnalyzeRequest):
    try:
        result = await analyze_market(request.query)
        send_message(f"✅ market_agent\nQuery: {request.query}\nResult: {result}")
        return {"result": result}
    except Exception as e:
        send_message(f"❌ market_agent\nQuery: {request.query}\nError: {e}")
        return {"error": str(e)}, 500