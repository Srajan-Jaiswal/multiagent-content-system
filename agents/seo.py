import json
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults

from config import prompts, settings
from graph.state import ContentState, ErrorLog, SEOAnalysis


def run(state: ContentState) -> dict:
    """
    SEO Agent — performs keyword research and competitive analysis.
    Writes to: state["seo_analysis"], state["errors"]
    """
    print("[SEOAgent] Running SEO analysis...")

    try:
        competitor_data = _fetch_competitor_data(state["topic"])
        seo_analysis = _analyze(state["topic"], state["custom_keywords"], competitor_data)

        print(f"[SEOAgent] Primary keyword: {seo_analysis['primary_keyword']}")
        return {"seo_analysis": seo_analysis}

    except Exception as e:
        error: ErrorLog = {
            "agent": "SEOAgent",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        print(f"[SEOAgent] Error: {e}")
        return {"errors": [error]}


def _fetch_competitor_data(topic: str) -> str:
    tavily = TavilySearchResults(
        api_key=settings.TAVILY_API_KEY,
        max_results=10,
    )
    results = tavily.invoke(topic)
    lines = [f"URL: {r.get('url', '')}\nSnippet: {r.get('content', '')}" for r in results]
    return "\n---\n".join(lines)


def _analyze(topic: str, custom_keywords: list[str], competitor_data: str) -> SEOAnalysis:
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        max_output_tokens=2048,
    )

    messages = [
        {"role": "system", "content": prompts.SEO_SYSTEM},
        {
            "role": "user",
            "content": prompts.SEO_USER.format(
                topic=topic,
                custom_keywords=", ".join(custom_keywords) if custom_keywords else "none",
            )
            + f"\n\nCompetitor Data:\n{competitor_data}",
        },
    ]

    response = llm.invoke(messages)
    return json.loads(response.content)
