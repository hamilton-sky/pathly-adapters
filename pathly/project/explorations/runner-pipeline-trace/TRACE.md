# Trace — runner-pipeline-trace

## Files visited

| File | Lines | Finding |
|---|---|---|
| `src/pathly_orchestrator/http_server.py` | 541–577 | `/next_action` endpoint delegates to `next_action(data)` from `fsm_ops.py` |
| `src/pathly_orchestrator/fsm_ops.py` | 83–512 | `build_prompt()`, `_load_agent_text()`, `_agent_hint()`, full `next_action()` function |
| `src/pathly_orchestrator/fsm.py` | 1–81 | `recover_state()`, transition rules, gate evaluation |
| `src/pathly_data/core/flows/team.flow.yaml` | 1–116 | `agent_map: BUILDING: team/build`; all pipeline states, transitions, gates |
| `src/pathly_orchestrator/supervisor.py` | 1–810 | `_loop()` calls FSM, extracts `instructions`, calls `_run_stage_via_terminal()` |
| `src/pathly_orchestrator/runner.py` | 36–52 | `resolve_argv()` calls `resolve_command()` from adapters.py |
| `src/pathly_orchestrator/adapters.py` | 1–73 | `resolve_command()` reads `core/adapters.yaml`; builds final argv |
| `src/pathly_data/core/adapters.yaml` | 1–18 | claude: `claude -p {prompt} --model {model} --output-format json` |
| `src/pathly_data/core/skills/team/build.md` | 1–146 | The `team/build` skill — the actual prompt body sent to Claude |
| `src/pathly_data/core/agents/building/builder.md` | 1–128 | The `builder` role contract |
| `pathly/plans/chat-stop-proxy/CONVERSATION_PROMPTS.md` | 1–60 | Sample per-conversation prompt text |

---

## Code path — "runner calls next_action for BUILDING stage → claude receives exact text"

### Step 1 — Runner loop calls FSM

The runner is either the **supervised runner** (`supervisor.py/_loop()`) started via
`POST /runner/start`, or the legacy CLI runner (`runner.py/run_flow()`).
In both cases the first action in each loop iteration is:

```python
# supervisor.py:291
response = fhc.next_action({"flow": flow, "topic": topic, "project_root": project_root})
```

`flow` is always `"team"` for the normal pipeline (set at runner start from `data["flow"]`
in `http_server.py:948`).

---

### Step 2 — HTTP server → fsm_ops.next_action

`http_server.py:571`:
```python
result = next_action(data)   # data = {"flow": "team", "topic": "<feature>", "project_root": "..."}
```

---

### Step 3 — fsm_ops.next_action builds instructions

`fsm_ops.py:386–512`. Key lines when state is BUILDING and no feedback is open:

```python
# fsm_ops.py:391–392
flow_config = _load_flow(flow_name)          # loads team.flow.yaml
storage_path = _resolve_storage_path(...)    # → pathly/plans/<feature>/

# fsm_ops.py:500
instructions = build_prompt(flow_config, state_info["current_state"], storage_path)
# state_info["current_state"] == "BUILDING"

# fsm_ops.py:501
agent = flow_config["agent_map"][state_info["current_state"]]
# agent_map["BUILDING"] == "team/build"   (from team.flow.yaml:38)
```

---

### Step 4 — build_prompt constructs the instructions string

`fsm_ops.py:101–110`:

```python
def build_prompt(flow_config: dict, state_name: str, storage_path: Path) -> str:
    agent = flow_config["agent_map"][state_name]   # "team/build"
    agent_text = _load_agent_text(agent)           # reads core/skills/team/build.md
    context = (
        f"\n\n## Current task\n"
        f"Feature: {storage_path.name}\n"         # e.g. "chat-stop-proxy"
        f"State: {state_name}\n"                  # "BUILDING"
        f"Storage path: {storage_path}\n"
    )
    return agent_text + context
```

---

### Step 5 — _load_agent_text: how "team/build" is resolved

`fsm_ops.py:83–98`:

```python
def _load_agent_text(agent: str) -> str:
    if "/" in agent:
        return (
            files("pathly_data")
            .joinpath(f"core/skills/{agent}.md")       # "core/skills/team/build.md"
            .read_text(encoding="utf-8")
        )
    # else: loads from core/agents/<group>/<agent>.md
```

The `"/"` in `"team/build"` routes to **a skill file**, not an agent role contract.
`core/skills/team/build.md` is the actual prompt body.

---

### Step 6 — What "instructions" contains at this point

The returned `instructions` string is:

