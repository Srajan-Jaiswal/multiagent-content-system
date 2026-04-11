from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config import prompts, settings
from graph.state import ContentState, ErrorLog


def run(state: ContentState) -> dict:
    """
    YouTube Adaptation Agent — converts article into a video script.
    Writes to: state["youtube_script"], state["errors"]
    """
    print("[YouTubeAgent] Generating YouTube script...")

    try:
        script = _generate(state["article"])
        print(f"[YouTubeAgent] Script ready ({len(script.split())} words).")
        return {"youtube_script": script}

    except Exception as e:
        error: ErrorLog = {
            "agent": "YouTubeAgent",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        print(f"[YouTubeAgent] Error: {e}")
        return {"errors": [error]}


def _generate(article: str) -> str:
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        max_output_tokens=4096,
    )

    messages = [
        {"role": "system", "content": prompts.YOUTUBE_SYSTEM},
        {"role": "user", "content": prompts.YOUTUBE_USER.format(article=article)},
    ]

    response = llm.invoke(messages)
    return response.content.strip()