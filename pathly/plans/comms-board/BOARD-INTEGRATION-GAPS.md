# Comms Board — Integration Gaps & Proposals

> Audit date: 2026-06-14  
> Backend: complete (Phases 11–14 shipped)  
> This document covers what is missing between the backend and a fully live board.

---

## Gap 1 — Skills are silent (highest priority)

### What's wrong

Five pipeline skills write their outputs to the filesystem but never post to the comms board.
The board goes dark the moment planning ends. Agents already *receive* board context in every
prompt (the runner injection is fully wired) — the gap is one-directional: agents read but
don't write back.

| Skill | State | Currently writes to | Should also post |
|---|---|---|---|
| `review.md` | REVIEWING | `REVIEW_FAILURES.md` | `type=warning` per finding, `type=decision` on clean pass |
| `test.md` | TESTING | `TEST_FAILURES.md` | `type=warning` per failure, `type=decision` on pass |
| `design.md` | DESIGNING | `DESIGN.md` | `type=artifact` with design decisions + system choices |
| `explore.md` | any | `CONCLUSIONS.md` | `type=discovery` per significant finding |
| `debug.md` | any | `DEBUG_REPORT.md` | `type=discovery` for root cause, `type=decision` for chosen fix |
| `retro.md` | RETRO | `RETRO.md` | `type=artifact` with summary + `type=decision` for patches accepted |

### Proposed solution — shared "board-post" fragment

Rather than duplicating HTTP curl instructions in six skill files, extract a reusable fragment:

```
src/pathly_data/core/skills/fragments/comms-post.md
```

Content of the fragment:

```markdown
## Posting to the Comms Board

After writing any output file, mirror the key decision or finding to the comms board.
This makes it visible to all other agents and to Studio without them reading the file.

Use the board type that best describes what you found:

| Output | type | when |
|---|---|---|
| A decision the team must accept | decision | design choice, rigor level, scope cut |
| A constraint future agents must respect | constraint | arch rule, API limit, known incompatibility |
| A factual discovery (no action needed yet) | discovery | explorer finding, root cause identified |
| A violation or risk that blocks progress | warning | review failure, test failure, security issue |
| A completed output file (artifact) | artifact | DESIGN.md, CONCLUSIONS.md, RETRO.md, REVIEW_FAILURES.md |

Posting template (skip if server unreachable — board is advisory):

curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "<your-role>",
    "type": "<type>",
    "text": "<one paragraph summary — what you found and why it matters>",
    "board": "feature",
    "stage": "<CURRENT_STATE>"
  }'

Rules:
- One post per finding, not one post per file line.
- text must be self-contained — other agents read this without the file.
- Post warnings before writing feedback files so Studio shows them in real time.
- Post artifact type after the file is written, with the file path in text.
- Never post the full file content — summarize in ≤ 3 sentences.
```

Each skill gets a one-line addition at its output step:

**`review.md`** — after each BLOCKER or MAJOR finding:
```bash
# post warning per finding, then decision when review is complete
curl ... -d '{"type":"warning","text":"B1 — comms_post() ignores DB overrides. File: blueprints/comms.py:94","from":"reviewer",...}'
curl ... -d '{"type":"decision","text":"Review PASS — 0 blockers, 2 minors noted and accepted.","from":"reviewer",...}'
```

**`test.md`** — after each failing acceptance criterion:
```bash
curl ... -d '{"type":"warning","text":"G3 — no HTTP end-to-end test for B1 fix. See TEST_FAILURES.md.","from":"tester",...}'
```

**`design.md`** — after DESIGN.md is written:
```bash
curl ... -d '{"type":"artifact","text":"DESIGN.md written. Token budget: 4096. Font: Inter. Color system: HSL custom props. Stack: React + CSS Modules.","from":"designer",...}'
```

**`explore.md`** — after each conclusion:
```bash
curl ... -d '{"type":"discovery","text":"FSM reads flow YAML once at startup — live reload requires server restart. Relevant to: any hot-config work.","from":"explorer",...}'
```

**`debug.md`** — after root cause identified and after fix chosen:
```bash
curl ... -d '{"type":"discovery","text":"Root cause: fsm_http_client.py never sent X-Pathly-Secret header. All FSM calls failed silently with 401.","from":"builder",...}'
curl ... -d '{"type":"decision","text":"Fix: _load_secret() reads env or ~/.pathly/server_secret.txt. Applied to _request_raw(). No config change needed.","from":"builder",...}'
```

**`retro.md`** — after RETRO.md is written:
```bash
curl ... -d '{"type":"artifact","text":"RETRO.md written. 2 lessons captured. 1 instruction patch accepted. Signal: BACKEND_COMPLETE.","from":"planner",...}'
```

### Build estimate
- 1 new fragment file: `comms-post.md` (~40 lines)
- 6 skill edits: ~5 lines each
- Total: ~1 builder conversation (small)

