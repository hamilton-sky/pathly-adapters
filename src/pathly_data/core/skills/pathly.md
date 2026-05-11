# pathly

This is the canonical Pathly dispatcher. It reads `$ARGUMENTS`, extracts the
subcommand, and executes the matching behavior inline.

## Routing

Split `$ARGUMENTS` into:
- **subcommand** — first word (lowercase)
- **args** — everything after the first word

### Core FSM commands

| subcommand | aliases | behavior |
|---|---|---|
| (empty) | — | → **help** |
| `start` | `s` | → **start** |
| `go` | `g`, `continue`, `resume`, `next` | → **go** |
| `pause` | `stop` | → **pause** |
| `end` | `done`, `finish`, `wrap` | → **end** |
| `help` | `h`, `?` | → **help** |
| `meet` | — | → **meet** |
| `build` | `b` | → **go** with intent `"continue build"` |
| `storm` | — | → **go** with intent `"storm <args>"` |

### Specialized commands (skip director routing)

| subcommand | behavior |
|---|---|
| `po` | → **po** skill directly |
| `debug` | → **debug** skill directly |
| `explore` | → **explore** skill directly |
| `verify` | → **verify-state** skill directly |

### Catch-all

| subcommand | behavior |
|---|---|
| anything else | treat all of `$ARGUMENTS` as natural language intent → **go** |

Before invoking, print:
```
Pathly route: <subcommand>
```

---

## Behavior: start

You are the Director entry point. Greet the user, show the full feature journey,
and route to the right workflow.

Print:

```
╔═══════════════════════════════════════════╗
║           Welcome to Pathly               ║
╚═══════════════════════════════════════════╝

Typical path for a new feature:

  0. /pathly po      — clarify requirements with the Product Owner (optional, recommended for ambiguous features)
  1. /pathly storm   — brainstorm the approach with the architect
  2. /pathly go      — plan + route to build (director chooses rigor)
  3. /pathly build   — implement conversation by conversation
     (review + test happen automatically inside the pipeline)
  4. /pathly end     — retro + archive

Also: debug · explore · verify · meet · help

What would you like to do?

  (1) Start a new feature      — describe it and let the director route
  (2) Clarify requirements     — talk to the PO first
  (3) Brainstorm an idea       — open architect storm session
  (4) Continue in-progress work
  (5) Import a PRD file

Reply with 1–5 — or just describe what you want:
```

Wait for user input. Then route:

- **1 or free text**: treat as intent → route via **go** behavior
- **2 or po**: ask "Which feature? (or describe it)" → route to **po** skill
- **3 or storm**: ask "What idea do you want to explore?" → invoke `storm <answer>`
- **4 or continue**: route to **go** behavior with intent `"continue"`
- **5 or prd / import**: ask "Feature name and PRD file path?" → route to **go** with intent `"prd-import <name> <path>"`

---

## Behavior: go

**Step 0 — Get Intent**

Use `args` as the intent. If `args` is empty, ask:

```
What do you want to build or do?
```

Wait for reply.

**Step 1 — Read Project State**

1. Does `plans/` exist and contain feature folders?
2. For each folder in `plans/` (skip `.archive/`), read `PROGRESS.md` if present.
3. Count TODO vs DONE conversations.
4. Check `git status --short`.

**Step 2 — Classify Intent**

| Intent | Signals | Route |
|---|---|---|
| `tiny_change` | copy tweak, config, one obvious bug, "quick fix" | `team-flow <feature> nano` |
| `new_feature` | build, add, create, implement, make, I want | `team-flow <feature> <rigor>` |
| `brainstorm` | brainstorm, storm, refine, unclear idea | `storm <topic>` |
| `resume` | continue, resume, finish, next step, keep going | `team-flow <feature> build` |
| `test` | test, verify, acceptance criteria, QA | `team-flow <feature> test` |
| `fix_or_review` | fix, broken, bug, check diff, review | `review` or `team-flow <feature> nano` |
| `retro` | retro, wrap up, lessons, done building | `retro <feature>` |
| `unclear` | anything else | ask one clarifying question |

Feature name: strip filler words, kebab-case the useful phrase, match to existing
`plans/<name>/` folder if one exists.

**Step 3 — Choose Rigor**

- **nano**: ≤2 files, obvious path, no high-risk domain, user didn't ask for planning
- **lite**: low-risk feature, short plan useful, 1–3 conversations
- **standard**: multiple layers, >3 conversations, meaningful user-facing behavior
- **strict**: auth, payment, billing, secrets, privacy, schema migration, destructive data, compliance

Add `fast` only if user explicitly asks for no-pause execution. Never combine `strict` + `fast`.

**Step 4 — Ask Only If Unsafe**

Ask one clarifying question only if:
- Multiple active features could match
- A destructive request lacks a target
- Cannot infer intent between review, fix, or new implementation

Otherwise choose conservatively and proceed.

