# review

This is the canonical, tool-agnostic Pathly behavior for the review workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

> Shared protocols — **Scout choreography**, **Sub-agent spawning rules**, and **Live progress
> logging** — are composed in below from fragments. This body covers only the interactive
> review-workflow specifics (including its own pipeline exit contract).

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

Review code at $ARGUMENTS against this project's architectural standards.

- `staged` or empty → review `git diff --staged`
- `last` → review `git diff HEAD~1 HEAD`
- file path → review that specific file
- `<feature> <N>` (e.g. `pathly-observability 2`) → **pipeline review**: review `git diff HEAD~1 HEAD`, load that feature's `ARCHITECTURE_PROPOSAL.md` for scope context, then run the exit contract on pass/fail

## Pre-review context gathering

**Phase 1 — Analyze:**
log-phase PHASE_START analyze

Spawn `reviewer` with `phase: analyze`. Pass the diff target (`$ARGUMENTS`).
Parse the returned `## NEEDS_CONTEXT` block.

log-phase PHASE_DONE analyze

**Phase 2 — Scout:**
log-phase PHASE_START scout

Run the Scout choreography with `ROLE: reviewer`. Use the returned summary as findings
(`none` if `NEEDS_CONTEXT` was `none`).

log-phase PHASE_DONE scout (include scouts_count = number of entries spawned, or 0 if skipped)

**Phase 3 — Review:**
log-phase PHASE_START review

Spawn `reviewer` with the full review prompt. Inject:
```
## Applicable Rules
[compressed summary from Phase 2, or "none" if skipped]
```
Keep Steps 1–3 and the report format inside the reviewer's spawn prompt.

log-phase PHASE_DONE review

## Step 1 — Get the diff

Run the appropriate git diff command based on `$ARGUMENTS`.

## Step 2 — Load project rules

Read (if present):
1. The `ARCHITECTURE_PROPOSAL.md` in the `pathly/features/*/` folder that most closely matches the changed files — defines the intended architecture for in-progress work
2. Project rule files — project-wide architectural contracts

If neither exists, review against general software engineering good practices and note the absence.

If the task you are reviewing has `context_refs`, for each `{artifact, anchor}` call:
```
GET /comms/artifacts/section?scope=$SCOPE&artifact=<artifact>&anchor=<anchor>
```
and read the returned `text` field (the full section — the advisory spec for that phase,
e.g. edge cases / happy flow). The `summary` is a pointer, not the spec — read `text`.
If `anchor` is absent or null, omit it to retrieve the whole file. These are the same
refs the builder hydrated — review against the same advisory spec the builder used.

## Step 3 — Check for violations

For each changed file, check:

### Dependency direction
- Does the file import from a layer it should not depend on?
- Does the dependency direction match what `ARCHITECTURE_PROPOSAL.md` specifies?

### Layer responsibility
- Does the file contain logic that belongs in a different layer?
- Are concerns properly separated (e.g., data access vs. business logic vs. presentation)?

### Conventions
- Does the file follow naming and structural conventions shown in project rules?
- Are interfaces and contracts implemented correctly per the rules files?

### Scope
- Does the change touch files outside the scope described in the active conversation plan?
- Are there unexpected side effects on other modules?

## Report format

List each check as PASS / FAIL / N/A.

For failures use these prefixes:
```
[ARCH] <file>:<line> — <what the violation is> — <what it should be instead>
[IMPL] <file>:<line> — <what the violation is> — <fix required>
```

If all checks pass: `PASS — no violations found.`

If violations found: list each one. Do NOT auto-fix. Report only.

## Exit contract (pipeline review only — when called as `<feature> <N>`)

**On PASS:**

1. Report completion to the FSM:
   ```bash
   pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>
   ```
   The FSM computes the next state from `transition_rules`: if ready tasks remain on the board DAG
   it loops back to `BUILDING` for the next task, otherwise it advances to `TESTING`. The FSM writes
   STATE.json as the authoritative mirror — do NOT hand-edit STATE.json or any tracking file.
2. Invoke the `log-agent-done` skill with:
   ```json
   {"agent":"reviewer","feature":"<feature>","conversation":<N>,"result":"PASS"}
   ```

**On FAIL:**

1. Write violations to `pathly/features/<feature>/feedback/REVIEW_FAILURES.md`.
2. Report completion to the FSM:
   ```bash
   pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>
   ```
   (The FSM reads REVIEW_FAILURES.md and routes via transition_rules to REVIEW_FAILED. The FSM writes STATE.json as the authoritative mirror.)
3. Do NOT change board task status — the task is not done until violations are resolved.

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

## Sub-agent spawning rules

This stage runs on a host that can spawn sub-agents (Task / subagent capability).

- **Never execute work yourself** — spawn the right subagent for each step.
- Treat the FSM as a deterministic filesystem machine: read disk, process one event, emit one action.
- After every agent completes, check for feedback files before advancing.
- Spawn scouts and parallel workers up to a maximum of 4 at once.

Map each action to its subagent (the stage skill lists the exact roles for that stage):

