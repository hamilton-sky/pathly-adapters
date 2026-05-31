"""Heuristic chat agent for the Conductor panel.

Handles /chat POST requests from Studio. Returns automation plans or skill routing
responses without requiring an LLM — WebLLM integration is Conv 9.
"""

from __future__ import annotations

import re
import uuid

from flask import jsonify, make_response, Response


_AUTOMATION_PATTERN = re.compile(
    r"\b(create|make|build|add|new)\b",
    re.IGNORECASE,
)

_FLOW_PATTERN = re.compile(
    r"\b(flow|step|state|transition)\b",
    re.IGNORECASE,
)

_NEXT_STEP_PATTERN = re.compile(
    r"\b(what should i do next|what do i do next|next step|next steps|what's next)\b",
    re.IGNORECASE,
)


def _is_automation_intent(text: str) -> bool:
    return bool(_AUTOMATION_PATTERN.search(text) and _FLOW_PATTERN.search(text))


def _extract_labels(studio_schema: list[dict]) -> list[str]:
    labels = []
    for el in studio_schema:
        label = el.get("label", "")
        if label:
            labels.append(label)
    return labels


def _generate_steps(text: str, labels: list[str]) -> list[dict]:
    """Generate a deterministic action plan from text + schema labels."""
    steps: list[dict] = []

    # Step 1: navigate to the appropriate screen
    nav_label = "Flow Canvas"
    for label in labels:
        if "flow" in label.lower() or "canvas" in label.lower():
            nav_label = label
            break
    steps.append({
        "id": str(uuid.uuid4()),
        "description": f"Navigate to {nav_label}",
        "action": {
            "type": "navigate",
            "label": nav_label,
        },
        "status": "pending",
    })

    # Step 2: click "New Flow" or equivalent button if available
    new_flow_label = None
    for label in labels:
        if "new" in label.lower() and "flow" in label.lower():
            new_flow_label = label
            break
        if "create" in label.lower() and "flow" in label.lower():
            new_flow_label = label
            break
    if not new_flow_label and labels:
        for label in labels:
            if "new" in label.lower() or "create" in label.lower() or "add" in label.lower():
                new_flow_label = label
                break

    if new_flow_label:
        steps.append({
            "id": str(uuid.uuid4()),
            "description": f"Click '{new_flow_label}'",
            "action": {
                "type": "click",
                "label": new_flow_label,
            },
            "status": "pending",
        })

    # Step 3: fill in a flow name if text hints at one
    name_match = re.search(
        r'(?:called|named|name[d]?\s+(?:it\s+)?|title[d]?\s+)["\']?([A-Za-z0-9 _-]+)["\']?',
        text,
        re.IGNORECASE,
    )
    name_label = None
    for label in labels:
        if "name" in label.lower() or "title" in label.lower():
            name_label = label
            break

    if name_label:
        fill_value = name_match.group(1).strip() if name_match else "New Flow"
        steps.append({
            "id": str(uuid.uuid4()),
            "description": f"Enter flow name: '{fill_value}'",
            "action": {
                "type": "fill",
                "label": name_label,
                "value": fill_value,
            },
            "status": "pending",
        })

    # Step 4: confirm/save if a save/confirm button is in schema
    save_label = None
    for label in labels:
        if any(k in label.lower() for k in ("save", "confirm", "create", "submit", "ok")):
            save_label = label
            break

    if save_label:
        steps.append({
            "id": str(uuid.uuid4()),
            "description": f"Confirm by clicking '{save_label}'",
            "action": {
                "type": "click",
                "label": save_label,
            },
            "status": "pending",
        })

    # Ensure at least 2 steps
    if len(steps) < 2:
        steps.append({
            "id": str(uuid.uuid4()),
            "description": "Verify result",
            "action": {
                "type": "navigate",
                "label": labels[0] if labels else "Home",
            },
            "status": "pending",
        })

    return steps


def _extract_intent(text: str) -> str:
    """Summarise the intent in a short human-readable phrase."""
    text_stripped = text.strip().rstrip(".")
    if len(text_stripped) <= 60:
        return text_stripped.capitalize()
    words = text_stripped.split()
    return " ".join(words[:10]).capitalize() + "..."


def _build_pathly_reply(text: str, context: dict) -> str:
    app_context: dict = context.get("appContext") or {}
    feature = app_context.get("activeFeature") or ""
    stage = app_context.get("fsmStage") or "unknown"
    conversation = app_context.get("activeConversation")
    next_story = app_context.get("nextUncompletedStory") or ""
    stories = app_context.get("userStoriesSummary") or ""

    if feature:
        intro = f"You are working on **{feature}** at stage **{stage}**."
        if conversation is not None:
            intro += f" Conversation {conversation}."
        if _NEXT_STEP_PATTERN.search(text):
            if next_story:
                return f"{intro} Next: {next_story}"
            return f"{intro} Continue with the current plan."
        if stories:
            return f"{intro} Plan context is available."
        return f"{intro} Continue with the current plan."

    return "I can help you with your Pathly workflow. Try asking me what should I do next."


def handle_chat(request) -> Response:
    """Handle POST /chat.

    Request body: { text, context, mode?, studioSchema? }
    Returns JSON (not SSE).
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return make_response(jsonify({"error": "Invalid JSON body"}), 400)

    text: str = data.get("text") or data.get("message") or ""
    context: dict = data.get("context") or {}
    mode: str = data.get("mode") or "chat"
    studio_schema: list = data.get("studioSchema") or context.get("studioSchema") or []

    is_automation = mode == "automation" or _is_automation_intent(text)

    if is_automation:
        labels = _extract_labels(studio_schema)
        steps = _generate_steps(text, labels)
        intent = _extract_intent(text)
        return jsonify({"type": "automation", "intent": intent, "steps": steps})

    if context.get("source") == "pathly-studio" or data.get("messageType") == "pathly_chat":
        return jsonify({"type": "chat", "text": _build_pathly_reply(text, context)})

    # Chat / skill routing response
    skills: list[str] = context.get("skills") or []
    matched_skill = data.get("matchedSkill") or ""

    if matched_skill:
        reply = f"Routing to: **{matched_skill}**"
    elif skills:
        reply = f"Routing to: {skills[0]}"
    else:
        reply = "I can help you with your Pathly workflow. Try asking me to create a flow or run a skill."

    return jsonify({"type": "chat", "text": reply})
