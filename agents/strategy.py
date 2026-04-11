import json
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config import prompts, settings
from graph.state import ContentState, ContentStrategy, ErrorLog


def run(state: ContentState) -> dict:
    """
    Strategy Agent — creates content angle, key messages, and article outline.
    Writes to: state["strategy"], state["errors"]
    """
    print("[StrategyAgent] Building content strategy...")

    try:
        research_summary = _summarize_research(state["research"])
        strategy = _create_strategy(state, research_summary)

        print(f"[StrategyAgent] Strategy ready. Angle: {strategy['content_angle'][:60]}...")
        return {"strategy": strategy}

    except Exception as e:
        error: ErrorLog = {
            "agent": "StrategyAgent",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        print(f"[StrategyAgent] Error: {e}")
        return {"errors": [error]}


def _summarize_research(research: list) -> str:
    return "\n".join(
        f"- {item['fact']} (source: {item['source_url']}, reliability: {item['reliability_score']})"
        for item in research
    )


def _create_strategy(state: ContentState, research_summary: str) -> ContentStrategy:
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        max_output_tokens=2048,
    )

    messages = [
        {"role": "system", "content": prompts.STRATEGY_SYSTEM},
        {
            "role": "user",
            "content": prompts.STRATEGY_USER.format(
                topic=state["topic"],
                audience=state["audience"],
                tone=state["tone"],
                research_summary=research_summary,
                seo_analysis=json.dumps(state["seo_analysis"], indent=2),
            ),
        },
    ]

    response = llm.invoke(messages)
    return json.loads(response.content)