---

## Gap 2 — Warning/escalation resolve doesn't reach the FSM

### What's wrong

The Studio renders "Block stage / Note as future work / Ignore" buttons on `warning` and
`escalation` message cards. The buttons fire `resolve()` in `commsStore`, which calls
`POST /comms/acknowledge` — and stops. The FSM never receives a block or continue signal.
So a reviewer warning card on the board currently has no pipeline effect.

### Current flow (broken)

```
board warning card
  → user clicks "Block stage"
  → commsStore.resolve('block')
  → POST /comms/acknowledge          ← only this happens
  → (nothing)                        ← FSM never hears about it
```

### Proposed flow

```
board warning card
  → user clicks "Block stage"
  → commsStore.resolve('block')
  → POST /comms/acknowledge          ← marks message handled on board
  → POST /runner/decision            ← supplies FSM gate decision
      body: { run_id, decision: "block", reason: message.text }
  → SSE STATUS event → Studio updates stage indicator
```

```
board warning card
  → user clicks "Note as future work"
  → commsStore.resolve('note')
  → POST /comms/acknowledge
  → POST /comms/post                 ← posts a decision message recording the choice
      body: { type: "decision", text: "Warning noted as future work: <warning.text>", from: "human" }
  → POST /runner/decision            ← continues pipeline
      body: { run_id, decision: "continue" }
```

```
board warning card
  → user clicks "Ignore"
  → commsStore.resolve('ignore')
  → POST /comms/acknowledge
  → POST /runner/decision            ← continues pipeline
      body: { run_id, decision: "continue" }
```

### Changes required

**`studio/src/renderer/src/store/commsStore.ts`** — `resolve()` action:
- Accept `resolution: 'block' | 'note' | 'ignore'` and `runId: string`
- After `POST /comms/acknowledge`, call `POST /runner/decision` with the correct decision value
- For 'note', first post a `type=decision` message to board recording the choice

