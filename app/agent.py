import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from tavily import TavilyClient

load_dotenv()

# ── Clients ───────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", google_api_key=os.getenv("GEMINI_API_KEY"))
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def response_text(response) -> str:
    """Gemini can return content as a string or a list of content parts (e.g. text + thinking blocks)."""
    content = response.content
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


# ── State — what gets passed between nodes ────────────────────
class ResearchState(TypedDict):
    topic: str                    # user's research topic
    search_results: list          # raw results from Tavily
    search_queries: list          # queries we've tried
    report: str                   # final report
    searches_done: int            # how many searches done


# ── Node 1: Search the web ────────────────────────────────────
def search_web(state: ResearchState) -> ResearchState:
    topic = state["topic"]
    searches_done = state.get("searches_done", 0)
    existing_results = state.get("search_results", [])
    queries_tried = state.get("search_queries", [])

    # Build search query
    if searches_done == 0:
        query = topic
    else:
        # Ask LLM to generate a better follow-up query
        response = llm.invoke([
            SystemMessage(content="Generate a specific search query to find more information. Return ONLY the query, nothing else."),
            HumanMessage(content=f"Topic: {topic}\nAlready searched: {queries_tried}\nWhat should I search next?")
        ])
        query = response_text(response).strip()

    print(f"Searching: {query}")

    # Search Tavily
    results = tavily.search(query=query, max_results=3)
    new_results = results.get("results", [])

    return {
        **state,
        "search_results": existing_results + new_results,
        "search_queries": queries_tried + [query],
        "searches_done": searches_done + 1
    }


# ── Node 2: Analyze results ───────────────────────────────────
def analyze_results(state: ResearchState) -> ResearchState:
    # Just pass state through — decision happens in edge function
    return state


# ── Node 3: Write report ──────────────────────────────────────
def write_report(state: ResearchState) -> ResearchState:
    topic = state["topic"]
    results = state["search_results"]
    
    # Format search results for LLM
    # Format search results for LLM
    context = ""
    for i, r in enumerate(results):
        content = r.get('content', '')[:500]  # ← limit to 500 chars per result
        context += f"\nSource {i+1}: {r.get('title', '')}\n"
        context += f"URL: {r.get('url', '')}\n"
        context += f"Content: {content}\n"
        context += "---\n"

    # Ask LLM to write report
    response = llm.invoke([
        SystemMessage(content="""You are a research analyst. 
Write a comprehensive research report based on the sources provided.
Structure your report with:
1. Executive Summary (2-3 sentences)
2. Key Findings (bullet points)
3. Detailed Analysis (2-3 paragraphs)
4. Sources Used

Base your report ONLY on the provided sources."""),
        HumanMessage(content=f"Topic: {topic}\n\nSources:\n{context}")
    ])

    return {
        **state,
        "report": response_text(response)
    }


# ── Edge: Decide whether to search more or write report ───────
def should_continue(state: ResearchState) -> str:
    searches_done = state.get("searches_done", 0)
    results_count = len(state.get("search_results", []))

    # Simple rule: 2 searches max, at least 3 results needed
    if searches_done < 2 and results_count < 6:
        return "search_more"
    else:
        return "write_report"


# ── Build the graph ───────────────────────────────────────────
def build_agent():
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("search_web", search_web)
    graph.add_node("analyze", analyze_results)
    graph.add_node("write_report", write_report)

    # Add edges
    graph.set_entry_point("search_web")
    graph.add_edge("search_web", "analyze")
    graph.add_conditional_edges(
        "analyze",
        should_continue,
        {
            "search_more": "search_web",
            "write_report": "write_report"
        }
    )
    graph.add_edge("write_report", END)

    return graph.compile()


# ── Run function ──────────────────────────────────────────────
def run_research(topic: str) -> dict:
    agent = build_agent()

    initial_state = {
        "topic": topic,
        "search_results": [],
        "search_queries": [],
        "report": "",
        "searches_done": 0
    }

    final_state = agent.invoke(initial_state)

    return {
        "topic": topic,
        "report": final_state["report"],
        "sources_used": len(final_state["search_results"]),
        "searches_done": final_state["searches_done"],
        "queries_used": final_state["search_queries"]
    }