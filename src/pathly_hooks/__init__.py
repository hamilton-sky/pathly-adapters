"""
Pathly hooks — Claude Code post-tool-call hooks for feedback classification and TTL injection.

These hooks require the Claude Code hook event system and have no equivalent in Codex or Copilot.
"""

from . import classify_feedback, inject_feedback_ttl  # noqa: F401
