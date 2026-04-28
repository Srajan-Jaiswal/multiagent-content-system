import json

from langchain_tavily import TavilySearch

from agents.base import BaseAgent
from config import prompts, settings
from graph.state import ContentState, ResearchItem
from rag import VectorStore
from utils import _format_tavily_results


class ResearchAgent(BaseAgent):
    """
    Research Agent — searches the web and builds a structured knowledge base.

    Phase 1 (current): Tavily web search only.
    Phase 2 (planned): Add Exa semantic search and merge both result sets.

    Writes to: state["research"], state["status"], state["errors"]
    """

    def __init__(self):
        super().__init__(
            name="research_agent",
            provider=settings.RESEARCH_PROVIDER,
            model=settings.RESEARCH_MODEL,
            token_budget=50_000,
        )

    # ── Public interface ──────────────────────────────────────────────────── #

    def run(self, state: ContentState) -> dict:
        self._tokens_used = 0  # reset per pipeline run
        print("[ResearchAgent] Starting research...")

        try:
            raw_results = self._search(state["topic"], state["audience"])
            research_items = self._synthesize(raw_results, state["topic"], state["audience"])

            # L2 — degraded output: fewer items than required, retry with broader query
            if not self._validate_output(research_items):
                print("[ResearchAgent] Too few results, retrying with broader query...")
                raw_results = self._search(state["topic"], audience=None)
                research_items = self._synthesize(raw_results, state["topic"], state["audience"])

            print(f"[ResearchAgent] Collected {len(research_items)} research items. "
                  f"Tokens used: {self._tokens_used:,}")

            stored = self._store_in_vectordb(research_items, state["job_id"])
            print(f"[ResearchAgent] Stored {stored} items in ChromaDB (job={state['job_id']})")

            return {
                "research": research_items,
                "status": "researched",
            }

        except Exception as e:
            print(f"[ResearchAgent] Error: {e}")
            return {
                "errors": [self._error_log(e)],
                "status": "research_failed",
            }

    def _validate_output(self, output: list[ResearchItem]) -> bool:
        if len(output) < settings.MIN_RESEARCH_SOURCES:
            return False
        return all(bool(item.get("source_url", "").strip()) for item in output)

    # ── Internal steps ────────────────────────────────────────────────────── #

    def _search(self, topic: str, audience: str | None) -> str:
        query = f"{topic} for {audience}" if audience else topic

        if settings.USE_MOCK_DATA:
            from tests.mocks import get_mock_results
            print(f"[ResearchAgent] USE_MOCK_DATA=true — skipping live call for query: {query!r}")
            return _format_tavily_results(get_mock_results()["results"])

        tavily = TavilySearch(
            api_key=settings.TAVILY_API_KEY,
            max_results=settings.MIN_RESEARCH_SOURCES,
        )
        results = tavily.invoke(query)
        return _format_tavily_results(results)

    @staticmethod
    def _store_in_vectordb(items: list[ResearchItem], job_id: str) -> int:
        try:
            store = VectorStore()
            return store.store(items, job_id)
        except Exception as e:
            print(f"[ResearchAgent] ChromaDB store failed (non-fatal): {e}")
            return 0

    def _synthesize(self, search_results: str, topic: str, audience: str) -> list[ResearchItem]:
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
        content = self._invoke(messages)
        return json.loads(content)


_agent = ResearchAgent()


def run(state: ContentState) -> dict:
    return _agent.run(state)