"""Shared Blueprint object and helpers for the runner API routes."""

from flask import Blueprint

bp = Blueprint("runner", __name__)


def _topic_from_body(data: dict) -> str | None:
    topic = data.get("topic", "")
    return topic if isinstance(topic, str) and topic.strip() else None