```
<full text of src/pathly_data/core/skills/team/build.md>

## Current task
Feature: chat-stop-proxy
State: BUILDING
Storage path: C:\Users\Yafit\pathly-adapters\pathly\plans\chat-stop-proxy
```

The `team/build` skill is a **skill orchestrator** — it does NOT implement code itself.
Its job is to read `PROGRESS.md`, find the first TODO conversation in `CONVERSATION_PROMPTS.md`,
then spawn `builder` subagents. It runs the three-phase flow:
1. `builder` with `phase: analyze` → produces `NEEDS_CONTEXT`
2. `quick`/`scout` subagents in parallel (if needed)
3. `builder` with `phase: implement` + injected Scout Findings

The conversation-specific code instructions live in `CONVERSATION_PROMPTS.md` and are NOT
baked into the FSM response — they are read at runtime by the `team/build` skill.

---

### Step 7 — _agent_hint wraps instructions

`fsm_ops.py:146–164`:

```python
def _agent_hint(agent: str, instructions: str | None) -> dict:
    codex_role = "explorer" if agent in _CODEX_EXPLORER_AGENTS else "worker"
    prompt = (
        f"PATHLY AGENT: {agent}\n"
        f"CODEX FALLBACK ROLE: {codex_role}\n\n"
        "Use the Pathly role instructions below as the source of truth. "
        "Preserve the requested artifacts, limits, and completion signal. "
        "Do not revert unrelated user changes.\n\n"
    )
    prompt += instructions   # full team/build skill text + context footer
    return {
        "agent": agent,          # "team/build"
        "role": codex_role,      # "worker"
        "mode": "native-pathly-agent-if-callable-else-codex-role",
        "instructions": prompt,
    }
```

So `agent_hint.instructions` = preamble header + full skill text + context footer.

The top-level `instructions` field in the FSM response is the **raw** `build_prompt()` output
(without the preamble). The `agent_hint.instructions` field is the **wrapped** version.
Both are present in the JSON response. The CLAUDE.md adapter contract says new adapters must
read `agent_hint`.

---

### Step 8 — Supervisor extracts and dispatches instructions

`supervisor.py:328–329`:
```python
instructions = response.get("instructions", "")
preferred_adapter = response.get("preferred_adapter", "") or "claude"
```

Note: the supervisor reads the **top-level** `instructions` field (raw skill text + context),
not `agent_hint.instructions`. This is the string passed to `_run_stage_via_terminal`.

`supervisor.py:393–402`:
```python
invoke_result = _run_stage_via_terminal(
    state,
    instructions,       # <-- raw instructions from top-level field
    preferred_adapter,  # "claude" (no adapter_map set in team.flow.yaml)
    model,
    run_id,
    broadcast_fn,
    session=session_id,
    autonomy=autonomy_for_adapter,
)
```

---

### Step 9 — _run_stage_via_terminal → resolve_argv

`supervisor.py:182–184`:
```python
argv = resolve_argv(adapter, instructions, model, session=session, autonomy=autonomy)
```

`runner.py:36–52`:
```python
def resolve_argv(adapter, prompt, model, session=None, autonomy=True) -> list[str]:
    argv = resolve_command(adapter, prompt, model, session=session, autonomy=autonomy)["argv"]
    if adapter == "claude" and "--output-format=json" not in argv:
        argv = [*argv, "--print", "--output-format=json"]
    return argv
```

---

### Step 10 — resolve_command builds the final subprocess argv

`adapters.py:51–56` expands the template from `core/adapters.yaml`:

```yaml
claude:
  headless: [claude, "-p", "{prompt}", "--model", "{model}", "--output-format", json]
  autonomy_flag: "--dangerously-skip-permissions"
  resume: {mode: flag, flag: "--resume", arg: "{session_id}"}
```

Result (autonomy=True, no session):
```
["claude", "-p", "<instructions>", "--model", "claude-sonnet-4-6",
 "--output-format", "json", "--dangerously-skip-permissions",
 "--print", "--output-format=json"]
```

Where `<instructions>` is the raw skill text + `## Current task` footer.

The `--dangerously-skip-permissions` flag is appended because `autonomy=True`.

Note: `--output-format json` appears twice — once from the YAML template, once appended
by `resolve_argv`. The second one (`--output-format=json`) uses the equals form.
This is a benign duplicate; Claude CLI accepts both.

---

### Step 11 — What Claude actually receives in the -p flag

For a BUILDING stage on feature `chat-stop-proxy`, the exact `-p` value is:

