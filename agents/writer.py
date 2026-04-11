import json
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config import prompts, settings
from graph.state import ContentState, ErrorLog


def run(state: ContentState) -> dict:
    """
    Writing Agent — produces the full long-form article using Claude Opus.
    Writes to: state["article"], state["meta_description"], state["errors"]
    """
    print("[WriterAgent] Writing article (Gemini)...")

    try:
        article, meta_description = _write(state)
        word_count = len(article.split())
        print(f"[WriterAgent] Article written. Word count: {word_count}")
        return {
            "article": article,
            "meta_description": meta_description,
            "status": "written",
        }

    except Exception as e:
        error: ErrorLog = {
            "agent": "WriterAgent",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        print(f"[WriterAgent] Error: {e}")
        return {"errors": [error], "status": "writing_failed"}


def _write(state: ContentState) -> tuple[str, str]:
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        max_output_tokens=8192,
    )

    research_text = "\n".join(
        f"- {item['fact']} ({item['source_url']})" for item in state["research"]
    )
    seo = state["seo_analysis"]

    messages = [
        {"role": "system", "content": prompts.WRITER_SYSTEM},
        {
            "role": "user",
            "content": prompts.WRITER_USER.format(
                topic=state["topic"],
                audience=state["audience"],
                tone=state["tone"],
                word_count=state["word_count_target"],
                brand_guidelines=state["brand_guidelines"] or "None",
                strategy=json.dumps(state["strategy"], indent=2),
                research=research_text,
                primary_keyword=seo["primary_keyword"],
                secondary_keywords=", ".join(seo["secondary_keywords"]),
            ),
        },
    ]

    response = llm.invoke(messages)
    content = response.content

    # Parse META_DESCRIPTION separator written by the LLM
    if "META_DESCRIPTION:" in content:
        parts = content.split("META_DESCRIPTION:", 1)
        article = parts[0].strip()
        meta_description = parts[1].strip()
    else:
        article = content.strip()
        meta_description = ""

    return article, meta_description