---

---
# consolidate

This is the canonical, tool-agnostic Pathly behavior for the memory consolidation workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## When to use

The consolidate skill is triggered when the board is asked to synthesize its free-form
notes into a single durable summary. It is invoked via `POST /comms/consolidate` with
`mode="full"` or `mode="reflect"`. Do not run this skill manually unless asked to.

---

## Step 1 — Read board context

The board context is injected into your prompt. It contains all messages currently on the
feature board for the active scope: discoveries, statuses, nudges, warnings, decisions,
tasks, and goals.

If no context is injected, or if the board contains only structural/governance messages
(goals, tasks, decisions, escalations, questions, answers), post a `status` noting there
are no free-form notes to consolidate and stop.

---

## Step 2 — Idempotency check

Before synthesizing, check for a recent consolidated note:

```bash
curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&scope=$FEATURE"
```

Inspect the response for any `type=discovery` message whose `text` starts with
"📝 Consolidated:". If one exists and no new `discovery`, `status`, `nudge`, or `warning`
messages were posted AFTER its timestamp, skip synthesis — the board is already
consolidated. Post a brief `status` noting this and stop.

---

## Step 3 — Identify free-form notes

From the injected board context, identify all messages of type `discovery`, `status`,
`nudge`, or `warning` that are NOT already superseded. These are the raw free-form notes
you will synthesize. Collect their `message_id` values.

Do NOT include goals, tasks, decisions, escalations, questions, or answers. Those are
structural/governance and must not be restated or superseded.

If there are fewer than 2 free-form notes, post a `status` noting there is not enough
to consolidate and stop.

---

## Step 4 — Synthesize

Write ONE concise synthesis note covering the durable learnings from the free-form notes:
- What was discovered or found
- Key outcomes or state changes
- Any warnings or important caveats

You MAY reference decisions or tasks in prose (e.g. "following the decision to …") but
must NOT restate or reproduce them. Keep the synthesis to 3–6 sentences.

---

## Step 5 — Post the consolidated note

POST the synthesis as a `type=discovery` message:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "reflector",
    "type": "discovery",
    "text": "📝 Consolidated: <your synthesis here>",
    "board": "feature",
    "scope": "$FEATURE"
  }'
```

Record the returned `"message_id"` as `$SUMMARY_ID`.

---

## Step 6 — Supersede the raw free-form notes

For each raw free-form note you identified in Step 3 (type in {discovery, status, nudge,
warning}), supersede it by the consolidated summary. NEVER supersede goal, task, decision,
escalation, question, or answer messages.

```bash
curl -s -X POST http://127.0.0.1:8765/comms/supersede \
  -H "Content-Type: application/json" \
  -d '{
    "old_id": "<raw note id>",
    "new_id": "$SUMMARY_ID"
  }'
```

Repeat for each raw note. If the FSM server is unreachable for any supersede call, skip
it silently and list the IDs that were not superseded in your output.

---

## Step 7 — Report

After all posts and supersede calls complete (or are skipped), output:

```
## Consolidation complete

Synthesized: <N> free-form notes
Consolidated note id: <$SUMMARY_ID>
Superseded: <list of raw note ids>

Summary posted:
"📝 Consolidated: <first 120 chars of synthesis>"
```

If you had to skip because the board was already consolidated, output:

```
## Already consolidated

No new free-form notes since the last synthesis. Nothing to do.
```

---

## Constraints

- Never supersede goal, task, decision, escalation, question, or answer messages.
- Post exactly ONE consolidated discovery. Do not split into multiple posts.
- Propose/summarize only — do not execute code, run builds, or modify files.
- Write only board messages. Do not touch plan files, state files, or artifacts.
- If the FSM server is unreachable for the synthesis POST, list the proposed text in
  your output so the human can post it manually. Fail silently on unreachable supersede
  calls and list the skipped IDs.