**`studio/src/renderer/src/components/HQ/CommsPanel/CardBody.tsx`** — button handlers:
- Pass `runId` from `commsStore` (active run for the board's current feature) down to buttons
- The active `run_id` is already in `commsStore` via the runner status subscription

**`studio/src/renderer/src/store/commsApi.ts`** — add:
```typescript
export async function apiSupplyDecision(runId: string, decision: 'block'|'continue', reason?: string) {
  return apiFetch('/runner/decision', 'POST', { run_id: runId, decision, reason })
}
```

### Build estimate
- 1 store change, 1 component change, 1 API helper
- Total: ~2h / part of a Studio builder conversation

---

## Gap 3 — Async agent question loop doesn't exist

### What's wrong

`type=question` messages with `options` arrays are fully supported on the backend and render
correctly in Studio (radio buttons + Answer button). But no agent skill ever posts a question
to the board. The existing human-in-the-loop path uses a completely different mechanism:
`AskUserQuestion` tool → supervisor `_await_agent_question()` → `/runner/agent-answer`.

This means:
- Agents can only ask questions during a live, blocking PTY session
- Questions disappear when the session ends — no async, no history
- The board question UI has no content

### Proposed solution — two-part

**Part A: Async question posting in skills**

Add to the `comms-post.md` fragment (Gap 1) a `question` type section:

```markdown
## Posting a question to the board (async / non-blocking)

Use type=question when you need human input but can continue other work in the meantime.
Unlike AskUserQuestion (which blocks the PTY), board questions are async — you post and move on.
The human answers via Studio; you check for the answer at a defined checkpoint.

Post the question:
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "<your-role>",
    "type": "question",
    "text": "Should I use pattern A (simple, less flexible) or pattern B (complex, future-proof)?",
    "options": [
      {"label": "Pattern A", "value": "a"},
      {"label": "Pattern B", "value": "b"}
    ],
    "board": "feature",
    "stage": "<CURRENT_STATE>"
  }'

Record the returned message_id. At your next checkpoint, check for the answer:
curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&type=question&status=answered"

If no answer yet: proceed with your best judgment, note your assumption in a decision post.
If answered: use the chosen option value and post a decision confirming the choice.
```

**Part B: Answer → board → agent loop (runner-side)**

Currently `POST /comms/answer` marks the message answered in the DB but doesn't signal the
runner. To close the loop:

In `commsStore.answer()`: after `POST /comms/answer`, if there is an active run and the
answered question was tagged with `stage = current stage`, optionally call
`POST /runner/agent-answer` to unblock a waiting stage.

This is opt-in — most board questions are fire-and-check (agent continues). Only questions
explicitly tagged for runner-blocking need the `agent-answer` callback.

### Build estimate
- Fragment addition: ~20 lines
- Store change: ~10 lines
- Part B (runner callback) is a stretch goal — async fire-and-check is sufficient for V1

---

## Gap 4 — Studio missing search, supersede, attach

### What's wrong

Three backend endpoints are fully implemented but have no Studio UI:

| Endpoint | Purpose | Missing UI |
|---|---|---|
| `POST /comms/search` | Hybrid BM25 + cosine search | No search bar in CommsPanel |
| `POST /comms/supersede` | Mark a message replaced by a newer one | No button on message cards |
| `POST /comms/attach` | Attach a file artifact to a message | No button on message cards |

### Proposed solutions

**Search bar** — add to `CommsPanel.tsx` header row (above message list):

```
┌─ CommsPanel ────────────────────────────────────────┐
│  Feature ▸ Project ▸ Global    scope: comms-board   │
│  ┌─ Search board… ──────────────────────────── 🔍 ─┐ │  ← NEW
│  └──────────────────────────────────────────────────┘ │
│  Messages (7) │ Tasks (6)                            │
│  ...                                                 │
```

- On submit: `POST /comms/search` with `{ query, feature, board, scope, mode: "hybrid" }`
- Results replace the message list temporarily; "×" clears search and restores full list
- State: `searchQuery: string`, `searchResults: Message[] | null` in `useCommsPanel`
- Empty query = no search = normal list

**Supersede** — add to `CommsMsgCard` overflow menu (three-dot button, already implied by the
card layout):

```
[…]
  Mark as superseded by… → opens a message picker → POST /comms/supersede
  Delete
```

Superseded messages render with a strikethrough title and a "→ see [newer message]" link.
This is the primary way to retire stale decisions without deleting them.

**Artifact attach** — the paperclip button already exists in `CommsInput.tsx` (line 59–67)
with the icon rendered and `aria-label` set, but it is explicitly `disabled` with
`title="Attach artifact (coming soon)"`. The icon does not need to be added — only the
click handler and API call need wiring:

```
[text input field]  [📎]  [type picker]  [Send]
                      ↑
               currently disabled — needs:
               1. remove disabled prop
               2. onClick → open a file-path input (or browser file picker)
               3. POST /comms/attach { message_id, artifact_path }
```

Attach applies to an existing message: post the text message first, get back `message_id`,
then call `/comms/attach`. The simplest UX is a two-step compose: send text → card appears →
📎 button on the card opens a path input → calls attach.

### Build estimate
- Search bar: ~3h (input, state, results overlay)
- Supersede: ~2h (overflow menu, picker, visual treatment)
- Attach: ~45m (remove `disabled`, add path input, wire API call — icon already done)
- Total: ~1 Studio builder conversation

---

## Gap 5 — ConfigurePhaseModal ✓ ALREADY DONE

**Verified 2026-06-14.** `ConfigurePhaseModal` is fully integrated into the Monitor.

- `Monitor/index.tsx` imports it and holds `configStage` state
- `FsmView` receives `onStageClick={(stage) => setConfigStage(stage)}` — clicking a stage
  card opens the modal for that stage
- Modal renders inside Monitor with `stage={configStage}` and `onClose={() => setConfigStage(null)}`

No work needed here.

---

## Implementation order

| Priority | Gap | Effort | Value |
|---|---|---|---|
| 1 | Skills post to board (reviewer + tester first) | Small (1 conv) | High — board is dark during quality phases without this |
| 2 | Warning resolve → FSM | Small (2h) | High — warning buttons are broken without this |
| 3 | Search UI | Medium (3h) | Medium — becomes necessary around phase 3+ |
| 4 | Explorer + debug + retro post to board | Small (1 conv) | Medium — completes the read-back loop |
| 5 | Supersede + attach UI | Small (3h) | Medium — board accumulates stale notes without supersede |
| 6 | Async question loop | Medium (1 conv) | Low for V1 — fire-and-check is sufficient |

Priorities 1–2 can be done in a single builder session. Priorities 3–5 are a second session.
Priority 6 is a follow-up feature.

---

## What "fully wired" looks like

When all gaps are closed, the board lifecycle for a feature run looks like this:

```
PLANNING   planner posts type=task per phase (depends_on wired)     ← done ✓
DESIGNING  designer posts type=artifact with DESIGN.md summary      ← gap 1
BUILDING   builder polls ?ready=true, posts type=decision per phase ← done ✓
REVIEWING  reviewer posts type=warning per finding in real time     ← gap 1
           user sees warning card → clicks Block/Note/Ignore        ← gap 2 (resolve→FSM)
TESTING    tester posts type=warning per failure                    ← gap 1
RETRO      retro posts type=artifact with summary                   ← gap 1
DONE       board is a full audit trail of every decision,           ← end state
           warning, discovery, and artifact across the feature run
```

The board becomes a complete, searchable, dependency-aware history of how a feature was built
— readable by any future agent that needs context without re-reading every file.
