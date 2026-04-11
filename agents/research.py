import json
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from tenacity import retry, stop_after_attempt, wait_exponential

from config import prompts, settings
from graph.state import ContentState, ErrorLog, ResearchItem


def run(state: ContentState) -> dict:
    """
    Research Agent — searches the web and builds a structured knowledge base.
    Writes to: state["research"], state["status"], state["errors"]
    """
    print("[ResearchAgent] Starting research...")

    try:
        raw_results = _search(state["topic"], state["audience"])
        research_items = _synthesize(raw_results, state["topic"], state["audience"])

        print(f"[ResearchAgent] Collected {len(research_items)} research items.")
        return {
            "research": research_items,
            "status": "researched",
        }

    except Exception as e:
        error: ErrorLog = {
            "agent": "ResearchAgent",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        print(f"[ResearchAgent] Error: {e}")
        return {"errors": [error], "status": "research_failed"}


@retry(stop=stop_after_attempt(settings.MAX_RETRIES), wait=wait_exponential(multiplier=1, min=2, max=10))
def _search(topic: str, audience: str) -> str:
    """Run Tavily search and return raw results as a formatted string."""
    tavily = TavilySearchResults(
        api_key=settings.TAVILY_API_KEY,
        max_results=settings.MIN_RESEARCH_SOURCES,
    )
    results = tavily.invoke(f"{topic} for {audience}")

    # Flatten into a readable block for the LLM
    formatted = []
    for r in results:
        formatted.append(f"URL: {r.get('url', 'N/A')}\nContent: {r.get('content', '')}\n")
    return "\n---\n".join(formatted)


def _synthesize(search_results: str, topic: str, audience: str) -> list[ResearchItem]:
    """Ask Claude Sonnet to extract and structure research items from raw search results."""


    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        max_output_tokens=8192,
    )

    messages = [
        {"role": "system", "content": prompts.RESEARCH_SYSTEM},
        {
            "role": "user",
            "content": prompts.RESEARCH_USER.format(
                topic=topic,
                audience=audience,
                search_results=search_results,
                min_sources=settings.MIN_RESEARCH_SOURCES,
            ),
        },
    ]

    response = llm.invoke(messages)
    content = response.content.strip()
    # Strip markdown code fences that LLMs sometimes add despite instructions
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()
    return json.loads(content)