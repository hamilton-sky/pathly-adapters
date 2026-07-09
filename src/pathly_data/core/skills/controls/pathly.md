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
| `meet` | — | → **pathly-meet** skill directly |

### Specialized commands (direct to skill — no director routing)

| subcommand | aliases | behavior |
|---|---|---|
| `build` | `b` | → **pathly-build** skill directly |
| `storm` | — | → **pathly-storm** skill directly |
| `plan` | `p` | → **pathly-plan** skill directly |
| `design` | `d` | → **pathly-design** skill directly |
| `review` | `r` | → **pathly-review** skill directly |
| `test` | `t` | → **pathly-test** skill directly |
| `retro` | — | → **pathly-retro** skill directly |
| `archive` | — | → **pathly-archive** skill directly |
| `lessons` | — | → **pathly-lessons** skill directly |
| `team` | `flow`, `tf` | → **pathly-team** skill directly |
| `po` | — | → **pathly-po** skill directly |
| `debug` | — | → **pathly-debug** skill directly |
| `explore` | — | → **pathly-explore** skill directly |
| `verify` | — | → **pathly-verify-state** skill directly |
| `prd-import` | `import` | → **pathly-prd-import** skill directly |

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
  3. /pathly design  — generate a DESIGN.md visual spec (style, palette, fonts, UX rules)
  4. /pathly build   — implement conversation by conversation
     (review + test happen automatically inside the pipeline)
  5. /pathly end     — retro + archive

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

Delegate entirely to the `go` skill. Pass `args` as `$ARGUMENTS` to the `go` skill
and follow its procedure from Step 0.

---

## Behavior: end

**Step 1 — Find in-progress feature**

Scan `pathly/features/*/STATE.json` (skip `.archive/`). Look for a feature whose `current` state
is active (in progress) — not `IDLE`, `DONE`, or a `*_PAUSED` state.

**Step 2 — If a feature is in progress**

Print:

```
Feature: <feature-name>
Tasks done / total: <X> / <Y>
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

Scan `pathly/features/*/STATE.json` for a feature in an active (in-progress) state.
If found, report the pause to the FSM (`pathly-fsm-call complete-stage --flow pause --topic <feature>`); the FSM persists the paused state.

Print:

```
Session paused. Resume with /pathly go when ready.
```

---

## Behavior: meet

Scan `pathly/features/*/STATE.json` sorted by modification time (most recent first).
Pick the active feature and run the meet workflow: consult one relevant role,
write a read-only consult note to `pathly/features/<feature>/feedback/CONSULT_<role>.md`.

---

## Behavior: help (default when $ARGUMENTS is empty)

**Step 1 — Detect state**

1. If `args` is provided, use it as `FEATURE`. Otherwise scan `pathly/features/` for the
   most recently modified feature folder.
2. Read `pathly/features/$FEATURE/STATE.json` if it exists.
3. Check `pathly/features/$FEATURE/feedback/` for open files.
4. Infer rigor: **lite** (3 required files only), **standard** (all 7 files),
   **strict** (7 files + audit markers), **unknown** (no plan folder).
5. Classify state:
   - **no-feature** — no pathly/features/ folder or no feature found
   - **storm-done** — `pathly/features/STORM_SEED.md` exists, no plans folder yet
   - **plan-done** — plan folder exists, board tasks not yet done, no open feedback
   - **feedback-open** — feedback file(s) present
   - **build-done** — all conversations DONE, no RETRO.md yet
   - **retro-done** — RETRO.md exists

**Step 2 — Fetch menu from FSM and render**

Invoke `Skill("pathly-fsm-call")` to call the `/status` endpoint.

If the response contains a `menu` object with one or more items, render it as:

```
═══════════════════════════════════════════
  {menu.title}
  {menu.subtitle}
═══════════════════════════════════════════

  [1] {items[0].label:<32} {items[0].command}
  [2] {items[1].label:<32} {items[1].command}
  ...

Reply with 1–{N}, or type a command directly:
```

Wait for user input. Route:
- **Number N**: execute `items[N-1].command`
- **Free text**: treat as intent → route via **go** behavior

If the FSM is unreachable or returns no menu items, use this fallback:

```
═══════════════════════════════════════════
  Pathly — No active feature found
═══════════════════════════════════════════

  [1] Start a new feature          /pathly go <what you want>
  [2] Brainstorm an idea           /pathly storm
  [3] Import a PRD/BMAD file       /pathly prd-import
  [4] Explore the codebase         /pathly explore

Reply with 1–4, or describe what you want:
```

**Step 3 — Full command reference (shown on "See all commands")**

```
── Core ──────────────────────────────────
  /pathly start   /pathly go      /pathly storm
  /pathly build   /pathly pause   /pathly meet
  /pathly end     /pathly help

── Pipeline ──────────────────────────────
  /pathly plan    /pathly design  /pathly build
  /pathly review  /pathly test    /pathly retro
  /pathly archive /pathly lessons /pathly team

── Specialized ───────────────────────────
  /pathly po      /pathly debug
  /pathly explore /pathly verify
  /pathly prd-import

── Catch-all ─────────────────────────────
  /pathly <anything>   Director routes intent
```
