from flask import request

from pathly_orchestrator.chat_agent import handle_chat
from pathly_orchestrator.http_server import app


def _call_chat(payload: dict):
    with app.test_request_context("/chat", method="POST", json=payload):
        return handle_chat(request)


def test_pathly_studio_chat_is_plan_aware():
    response = _call_chat(
        {
            "text": "what should I do next?",
            "context": {
                "source": "pathly-studio",
                "appContext": {
                    "activeFeature": "brightsky-studio-wire",
                    "fsmStage": "BUILDING",
                    "activeConversation": 2,
                    "nextUncompletedStory": "Build backend PathlyModule",
                    "userStoriesSummary": "summary",
                },
            },
        }
    )

    data = response.get_json()
    assert data["type"] == "chat"
    assert "brightsky-studio-wire" in data["text"]
    assert "BUILDING" in data["text"]
    assert "Build backend PathlyModule" in data["text"]


def test_generic_chat_remains_unchanged():
    response = _call_chat(
        {
            "text": "hello there",
            "context": {
                "skills": ["plan", "build"],
                "studioSchema": [],
            },
        }
    )

    data = response.get_json()
    assert data == {"type": "chat", "text": "Routing to: plan"}
