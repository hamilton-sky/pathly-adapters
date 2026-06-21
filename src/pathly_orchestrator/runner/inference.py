"""Offline summarizer for comms-board artifacts (Phase 4, §1–§2a).

summarize_content  — synchronous, never raises; returns SummaryResult.
summarize_async    — fire-and-forget daemon thread (mirrors embed_async).

.md ONLY (§6.3): every other artifact_type early-returns SummaryResult(None, "none").
Default backend is "minilm" (summarization disabled, no prose generated).
"""

from __future__ import annotations

import logging
import subprocess
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SummaryResult:
    summary: str | None
    backend: str
    cost_usd: float = 0.0
    error: str | None = None


def _resolve_backend(backend: str | None) -> str:
    """Return the effective backend string, reading app_settings when backend is None."""
    if backend is not None:
        return backend
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_summary_backend

        return get_summary_backend(get_db())
    except Exception:
        return "minilm"


def _build_topic_map_prompt(text: str, max_sentences: int) -> str:
    """Build the prompt that asks the model for a topic-map (heading list + gloss)."""
    truncated = text[:8000] if len(text) > 8000 else text
    return (
        f"List the SUBJECTS this Markdown document covers as a compact topic map — "
        f"one line per heading with a short gloss (what that section is about, not its details). "
        f"Maximum {max_sentences} items. Output ONLY the topic-map lines, no preamble.\n\n"
        f"Document:\n{truncated}"
    )


def summarize_content(
    text: str,
    *,
    artifact_type: str = "md",
    backend: str | None = None,
    max_sentences: int = 3,
    timeout: int = 30,
) -> SummaryResult:
    """Generate a topic-map summary of text. Never raises.

    Returns SummaryResult(summary=None, ...) when:
    - artifact_type != "md"  (§6.3 — .md only)
    - backend == "minilm"    (summarization disabled)
    - any backend error      (error field is set)
    """
    # §6.3 — .md ONLY
    if artifact_type != "md":
        return SummaryResult(None, "none")

    effective_backend = _resolve_backend(backend)

    # minilm = summarization disabled; return None, no writeback
    if effective_backend == "minilm":
        return SummaryResult(None, "minilm")

    if effective_backend == "ollama":
        return _run_ollama(text, max_sentences=max_sentences, timeout=timeout)

    if effective_backend == "haiku":
        return _run_haiku(text, max_sentences=max_sentences, timeout=timeout)

    # Unknown backend — treat as disabled
    return SummaryResult(None, effective_backend, error=f"unknown backend: {effective_backend}")


def _run_ollama(text: str, *, max_sentences: int, timeout: int) -> SummaryResult:
    """Call local Ollama HTTP API. Never raises — §6.6."""
    import json as _json

    prompt = _build_topic_map_prompt(text, max_sentences)
    payload = _json.dumps({"model": "llama3.2", "prompt": prompt, "stream": False}).encode()
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = _json.loads(resp.read().decode())
            summary = body.get("response", "").strip() or None
            return SummaryResult(summary, "ollama")
    except Exception as exc:
        return SummaryResult(None, "ollama", error="ollama unreachable")


def _run_haiku(text: str, *, max_sentences: int, timeout: int) -> SummaryResult:
    """Invoke claude-haiku via the CLI subprocess path (§7). Never raises."""
    from pathly_orchestrator.runner.argv import resolve_argv
    from pathly_orchestrator.runner.output import parse_result

    _HAIKU_MODEL = "claude-haiku-4-5-20251001"
    prompt = _build_topic_map_prompt(text, max_sentences)
    try:
        argv = resolve_argv("claude", prompt, _HAIKU_MODEL, interactive=False)
        out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        res = parse_result("claude", out.stdout)
        summary = res.get("result") or None
        if summary is not None:
            summary = summary.strip() or None
        return SummaryResult(summary, "haiku", cost_usd=res.get("cost_usd", 0.0))
    except subprocess.TimeoutExpired:
        return SummaryResult(None, "haiku", error="haiku timeout")
    except Exception as exc:
        return SummaryResult(None, "haiku", error=str(exc))


def summarize_async(
    artifact_id: str,
    message_id: str,
    text: str,
    *,
    artifact_type: str = "md",
    backend: str | None = None,
) -> None:
    """Fire-and-forget: run summarize_content in a daemon thread.

    When a non-None summary is produced, writes it to comms_artifacts.summary.
    Mirrors embed_async exactly — returns instantly. Best-effort: never raises.
    """

    def _worker() -> None:
        try:
            result = summarize_content(
                text,
                artifact_type=artifact_type,
                backend=backend,
            )
            if result.summary is None:
                return
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.comms import update_artifact_summary

            update_artifact_summary(get_db(), artifact_id, result.summary)
        except Exception:
            logger.debug(
                "summarize_async failed for artifact %s", artifact_id, exc_info=True
            )

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
