# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Setup (Windows, PowerShell):
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run the API locally:
```
uvicorn app.main:app --reload
```
The API listens on `http://127.0.0.1:8000`. The only functional endpoint is `POST /research` with body `{"topic": "..."}`; `GET /` is a health check.

There is no test suite, linter, or formatter configured in this repo.

## Environment

Requires a `.env` file (gitignored) with:
- `GROQ_API_KEY` — used by `ChatGroq` in `app/agent.py`
- `TAVILY_API_KEY` — used by `TavilyClient` in `app/agent.py`

Loaded via `python-dotenv` at import time in `app/agent.py`.

## Architecture

This is a FastAPI service wrapping a LangGraph research agent.

- `app/main.py` — FastAPI app. Single endpoint `POST /research` calls `run_research(topic)` from `app/agent.py` and wraps the result with a measured `latency_ms`.
- `app/agent.py` — defines and runs the LangGraph state machine. Key pieces:
  - `ResearchState` (TypedDict) — the state threaded through the graph: `topic`, `search_results`, `search_queries`, `report`, `searches_done`.
  - Graph nodes: `search_web` (queries Tavily; after the first search, asks the Groq LLM to generate a follow-up query based on `search_queries` already tried) → `analyze` (no-op passthrough; exists only as a place for the conditional edge) → `write_report` (asks the LLM to synthesize all `search_results` into a structured report).
  - `should_continue` — conditional edge function after `analyze`; loops back to `search_web` while `searches_done < 2` and fewer than 6 results have been collected, otherwise proceeds to `write_report`. Change search depth/breadth here.
  - `build_agent()` compiles the graph fresh each call; `run_research(topic)` builds the agent, runs it with a fresh initial state, and returns a plain dict (topic, report, sources_used, searches_done, queries_used).
  - LLM: Groq `llama-3.3-70b-versatile` via `langchain_groq.ChatGroq`. Search: Tavily via `tavily.TavilyClient`, capped at `max_results=3` per call.

## Deployment

`render.yaml` deploys this as a Render web service (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`), expecting `GROQ_API_KEY` and `TAVILY_API_KEY` to be set in the Render dashboard (not synced from a local env file).