**Step 5 — Print Decision**

```
I will treat this as: <rigor>
Reason: <one sentence>
Starting: <plain-language next action>
```

**Step 6 — Invoke Route**

```
storm <topic>
team-flow <feature> nano
team-flow <feature> lite
team-flow <feature> standard
team-flow <feature> strict
team-flow <feature> build
team-flow <feature> test
review
retro <feature>
```

Default for new features: `team-flow <feature> lite`.

---

## Behavior: end

**Step 1 — Find in-progress feature**

Scan `plans/` (skip `.archive/`). For each feature folder, read `PROGRESS.md`.
Look for `status: IN PROGRESS` or `Status: IN PROGRESS`.

**Step 2 — If a feature is in progress**

Print:

```
Feature: <feature-name>
Conversations done / total: <X> / <Y>
```

Ask:

```
Write a retro? (y/n):
```

- **y**: invoke `retro <feature>`
- **n**: print `All done. Changes committed? Run git commit if not.`

**Step 3 — If no feature is in progress**

Print:

```
Nothing in progress. All done.
```

---

## Behavior: pause

Scan `plans/` for a feature whose `PROGRESS.md` contains `status: IN PROGRESS`.
If found, write `status: PAUSED` to that feature's `PROGRESS.md`.

Print:

```
Session paused. Resume with /pathly go when ready.
```

---

## Behavior: meet

Scan `plans/*/STATE.json` sorted by modification time (most recent first).
Pick the active feature and run the meet workflow: consult one relevant role,
write a read-only consult note to `plans/<feature>/feedback/CONSULT_<role>.md`.

---

## Behavior: help (default when $ARGUMENTS is empty)

**Step 1 — Detect state**

1. If `args` is provided, use it as `FEATURE`. Otherwise scan `plans/` for the
   most recently modified feature folder.
2. Read `plans/$FEATURE/PROGRESS.md` if it exists.
3. Check `plans/$FEATURE/feedback/` for open files.
4. Infer rigor: **lite** (4 required files only), **standard** (all 8 files),
   **strict** (8 files + audit markers), **unknown** (no plan folder).
5. Classify state:
   - **no-feature** — no plans/ folder or no feature found
   - **storm-done** — `plans/STORM_SEED.md` exists, no plans folder yet
   - **plan-done** — plans folder exists, conversations TODO, no open feedback
   - **feedback-open** — feedback file(s) present
   - **build-done** — all conversations DONE, no RETRO.md yet
   - **retro-done** — RETRO.md exists

**Step 2 — Print state-aware menu**

### no-feature

```
═══════════════════════════════════════════
  Pathly — No active feature found
═══════════════════════════════════════════

  [1] Start a new feature          /pathly go <what you want>
  [2] Brainstorm an unclear idea   /pathly go storm
  [3] Import a PRD/BMAD file       prd-import / bmad-import
  [4] See all commands

Reply with 1–4:
```

### plan-done

```
═══════════════════════════════════════════
  <feature>  |  Plan ready
  Conv: <X> done · <Y> remaining
  Rigor: <lite|standard|strict>
═══════════════════════════════════════════

  [1] Continue building            /pathly go continue
  [2] Run full pipeline            team-flow <feature> build
  [3] Review current code          review
  [4] See all commands

Reply with 1–4:
```

### feedback-open

```
═══════════════════════════════════════════
  <feature>  |  Open feedback requires action
  Rigor: <lite|standard|strict>
═══════════════════════════════════════════

  Open files:
    <list each file → who must act>

  [1] Resume pipeline              /pathly go continue
  [2] Show feedback file content
  [3] See all commands

Reply with 1–3:
```

### build-done

```
═══════════════════════════════════════════
  <feature>  |  All conversations complete
  Rigor: <lite|standard|strict>
═══════════════════════════════════════════

  [1] Close feature (tests + retro)  /pathly end
  [2] Run tests only                  team-flow <feature> test
  [3] Write retro only                retro <feature>
  [4] See all commands

Reply with 1–4:
```

### retro-done

```
═══════════════════════════════════════════
  <feature>  |  DONE ✓
  RETRO.md written
  Rigor: <lite|standard|strict>
═══════════════════════════════════════════

  [1] Archive this feature         archive <feature>
  [2] Promote lessons              lessons
  [3] Start next feature           /pathly go <what you want>
  [4] Read the retro

Reply with 1–4:
```

**Step 3 — Full command reference (shown on "See all commands")**

```
── Core ──────────────────────────────────
  /pathly start   /pathly go      /pathly storm
  /pathly build   /pathly pause   /pathly meet
  /pathly end     /pathly help

── Specialized ───────────────────────────
  /pathly po      /pathly debug
  /pathly explore /pathly verify

── Catch-all ─────────────────────────────
  /pathly <anything>   Director routes intent

Run /pathly help for full descriptions and state-aware guidance.
```
