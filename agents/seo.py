import json
from typing import Any

from langchain_tavily import TavilySearch

from agents.base import BaseAgent
from config import prompts, settings
from graph.state import ContentState, SEOAnalysis
from utils import _format_tavily_results


class SEOAgent(BaseAgent):
    """
    SEO Agent — performs keyword research and competitive analysis.
    Writes to: state["seo_analysis"], state["errors"]
    """

    def __init__(self):
        super().__init__(
            name="seo_agent",
            provider=settings.SEO_PROVIDER,
            model=settings.SEO_MODEL,
            token_budget=30_000,
        )

    # ── Public interface ──────────────────────────────────────────────────── #

    def run(self, state: ContentState) -> dict:
        self._tokens_used = 0
        print("[SEOAgent] Running SEO analysis...")

        try:
            competitor_data = self._fetch_competitor_data(state["topic"])
            seo_analysis = self._analyze(state["topic"], state["custom_keywords"], competitor_data)

            print(f"[SEOAgent] Primary keyword: {seo_analysis['primary_keyword']}")
            return {"seo_analysis": seo_analysis}

        except Exception as e:
            print(f"[SEOAgent] Error: {e}")
            return {"errors": [self._error_log(e)]}

    def _validate_output(self, output: Any) -> bool:
        return bool(output.get("primary_keyword"))

    # ── Internal steps ────────────────────────────────────────────────────── #

    def _fetch_competitor_data(self, topic: str) -> str:
        if settings.USE_MOCK_TAVILY:
            from tests.mocks import MOCK_TAVILY_RESULTS
            print(f"[ResearchAgent] USE_MOCK_TAVILY=true — skipping live call for query: {query!r}")
            return _format_tavily_results(MOCK_TAVILY_RESULTS["results"])

        tavily = TavilySearch(
            api_key=settings.TAVILY_API_KEY,
            max_results=10,
        )
        results = tavily.invoke(topic)
        return _format_tavily_results(results)

    def _analyze(self, topic: str, custom_keywords: list[str], competitor_data: str) -> SEOAnalysis:
        messages = [
            {"role": "system", "content": prompts.SEO_SYSTEM},
            {
                "role": "user",
                "content": prompts.SEO_USER.format(
                    topic=topic,
                    custom_keywords=", ".join(custom_keywords) if custom_keywords else "none",
                ) + f"\n\nCompetitor Data:\n{competitor_data}",
            },
        ]
        content = self._invoke(messages)
        return json.loads(content)


_agent = SEOAgent()


def run(state: ContentState) -> dict:
    return _agent.run(state)