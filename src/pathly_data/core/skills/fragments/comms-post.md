## Posting to the Comms Board

After you finish your work and write your output file(s), mirror the key finding or decision to
the comms board. This makes it visible to every other agent and to Studio **without** them having
to open your file. The board is read back into every agent's prompt automatically.

This is one-directional broadcast — you post and continue. It never blocks your work, and it is
advisory: if the FSM server is unreachable, skip it silently (your output file is the authority).

### Choose the type that fits what you produced

| What you found | type | When to use it |
|---|---|---|
| A decision the team must accept | `decision` | design choice, rigor level, scope cut, review/test PASS |
| A constraint future agents must respect | `constraint` | arch rule, API limit, known incompatibility |
| A factual discovery, no action needed yet | `discovery` | explorer finding, root cause identified |
| A violation or risk that blocks progress | `warning` | review failure, test failure, security issue |
| A completed output file | `artifact` | DESIGN.md, CONCLUSIONS.md, RETRO.md, REVIEW_FAILURES.md |

### How to post

For each finding (one post per finding — not one per file line), POST to the board. Replace
`<feature>` with the feature slug, `<your-role>` with your agent role (`reviewer`, `tester`,
`designer`, `explorer`, `builder`, `planner`, …), and `<CURRENT_STATE>` with the active FSM stage.

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature>",
    "from": "<your-role>",
    "type": "<type>",
    "text": "<one self-contained paragraph — what you found and why it matters>",
    "board": "<board>",
    "run_id": "<run_id>",
    "stage": "<CURRENT_STATE>"
  }'
```

> Always include `"run_id": "<run_id>"` — it correlates your post to THIS run so it shows on the
> run's Pipeline **Board** tab and streams there **live** (the server tees run_id-tagged posts onto
> the per-run event feed) instead of the tab waiting on its poll.

**Server availability — skip-if-down (advisory):**
If the call fails or the server is not reachable (connection refused / non-200), skip silently and
continue. The board is a convenience mirror; your output file is the source of truth. Do **not**
start the server or retry in a loop just to post.

### Rules

- One post per finding, not one per file line.
- `text` must be self-contained — other agents read this without opening your file.
- Post `warning` items **before** writing the feedback file, so Studio shows them in real time.
- Post an `artifact` **after** the file is written. Provide TWO fields so it is both readable
  and findable:
  - `text` — a real **1–2 sentence description**: what the artifact is and why it matters. NOT a
    bare label like "Design doc: X".
  - `summary` — a compact **topic map of the file's sections**: one line per heading with a short
    gloss. This is the catalog entry other agents scan, and it is embedded for **semantic
    retrieval**, so make it cover the real section topics.
  ```bash
  curl -s -X POST http://127.0.0.1:8765/comms/post -H "Content-Type: application/json" -d '{
    "feature": "<feature>", "from": "<your-role>", "type": "artifact", "board": "<board>",
    "run_id": "<run_id>",
    "text": "<1-2 sentence description>", "summary": "<topic map, one line per section>",
    "artifact_path": "<path to the file>", "artifact_type": "md"}'
  ```
- Never paste full file content — keep `text` to 1–2 sentences and `summary` to one line per section.
- `<board>` is set for you by the runner — it is the board **tier** your stage writes to
  (`feature` for a feature/goal run, `project` for a project decompose). Post with
  `"board": "<board>"` and your write lands on the right board. `global`-tier writes stay
  role-gated (`director`/`human`); a `feature` write is always unrestricted.

### What each role typically posts

| Role / stage | After writing | Post |
|---|---|---|
| `reviewer` (REVIEWING) | `REVIEW_FAILURES.md` | one `warning` per BLOCKER/MAJOR finding; one `decision` ("Review PASS") on a clean pass |
| `tester` (TESTING) | `TEST_FAILURES.md` | one `warning` per failing acceptance criterion; one `decision` ("Tests PASS") on pass |
| `designer` (DESIGNING) | `DESIGN.md` | one `artifact` summarizing the design system (stack, palette, type, key choices) |
| `explorer` (any) | `CONCLUSIONS.md` | one `discovery` per significant finding |
| `builder` (debugging) | `DEBUG_REPORT.md` | one `discovery` for the root cause; one `decision` for the chosen fix |
| `planner` (RETRO) | `RETRO.md` | one `artifact` summarizing lessons; one `decision` per accepted instruction patch |

### Asking a question (non-blocking)

When you need a human decision but must **not** block, post a `question` with 2–4 options.
You continue working on the assumption stated in `text`; if a human answers, the answer is
injected at the next `/next_action`. Never wait in a loop for the reply.

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature>",
    "from": "<your-role>",
    "type": "question",
    "text": "<the question + the assumption you are proceeding with if unanswered>",
    "options": [
      {"id": "a", "label": "<option A>", "description": "<short consequence>"},
      {"id": "b", "label": "<option B>", "description": "<short consequence>"}
    ],
    "board": "<board>",
    "run_id": "<run_id>",
    "stage": "<CURRENT_STATE>"
  }'
```

Rules:
- Always state your fallback assumption in `text` — the question is advisory, not a gate.
- 2–4 options, each with a one-line `description` of its consequence.
- One question per genuinely-open decision; do not turn routine work into questions.
- The human answer arrives via `/comms/answer`; you read it from the injected board context
  on your next turn. Do not poll.
