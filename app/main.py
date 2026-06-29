import os
import time
from fastapi import FastAPI
from pydantic import BaseModel
from app.agent import run_research

app = FastAPI(title="Research Agent API")


class ResearchRequest(BaseModel):
    topic: str


class ResearchResponse(BaseModel):
    topic: str
    report: str
    sources_used: int
    searches_done: int
    queries_used: list
    latency_ms: int


@app.get("/")
def root():
    return {"status": "Research Agent API is running"}


@app.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest):
    start_time = time.time()

    result = run_research(request.topic)

    latency_ms = round((time.time() - start_time) * 1000)

    return ResearchResponse(
        topic=result["topic"],
        report=result["report"],
        sources_used=result["sources_used"],
        searches_done=result["searches_done"],
        queries_used=result["queries_used"],
        latency_ms=latency_ms
    )