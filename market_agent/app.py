from fastapi import FastAPI
from pydantic import BaseModel
from agent import analyze_market

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
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}, 500