```
# team/build

Stage 3a — Implement. Invoked by the `team` orchestrator when FSM state is BUILDING.
Executes one TODO conversation (analyze → scout → implement), then transitions to REVIEWING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.
...
[full content of core/skills/team/build.md — ~146 lines]
...
## Current task
Feature: chat-stop-proxy
State: BUILDING
Storage path: C:\Users\Yafit\pathly-adapters\pathly\plans\chat-stop-proxy
```

The `## Current task` block (3 lines) is appended by `build_prompt()`.

---

## The two different prompt paths

The question asked about `/pathly build` vs the runner. These are **separate, parallel invocation paths**:

### Path A — Manual skill: `/pathly build`
User types `/pathly build <feature>` in Claude Code. Claude Code loads
`~/.claude/skills/pathly-build/SKILL.md` (the installed adapter version of
`core/skills/development/build.md`). Claude receives that skill text directly as
its task context. This is a **human-initiated** invocation. The runner FSM is **not** involved —
the skill manages its own subagent spawning.

### Path B — Runner pipeline: `/runner/start`
Studio calls `POST /runner/start` → supervisor loop → `next_action` → extracts `instructions`
from FSM → passes to `resolve_argv` → launches `claude -p <instructions>`. The `-p` text
comes from `core/skills/team/build.md` (the `team/build` skill), NOT from
`core/skills/development/build.md`. These are two distinct skill files with similar but
different content.

| | `/pathly build` | Runner pipeline |
|---|---|---|
| Source | `core/skills/development/build.md` | `core/skills/team/build.md` |
| Trigger | User types command | Supervisor calls next_action |
| FSM involved | No | Yes |
| Spawns builder? | Yes (via Claude Code subagent) | Yes (skill spawns builder subagent) |

---

## Does the builder run the full pipeline (STORM→PLAN→BUILD)?

No. The agent Claude receives at BUILDING state is the **`team/build` skill**, which:
1. Reads `PROGRESS.md` for the next TODO conversation
2. Reads that conversation's prompt from `CONVERSATION_PROMPTS.md`
3. Spawns `builder` for analyze → scout → implement cycle for **one conversation**
4. Returns; the FSM then transitions to REVIEWING

The `team/build` skill does **not** loop through all pipeline stages. It does exactly one
BUILDING conversation and stops. The FSM state machine handles the STORM→PLAN→DESIGN→BUILD
→REVIEW→TEST→RETRO→DONE lifecycle across separate supervisor loop iterations.

---

## The `team` flow

`team.flow.yaml` defines the `team` flow. The `flow` field passed to `/runner/start` and
`/next_action` is always `"team"` for the standard pipeline. It drives:
- Which states exist (STORMING, PLANNING, DESIGNING, BUILDING, REVIEWING, TESTING, RETRO, DONE)
- Which skill/agent handles each state (`agent_map`)
- Transition rules (artifact-based, content-based, counter-based)
- Gates (verify_gate, scope_gate on BUILDING→REVIEWING)
- Transition actions (git commit on BUILDING→REVIEWING, archive on RETRO→DONE)

---

## Builder role contract vs team/build skill

`core/agents/building/builder.md` is **never** loaded during the runner pipeline's
BUILDING state. It is only loaded when:
- Another agent (like `team/build`) **spawns a `builder` subagent** (the Claude Code
  subagent system, not the FSM runner)
- A feedback file exists pointing to "builder" as target_agent, and `build_prompt_for_agent()`
  is called: `fsm_ops.py:488` calls `build_prompt_for_agent(flow_config, "builder", storage_path)`,
  which calls `_load_agent_text("builder")` — no slash, so it reads from
  `core/agents/building/builder.md`

In other words:
- FSM directly → Claude: sends `team/build` skill text
- `team/build` skill → Claude (as builder subagent): sends `builder.md` role contract

---

## Gaps

- The `_run_stage_via_terminal` path (supervisor → TERMINAL_SPAWN SSE → Studio terminal)
  was traced to the SSE broadcast, but the Studio-side terminal spawn (renderer code) was
  not read — the IPC to actually launch Claude Code is in the Studio renderer, not in the
  Python orchestrator.
- The legacy `invoke_agent()` in `runner.py` uses a slightly different prompt:
  `f"You are running pathly stage {state!r} for topic {topic!r}.\n\n{instructions}"` (line 144–147),
  adding a 2-line preamble. The supervisor path (`_run_stage_via_terminal`) does NOT add this
  preamble — it passes `instructions` verbatim.
- `core/skills/team/build.md` references `$ARGUMENTS` (FEATURE, rigor, autoFlow) but
  in the runner path there are no `$ARGUMENTS` — the feature and state come from
  the `## Current task` footer appended by `build_prompt()`. How the skill resolves this
  ambiguity was not verified end-to-end.
