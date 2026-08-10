# test

This is the canonical, tool-agnostic Pathly behavior for the standalone test workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

> Shared protocols — **Scout choreography** and **Live progress logging** — are composed in
> below from fragments. This body covers only the standalone test-workflow specifics.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## When to use

Use `/test` to verify acceptance criteria for a completed feature, or to run a targeted
test pass against a specific plan folder outside the full team pipeline.

Use `team <feature> test` when running within the full pipeline (build → test → retro).

---

## Feature detection

If `$ARGUMENTS` contains a non-keyword word, use it as `FEATURE`.
Otherwise auto-detect:
1. Read `pathly/features/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/features/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `pathly/features/` folder exists or is empty: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`

## Step 0 — Locate the plan

Parse `$ARGUMENTS` for a plan folder name (FEATURE). If blank, use the auto-detected FEATURE above.

Check the build is complete before testing. Query the board task DAG:
```
curl -s "http://127.0.0.1:8765/comms/tasks?feature=<feature>&scope=<feature>"
```
If any task's `task_status` is not `done`, stop:

```
Not all tasks are done for <feature>. Run /build first.
```

If the board is unreachable (older / offline plans), skip the completeness check and proceed on the
plan + repo state.

Read `pathly/features/<feature>/USER_STORIES.md` (required). If missing, stop:

```
No USER_STORIES.md found for <feature>. Cannot run acceptance tests without stories.
```

---

## Step 1 — Analyze (tester phase: analyze)

log-phase PHASE_START analyze

Spawn the **tester** agent with `phase: analyze`:

```
phase: analyze
Read pathly/features/<feature>/USER_STORIES.md.
List what test infrastructure and context you need before verifying — output NEEDS_CONTEXT block only.
```

Parse the `## NEEDS_CONTEXT` block it returns.

log-phase PHASE_DONE analyze

---

## Step 2 — Scout (if NEEDS_CONTEXT has entries)

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: tester`. Use the returned compressed summary as
`## Test Context` (set it to `none` and skip this step if `NEEDS_CONTEXT` was `none`).

log-phase PHASE_DONE scout (include scouts_count = number of entries spawned, or 0 if skipped)

---

## Step 3 — Test (tester phase: test)

log-phase PHASE_START test

Spawn the **tester** agent with `phase: test`:

```
phase: test
Read pathly/features/<feature>/USER_STORIES.md.
Run the verify command(s) to check each acceptance criterion.

## Test Context
[compressed summary from Step 2, or "none"]

For each criterion: PASS / FAIL / NOT COVERED.
If any FAIL or NOT COVERED: write pathly/features/<feature>/feedback/TEST_FAILURES.md.
```

log-phase PHASE_DONE test

---

## Step 4 — Fix loop (if TEST_FAILURES.md exists)

Track `retryCount = 0`.

**If `TEST_FAILURES.md` exists:**

Increment `retryCount`. If `retryCount > 2`: stop —
```
Test failures unresolved after 2 fix cycles. Manual intervention required.
```

Spawn **builder**:
```
Read pathly/features/<feature>/feedback/TEST_FAILURES.md.
Fix each failing or uncovered criterion.
Delete pathly/features/<feature>/feedback/TEST_FAILURES.md when resolved.
```

After builder completes: re-run Step 3.

**If no `TEST_FAILURES.md`:** all criteria pass — proceed to Step 5.

---

## Step 5 — Report

Print the tester's full test plan output showing PASS/FAIL/NOT COVERED per criterion.

Then ask:

```
Test run complete. What next?

[1] Proceed to retro       /retro <feature>
[2] Re-run tests           /test <feature>
[3] Done — keep as record
```

---

## Rules

- **Tester + builder only** — no reviewer, no planner.
- **Tester does not fix code.** Builder handles all fixes.
- **Run before reporting.** Never claim PASS without executing the verify command.
- **Strict rigor:** all NOT COVERED criteria must be resolved before proceeding to retro.

## Live progress logging

Each `log-phase PHASE_START <phase>` or `log-phase PHASE_DONE <phase>` marker is a mandatory
pipeline event. When you encounter one (or an inline `Run:` bash block replacing it), execute it immediately:

Run:
```bash
# On PHASE_START:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_START \
  --project-root "<project_root>"

# On PHASE_DONE:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_DONE \
  --project-root "<project_root>"
```

- `<feature>` — the feature slug (folder name under `pathly/features/`)
- `<agent>` — the current agent role (`builder`, `reviewer`, `tester`, `designer`, etc.)
- `<phase>` — one of `analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`

**Server availability — start-if-needed (same contract as log-agent-done):**

If `pathly-fsm-call` fails or the server is not reachable:
1. Start the server in the background: `pathly-fsm-http`
2. Wait 2 seconds, then retry the `record-phase` call once.
3. If the retry also fails: skip silently and continue — phase logging must never block execution.

This makes phase logging reliable on any adapter (Codex, Copilot, CLI) where the
FSM server is not automatically managed by the host environment.

## Code intelligence (ask Pathly's code graph before Grep)

