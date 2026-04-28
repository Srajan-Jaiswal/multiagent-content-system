import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from config.llm_factory import get_llm
from graph.state import ContentState, ErrorLog


class TokenBudgetExceededError(Exception):
    pass


class BaseAgent(ABC):
    """
    Abstract base class for all pipeline agents.

    Provides:
    - LLM initialisation via LLM factory (provider-agnostic)
    - Token-usage tracking with a hard per-agent budget
    - Exponential-backoff retry on every LLM call (L1 transient errors)
    - Markdown code-fence stripping on every LLM response
    - Structured ErrorLog output on failure
    - Abstract _validate_output() hook each subclass must implement

    Error levels handled here:
      L1 — Transient (rate limit, timeout): retried automatically via tenacity
      L3 — Agent failure: caught in run(), returned as ErrorLog entry

    Subclasses are responsible for L2 (degraded output retry with stricter prompt).
    """

    def __init__(
        self,
        name: str,
        model: str,
        token_budget: int,
        max_output_tokens: int = 8192,
        provider: str | None = None,
    ):
        """
        Args:
            name:              Agent identifier used in logs and ErrorLog entries
            model:             Model name (e.g. "gemini-2.5-flash", "claude-opus-4-6")
            token_budget:      Hard token limit for this agent per pipeline run
            max_output_tokens: Max tokens the model may generate per call
            provider:          LLM provider ("gemini" | "anthropic" | "groq").
                               Defaults to settings.DEFAULT_LLM_PROVIDER.
        """
        self.name = name
        self.token_budget = token_budget
        self._tokens_used: int = 0

        resolved_provider = provider or settings.DEFAULT_LLM_PROVIDER
        self.llm = get_llm(
            provider=resolved_provider,
            model=model,
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
        Extract clean JSON from LLM responses that may contain:
        - <think>...</think> reasoning blocks (Qwen/R1-style models)
        - Markdown code fences (```json ... ```)
        - Preamble text before the JSON
        - Trailing text after the JSON

        Strategy:
        1. Remove <think>...</think> reasoning blocks
        2. If ``` fences are present, extract content between them
        3. Otherwise, pick whichever of { or [ appears first and slice to its matching close
        """
        # Step 1: strip reasoning blocks emitted by Qwen / R1-family models
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # Step 2: strip ``` fences wherever they appear
        if "```" in content:
            start = content.find("```")
            end = content.rfind("```")
            if start != end:
                inner = content[start + 3:end]
                if inner.startswith("json"):
                    inner = inner[4:]
                content = inner.strip()

        # Step 3: extract JSON by picking whichever delimiter opens first
        obj_start = content.find('{')
        arr_start = content.find('[')
        candidates = [(i, c) for i, c in [(obj_start, '}'), (arr_start, ']')] if i != -1]
        if candidates:
            start, close_ch = min(candidates, key=lambda x: x[0])
            end = content.rfind(close_ch)
            if end != -1 and start < end:
                return content[start:end + 1]

        return content.strip()