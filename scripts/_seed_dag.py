"""One-shot script: seed comms board DAG for unified-cli-composition Gate 2."""
import json, urllib.request, urllib.error

BASE = "http://127.0.0.1:8765"
FEATURE = "unified-cli-composition"


def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


# Step 1 — post goal message
goal_resp = post("/comms/post", {
    "feature": FEATURE,
    "from": "planner",
    "type": "goal",
    "text": (
        "Gate 2: unified-cli-composition — deliver board-connected fragment pair "
        "(board-start-context, task-dag-post), convert Decompose to compose_skill(), "
        "extract build_adapter_caps() helper, and normalize Summary ActionPill error state. "
        "3 conversations. Gate 1 complete. Gate 3 deferred."
    ),
})
goal_id = goal_resp.get("id") or goal_resp.get("message_id")
print(f"goal posted: id={goal_id}")

# Step 2 — three task messages
tasks = [
    {
        "title": "Conv 1 — Error normalization + new fragments + manifest entry",
        "text": (
            "Build Gate 2 Phase 1 for unified-cli-composition.\n\n"
            "What to build:\n"
            "1. Summary ActionPill error state (US-01): extend useEditorAgentActions.ts "
            "(or skillCompose.ts) so that an ERROR: prefix in the Summary output file sets "
            "ActionPill state='error' with the error text visible. Analyze/Split must be unaffected.\n"
            "2. board-start-context.md fragment (US-02): new file at "
            "src/pathly_data/core/skills/fragments/board-start-context.md. Instructs agent to "
            "call GET /comms/retrieve?scope={scope}&goal_id={goal_id}&limit=10 as read-only preamble. "
            "Skip silently when goal_id absent. Skip-if-down advisory. "
            "Extend compose.py: add goal_id to _KNOWN_CAPABILITIES, update adapter_caps_for().\n"
            "3. task-dag-post.md fragment (US-03): new file at "
            "src/pathly_data/core/skills/fragments/task-dag-post.md. Instructs agent to "
            "POST /comms/post with type: 'task'. Full payload template (title, description, goal_id, "
            "parent_id, depends_on, executor, kind). Gated on goal_id. Skip-if-down advisory.\n"
            "4. planning/plan manifest entry (US-04): add to composition.yaml with both new fragments "
            "gated on goal_id. Use blocks: key (no profiles: rename).\n\n"
            "Files: studio/src/renderer/src/hooks/useEditorAgentActions.ts, "
            "src/pathly_data/core/skills/fragments/board-start-context.md (new), "
            "src/pathly_data/core/skills/fragments/task-dag-post.md (new), "
            "src/pathly_data/core/skills/composition.yaml, "
            "src/pathly_orchestrator/skills/compose.py.\n\n"
            "Done when: POST /skills/compose with goal_id returns prompt containing both fragment bodies; "
            "same call without goal_id excludes both. Summary pill shows error state for ERROR: output. "
            "Analyze/Split error states unaffected."
        ),
        "stories": ["US-01", "US-02", "US-03", "US-04"],
    },
    {
        "title": "Conv 2 — Decompose conversion to compose_skill()",
        "text": (
            "Build Gate 2 Phase 2 for unified-cli-composition.\n\n"
            "Prerequisite: Conv 1 complete. Both new fragments validated in isolation via "
            "manual POST /skills/compose calls before touching goal_decomposer.py.\n\n"
            "What to build:\n"
            "1. Baseline capture (US-07 pre): before modifying any Python, run a Decompose on a "
            "reference goal. Record task count, titles, dependency links, executor values as a "
            "code comment in goal_decomposer.py.\n"
            "2. Convert _decompose_planner() and _decompose_plan() (US-05, US-06, US-08): "
            "replace inline prompt string in both functions with compose_skill('planning/plan', "
            "build_adapter_caps(ctx), manifest). Remove stdout-tail / result.text parsing; "
            "read result from AGENT_DONE.summary in EVENTS.jsonl. Add goal_id, executor, kind "
            "to PHASE_START event metadata. Do NOT touch _decompose_consultation().\n"
            "3. DAG equivalence verification (US-07): run the same reference goal through the "
            "new path. Compare against baseline. Document equivalence before removing old code.\n\n"
            "Files: src/pathly_orchestrator/supervisor/goal_decomposer.py.\n\n"
            "Done when: neither _decompose_planner nor _decompose_plan contains an inline prompt "
            "string. AGENT_DONE.summary is the only result-capture mechanism. PHASE_START event "
            "contains goal_id, executor, kind. Task DAG equivalent to baseline."
        ),
        "stories": ["US-05", "US-06", "US-07", "US-08"],
    },
    {
        "title": "Conv 3 — build_adapter_caps() helper + Gate 2 smoke test",
        "text": (
            "Build Gate 2 Phase 3 for unified-cli-composition.\n\n"
            "Prerequisite: Conv 2 complete.\n\n"
            "What to build:\n"
            "1. Extract build_adapter_caps(ctx) helper (US-09): add function to compose.py "
            "returning at minimum {can_spawn, goal_id, executor, kind}. Update editor_render.py "
            "and goal_decomposer.py to call build_adapter_caps(ctx) instead of constructing "
            "adapter_caps inline. Verify: grep for 'adapter_caps = {' in src/pathly_orchestrator/ "
            "returns no results.\n"
            "2. Gate 2 smoke test (US-10 verified): add a test fragment entry to planning/plan in "
            "composition.yaml, POST /skills/compose with goal_id, confirm test fragment body in output, "
            "remove test entry, confirm it is gone.\n"
            "3. Update PROGRESS.md: mark all three conversations DONE.\n\n"
            "Files: src/pathly_orchestrator/skills/compose.py, "
            "src/pathly_orchestrator/blueprints/skills/editor_render.py, "
            "src/pathly_orchestrator/supervisor/goal_decomposer.py, "
            "src/pathly_data/core/skills/composition.yaml (smoke test only), "
            "pathly/plans/unified-cli-composition/PROGRESS.md.\n\n"
            "Done when: no inline adapter_caps dict at call sites. Declarative fragment round-trip "
            "verified. PROGRESS.md shows all three conversations DONE."
        ),
        "stories": ["US-09", "US-10"],
    },
]

for t in tasks:
    resp = post("/comms/post", {
        "feature": FEATURE,
        "from": "planner",
        "type": "task",
        "goal_id": goal_id,
        "text": t["text"],
        "title": t["title"],
        "options": {"stories": t["stories"]},
    })
    task_id = resp.get("id") or resp.get("message_id")
    print(f"task posted: {t['title']!r}  id={task_id}")

print("Done.")