When you need to understand code **structure** — where a symbol is defined, who calls it, or the
blast radius of a change — ask Pathly's code-knowledge graph first. It is precise and fast, and each
query is logged to the board as shared context for other agents.

**Reach it whichever way your tools allow — check your own tool list, don't assume:**
- If you have the **MCP code-tools** (`mcp__codebase-memory-mcp__{search_graph,query_graph,trace_path,
  get_architecture}` and/or `mcp__serena__{find_symbol,get_symbols_overview,find_referencing_symbols}`),
  **call them directly** — they ARE the graph + LSP the `op`s below describe (`symbol` → `find_symbol`;
  `callers`/`impact` → `query_graph`/`trace_path`; whole-file/arch structure → `get_symbols_overview`/
  `get_architecture`). No Bash needed — this is how the no-Bash roles reach the graph.
- If you have **Bash**, use the HTTP proxy + CLI fallback below.
- A few roles have **both** — prefer the MCP tools for one symbol, the proxy for a broad pattern sweep.

```bash
curl -s -X POST http://127.0.0.1:8765/code/query -H "Content-Type: application/json" -d '{
  "op": "symbol",
  "target": "<file path OR symbol name>",
  "role": "<your-role>",
  "scope": "<feature>",
  "engine": "both" }'
```

- `op` — `symbol` (definition + signature) · `callers` (who calls it) · `impact` (what a change to
  it touches) · `chain` (call path between two symbols) · `context` (surrounding structure) ·
  `pattern` (find a code pattern). Your `role` gates which ops you may use.
- `engine` (optional) — which backend answers: `graph` (whole-repo code graph — breadth, needs
  indexing) · `lsp` (Serena/LSP — precise, always-fresh, no index; the first query per project pays
  a ~1-min warm-up, then it's fast) · `both` (merge graph + LSP). Omit to use the server's configured
  default. Prefer `lsp` or `both` right after edits, since the graph can lag recent changes.
- The response is `{ "ok": true, "result": <block-or-null>, "backend": "<name>" }`.
- **If `result` is `null`** (backend off, file not yet indexed, or path unresolved), first try the
  **direct-CLI fallback** below; then fall back to Grep/Read. Never block on it — an accelerator, not a gate.

### Direct-CLI fallback (proxy returned null)

If `codebase-memory-mcp` is on the PATH, query its pre-built code graph directly — this works in
headless runs and covers cases the proxy misses (e.g. a file added since the last index). Resolve the
project slug once, then search:

```bash
codebase-memory-mcp cli list_projects '{}'    # pick the project whose root_path is your repo → use its "name"
codebase-memory-mcp cli search_code '{"project":"<name>","pattern":"<symbol_or_text>"}'   # ranked; note: pattern, not query
codebase-memory-mcp cli query_graph '{"project":"<name>","query":"MATCH (n) WHERE n.name=\"<sym>\" RETURN n.name, n.file_path"}'
```

`search_code` takes `pattern` (grep-like over the graph); `query_graph` runs Cypher (callers/callees,
call paths, impact). If the binary is absent or returns nothing, fall back to Grep/Read.

Use it **before** editing an unfamiliar symbol (check `callers` / `impact` so you don't break a
caller) and whenever a task names a symbol you haven't located yet (`symbol`). Prefer one targeted
query over a broad Grep sweep.

## Scout choreography (analyze → scout → compress)

The stage agent (builder / reviewer / tester) declares what context it needs *before* doing the
work, scouts gather that context in parallel, and the findings are compressed into the work prompt.

### Phase 1 — Analyze

Spawn the stage agent with `phase: analyze`. It outputs a `## NEEDS_CONTEXT` block **only** —
the list of things it must know before implementing / reviewing / testing.

NEEDS_CONTEXT format (one entry per line):
```
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>
```

Parse the `## NEEDS_CONTEXT` block. If it says `none`, skip Phase 2 (or use only the stage's
default scout entry, where one is defined).

### Phase 2 — Scout (parallel, max 4)

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total):
- `type: quick` → spawn `quick` with `ROLE: <stage agent>` + the question
- `type: scout` → spawn `scout` with `ROLE: <stage agent>` + scope + question

After each scout/quick returns, parse its `<usage>` block (`subagent_tokens`, `tool_uses`) and
record it immediately — non-blocking, skip if server unavailable:

```bash
# For each scout that returned — replace placeholders with actual values from <usage> block
# model is claude-haiku-4-5-20251001 for scout/quick agents
pathly-fsm-call record-activity \
  --agent "scout" \
  --feature "<feature>" \
  --summary "<question truncated to 80 chars>" \
  --conversation N \
  --model "claude-haiku-4-5-20251001" \
  --total-tokens SCOUT_TOKENS \
  --tool-uses SCOUT_TOOL_USES \
  --wall-seconds 0 \
  --cost-usd SCOUT_COST_USD
```

Compute `SCOUT_COST_USD` using haiku rates (input $0.80/MTok, output $4.00/MTok) with 80/20 split.
Add each scout's `SCOUT_TOKENS` to the stage running total for the final AGENT_DONE.

Compress all returned findings into a short summary and inject it into the Phase 3 work prompt
as the stage's findings section.

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
