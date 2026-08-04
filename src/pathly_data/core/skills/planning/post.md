# post

Post something from THIS session to a Pathly feature board — a file you produced (an *artifact*),
or a *decision* / *discovery* / *question* worth sharing with the team. This is the interactive
on-ramp from a Claude/Codex chat into the board: whatever you post is read back into every later
agent's prompt (`retrieve_board_context`), so work started here in conversation is picked up by
the pathly app where you left off.

## Step 1 — Decide WHAT to post, and its type

Read `$ARGUMENTS` and the conversation, and settle on the ONE thing to post. Infer its type:

| What you have | type | required fields |
|---|---|---|
| a file you wrote or produced | `artifact` | `text` (1–2 sentence description) · `summary` (one line per section) · `artifact_path` · `artifact_type` |
| a choice the team should adopt | `decision` | `text` |
| a fact or finding, no action needed yet | `discovery` | `text` |
| an open question for a human | `question` | `text` (+ the assumption you'd proceed on) · 2–4 `options` |

- `text` must be **self-contained** — 1–2 sentences another agent can act on without opening the file.
- For an `artifact`, resolve the file path and draft `summary` as a **topic map** (one line per
  heading) — it is embedded for semantic retrieval, so make it cover the real sections.
- If the type is genuinely ambiguous, ask the user once; otherwise infer it and confirm in Step 3.

## Step 2 — Pick the target board

Use the **feature-select** steps composed below to list the user's boards and let them choose.
That resolves `$FEATURE`, `board`, and `scope` (and routes to **create-feature** if they want a
new board or none exists yet).

## Step 3 — Confirm (this is the gate)

Show a compact preview and ask the user to **confirm / edit / cancel**. Post nothing until they approve:

```
POST <type> → <feature> board
<text>
<artifact_path>            (artifacts only)
```

## Step 4 — Post to the board

On approval, POST **once** — `from: "human"` (this came from an interactive human session), plus
the `$FEATURE` / `board` / `scope` from Step 2 and the type + fields from Step 1:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post -H "Content-Type: application/json" -d '{
  "feature": "<feature>", "from": "human", "type": "<type>",
  "board": "<board>", "scope": "<feature>",
  "text": "<self-contained 1-2 sentence text>"
}'
```

- **artifact** — also send `"summary": "<one line per section>"`, `"artifact_path": "<path>"`, `"artifact_type": "<md|json|…>"`.
- **question** — also send `"options": [{"id":"a","label":"…","description":"…"}, …]` (2–4 options).

Record the returned `"message_id"`.

**Skip-if-down (advisory):** if the server is unreachable, tell the user it was **not** posted —
and, for an artifact, that the file itself is unchanged and remains the source of truth. Do not
retry in a loop.

## Step 5 — Report

Confirm what landed where: `<type> · <feature> · <message_id>`. Nudge the user that it is live on
the board — they can continue in the pathly app, or open that feature's Command Center to see it.
