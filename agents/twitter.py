import json
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config import prompts, settings
from graph.state import ContentState, ErrorLog


def run(state: ContentState) -> dict:
    """
    Twitter Adaptation Agent — converts article into a tweet thread.
    Writes to: state["twitter_thread"], state["errors"]
    """
    print("[TwitterAgent] Generating tweet thread...")

    try:
        thread = _generate(state["article"])
        print(f"[TwitterAgent] Thread ready: {len(thread)} tweets.")
        return {"twitter_thread": thread}

    except Exception as e:
        error: ErrorLog = {
            "agent": "TwitterAgent",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        print(f"[TwitterAgent] Error: {e}")
        return {"errors": [error]}


def _generate(article: str) -> list[str]:
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        max_output_tokens=2048,
    )

    messages = [
        {"role": "system", "content": prompts.TWITTER_SYSTEM},
        {"role": "user", "content": prompts.TWITTER_USER.format(article=article)},
    ]

    response = llm.invoke(messages)
    return json.loads(response.content)