| Action | Spawn |
|---|---|
| Implement | `builder` |
| Review changes | `reviewer` |
| Verify acceptance criteria | `tester` |
| Clarify requirement | `planner` |
| Clarify / redesign architecture | `architect` |
| Scout context | `scout` or `quick` (with `ROLE:` set to the stage agent) |

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

## Pulling context from the Board Catalog

Your prompt's board context already pushes you the curated channels — governance,
the task's referenced sections, and semantic matches. When the task needs more than
those, you may **pull** additional artifacts from the board catalog. You are scoped to your
own board, so this is safe and bounded — you cannot see another feature's artifacts.

The **Catalog** block in your context lists the top artifacts inline (path · type · summary).
Read that first and pull only the section you actually need — do not refetch the references,
they are already hydrated.

### How to pull

```bash
# List what's available on your board (already permission-scoped to you)
curl -s "http://127.0.0.1:8765/comms/artifacts?board=feature&scope=<feature>"

# Read one section (omit &anchor for the whole file)
curl -s "http://127.0.0.1:8765/comms/artifacts/section?scope=<feature>&artifact=<path>&anchor=<anchor>&trail=<task_id>"
```

Read the returned `text` field — it is the authoritative section, not the `summary`.

### Rules

- **Pull narrowly.** Only fetch what the current task needs; the catalog is large by design.
- **Record what you read.** Append `&trail=<task_id>` to a section pull so the board logs the
  access — this is how the timeline shows what context each task consumed.
- **Advisory + skip-if-down.** If the server is unreachable, skip silently and proceed from the
  context you already have. Pulling never blocks your work.
- **Don't refetch references** — they are already in your prompt.

## Searching the board

Your prompt's board context was assembled from ONE query the runner wrote for you — it
embedded your task description and took the top few matches per tier. That is a good first
guess, but it is a guess: it was computed before you read the task, and it cannot know the
term you are about to trip over.

When it comes up short, **ask the board yourself, in your own words**. This is the same
hybrid (keyword + semantic) index the injected context came from — you are re-querying it
with a better question, not reading a different store.

### When to search

Search when the answer plausibly already exists on the board and you do not have it:

- The injected context is thin, or it matched your task's topic but not the part you are
  actually stuck on.
- You hit a term, constraint, or name that reads like a prior decision you were not shown.
- You are about to make a choice someone may already have made — search before deciding,
  not after.

Do **not** search:

- Before reading what you were already given. The pushed channels come first, always.
- To re-fetch a reference or catalog entry that is already in your prompt.
- More than a few times for one task. Two or three targeted queries is a working session;
  ten is a sign you should proceed with what you have and say what was missing.

### How to search

```bash
curl -s -X POST http://127.0.0.1:8765/comms/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "<what you actually want to know, in plain words>",
    "feature": "<feature>",
    "board": "<board>",
    "scope": "<feature>",
    "k": 5
  }'
```

- `query` — a phrase, not a keyword. `"why does the runner spawn codex with null stdin"`
  beats `"codex stdin"`: the semantic arm matches meaning, so a fuller question ranks better.
  Capped at 512 characters.
- `k` — how many results (default 5, max 50). Start at 5; raise it only if 5 came back all
  relevant and you need more of the same.
- `mode` — optional: `hybrid` (default, use this), `keyword` for an exact literal string,
  `semantic` when you want meaning-matches only.
- `feature` — always your own `<feature>`. The route requires it, but it is only a fallback:
  `board` + `scope` are what actually select which board is searched.

### Which boards you may search

<search_tiers>

Those are the tiers this run reads, and they are the tiers you may query — one `board` +
`scope` pair each. Pass a pair **exactly as written above**: the scope is a different shape per
tier (a feature board keys by its slug, the project board by the project root path, the global
board by the literal `global`), and a mismatched pair is not an error — it returns `[]`, which
reads exactly like "the board knows nothing". Copy the pair rather than reconstructing it.

The default query above is your own board. Widen to another listed tier when the thing you are
missing is plainly not local — a cross-cutting decision, a convention, a lesson from another
feature. A tier that is NOT listed is off for this run: its board-scope setting says this agent
does not read it, and searching around that is not your call. If nothing is listed, do not
search at all.

### Reading the results

The response is a JSON array of board messages, best-first. Per result:

- `text` — the message. This is the content; read it.
- `_match_source` — `keyword` (a literal match) or `semantic` (a meaning match). A keyword
  hit is a stronger signal that you found the exact thing you named.
- `_distance` — cosine distance on semantic hits, lower is closer. Absent on keyword hits.
- `type` — `decision` and `constraint` outrank `discovery` and `status`: a decision binds
  you, a discovery merely informs you.

**An empty array means the board genuinely has nothing** — results are never padded with
recent messages, so `[]` is a real answer, not a failure. Take it at face value, stop
searching for that thing, and proceed. If what you needed was missing, say so in your
output; that gap is itself worth recording.

### Rules

- **Search reads, it never writes.** Finding something does not mean re-posting it — it is
  already on the board. Post only what YOU produced.
- **A search result is context, not authority.** Governance in your prompt still wins, and
  your own output file remains the source of truth for your work.
- **Advisory + skip-if-down.** If the server is unreachable or returns non-200, skip
  silently and proceed from the context you already have. Searching never blocks your work.
