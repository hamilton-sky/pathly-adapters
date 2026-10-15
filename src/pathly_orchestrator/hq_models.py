"""HQ model eligibility (hq-copilot ticket 05).

A model that cannot hold the packet would silently drop board facts, so HQ
refuses unsuitable models instead of degrading quietly. Fail closed: an
unknown model id is ineligible until added to the table below.

Context windows are the models' native architecture limits. Studio's model
catalog (studio/src/main/ipc/llm.ts MODEL_REGISTRY) declares no context
limits — this table is the first place they are pinned for HQ. It is
conservative: node-llama-cpp may load with a smaller effective n_ctx, so
eligibility additionally requires 2*budget+4000 tokens of headroom.
"""

from __future__ import annotations

MODEL_CONTEXT_WINDOWS = {
    "qwen3-4b": 32768,
    "qwen3-8b": 32768,
    "qwen2.5-coder-7b": 32768,
    "phi-4-mini": 128000,
    "deepseek-r1-1.5b": 128000,
}


def hq_default_model() -> str:
    """The configured HQ model id (hq.default_model, default qwen3-8b)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.hq_settings import get_hq_default_model

    return get_hq_default_model(get_db())


def hq_budget_tokens() -> int:
    """The configured HQ packet budget (hq.context_budget_tokens, default 6000)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.hq_settings import get_hq_budget_tokens

    return get_hq_budget_tokens(get_db())


def hq_required_context(budget_tokens: int) -> int:
    """Context tokens an HQ turn needs: the packet, prompt and answer headroom.

    2*budget covers the chars/4 estimate undercounting real tokenization (ids
    and paths tokenize poorly); +4000 is the system prompt, the message and
    the answer. The same number gates eligibility and is the context size
    Studio requests from the runtime (Ollama's ``num_ctx``, node-llama-cpp's
    minimum context), so the two can never disagree.
    """
    return 2 * budget_tokens + 4000


def hq_eligible(model_id: str, budget_tokens: int | None = None) -> bool:
    """True when the model's known context window holds an HQ turn:
    window >= hq_required_context(budget).

    Unknown model ids are ineligible (fail closed). ``budget_tokens``
    overrides the configured budget (tests).
    """
    window = MODEL_CONTEXT_WINDOWS.get(model_id or "")
    if window is None:
        return False
    if budget_tokens is None:
        budget_tokens = hq_budget_tokens()
    return window >= hq_required_context(budget_tokens)
