from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI


from config import prompts, settings
from graph.state import ContentState, ErrorLog


def run(state: ContentState) -> dict:
    """
    LinkedIn Adaptation Agent — converts article into a LinkedIn post.
    Writes to: state["linkedin_post"], state["errors"]
    """
    print("[LinkedInAgent] Generating LinkedIn post...")

    try:
        post = _generate(state["article"], state["audience"])
        print(f"[LinkedInAgent] Post ready ({len(post)} chars).")
        return {"linkedin_post": post}

    except Exception as e:
        error: ErrorLog = {
            "agent": "LinkedInAgent",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        print(f"[LinkedInAgent] Error: {e}")
        return {"errors": [error]}


def _generate(article: str, audience: str) -> str:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        max_output_tokens=4096,
    )

    messages = [
        {"role": "system", "content": prompts.LINKEDIN_SYSTEM},
        {
            "role": "user",
            "content": prompts.LINKEDIN_USER.format(article=article, audience=audience),
        },
    ]

    response = llm.invoke(messages)
    return response.content.strip()