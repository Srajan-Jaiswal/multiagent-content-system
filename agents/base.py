from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from graph.state import ContentState, ErrorLog


class TokenBudgetExceededError(Exception):
    pass


class BaseAgent(ABC):
    """
    Abstract base class for all pipeline agents.

    Provides:
    - LLM initialisation with model + token budget configuration
    - Token-usage tracking with a hard per-agent budget (L1 enforcement)
    - Exponential-backoff retry on every LLM call (L1 transient errors)
    - Markdown code-fence stripping on every LLM response
    - Structured ErrorLog output on failure
    - Abstract _validate_output() hook each subclass must implement

    Error levels handled here:
      L1 — Transient (rate limit, timeout): retried automatically via tenacity
      L3 — Agent failure: caught in run(), returned as ErrorLog entry

    Subclasses are responsible for L2 (degraded output retry with stricter prompt).

    NOTE: For the WriterAgent using Claude Opus in production, override __init__
    and swap self.llm for ChatAnthropic(model="claude-opus-4-6", ...).
    """

    def __init__(self, name: str, model: str, token_budget: int, max_output_tokens: int = 8192):
        self.name = name
        self.token_budget = token_budget
        self._tokens_used: int = 0

        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
            max_output_tokens=max_output_tokens,
        )

    # ── Public interface ──────────────────────────────────────────────────── #

    @abstractmethod
    def run(self, state: ContentState) -> dict:
        """
        Execute the agent logic. Must return a dict containing only the
        ContentState fields this agent writes — LangGraph merges it into state.

        Subclasses should reset self._tokens_used = 0 at the top of run()
        so token budgets are per-pipeline-run, not cumulative across runs.
        """
        ...

    @abstractmethod
    def _validate_output(self, output: Any) -> bool:
        """
        Return True if the output meets quality requirements.
        Return False to signal an L2 degraded output — the subclass should
        retry once with a stricter prompt before accepting partial output.
        """
        ...

    # ── LLM invocation ────────────────────────────────────────────────────── #

    def _invoke(self, messages: list[dict]) -> str:
        """
        Single entry point for all LLM calls. Handles:
        - Budget check before invoking
        - Exponential-backoff retry (via tenacity)
        - Token usage tracking after response
        - Markdown code-fence stripping

        Returns the plain text content of the LLM response.
        Raises TokenBudgetExceededError if the agent has exhausted its budget.
        """
        self._check_budget()
        response = self._invoke_with_retry(messages)
        self._track_usage(response)
        return self._strip_fences(response.content.strip())

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    def _invoke_with_retry(self, messages: list[dict]):
        """Raw LLM call wrapped with tenacity retry for L1 transient errors."""
        return self.llm.invoke(messages)

    # ── Token budget ─────────────────────────────────────────────────────── #

    def _check_budget(self) -> None:
        if self._tokens_used >= self.token_budget:
            raise TokenBudgetExceededError(
                f"[{self.name}] Token budget of {self.token_budget:,} exhausted "
                f"({self._tokens_used:,} used)."
            )

    def _track_usage(self, response) -> None:
        usage = getattr(response, "usage_metadata", None) or {}
        self._tokens_used += usage.get("total_tokens", 0)

    @property
    def tokens_used(self) -> int:
        return self._tokens_used

    # ── Error handling ────────────────────────────────────────────────────── #

    def _error_log(self, error: Exception) -> ErrorLog:
        return {
            "agent": self.name,
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── Utilities ─────────────────────────────────────────────────────────── #

    @staticmethod
    def _strip_fences(content: str) -> str:
        """
        Remove markdown code fences LLMs add despite 'Return only JSON' instructions.
        Handles both ```json ... ``` and ``` ... ``` variants.
        """
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0].strip()
        return content