# Pathly — Agents & Skills Assessment

_Analysis of `core/agents/` and `core/skills/` — the behavioral contracts and
workflow procedures behind the Pathly system._

---

## 1. What this system is

`pathly-adapters` is not an application — it is a **packaging and distribution
system for an opinionated AI development workflow**. The real product is a set
of:

- **Agents** — tool-agnostic *behavioral contracts* defining how each role thinks
  (`core/agents/`).
- **Skills** — tool-agnostic *procedures* defining what each workflow does
  (`core/skills/`).

These are "stitched" with host-specific metadata (`adapters/<host>/_meta/*.yaml`)
and installed into AI host tools (Claude Code, Codex, Copilot).

```
core/agents/*.md     ← role contracts (how an agent THINKS)
core/skills/*.md     ← procedures     (what a workflow DOES)
        +
adapters/<host>/_meta/*.yaml  ← host metadata (model, tools, frontmatter)
        ↓ stitch
~/.claude/agents · ~/.codex/skills · VS Code ext  ← deployed artifacts
```

**The goal:** convert ad-hoc "vibe coding" into a **deterministic, file-backed
state machine** where specialized roles hand work to each other through plan
files and feedback files, with a Python FSM server enforcing transitions.

---

## 2. How it works

**Two axes — roles and stages.**

- **14 agents (roles):** `director`, `architect`, `planner`, `po`, `builder`,
  `designer`, `reviewer`, `tester`, `explorer`, `scout`, `web-researcher`,
  `quick`, `orchestrator`, `human`. Each is a *capability boundary*; the
  `tools:` frontmatter is runtime-enforced (e.g. `scout` cannot write;
  `reviewer` can write feedback files but cannot edit source or run Bash).
- **29 user-facing + 2 internal skills (procedures):** lifecycle controls
  (`start/go/pause/meet/end/help`), pipeline stages
  (`plan/design/build/review/test/retro`), and a `team` orchestrator that drives
  the FSM.

**The flow:**
`/pathly go <intent>` → `director` classifies intent + selects rigor
(`nano`/`lite`/`standard`/`strict`) → routes to `team` → `team` uses the **HTTP
FSM engine** (Python server on :8765, auto-started by `fsm-call`) or falls back
to the **LLM orchestrator** agent → FSM walks
`STORMING → PLANNING → BUILDING → REVIEWING → TESTING → RETRO → DONE`, spawning
the mapped agent per state.

**Communication is filesystem-native.** No shared memory — everything passes
through `plans/<feature>/feedback/*.md`. File present = issue open; deleted =
resolved. Strict priority order:
`HUMAN_QUESTIONS > ARCH_FEEDBACK > DESIGN_QUESTIONS > IMPL_QUESTIONS > REVIEW_FAILURES > TEST_FAILURES`.
State is recoverable from disk, so a crashed session can resume.

---

## 3. Strengths

| # | Strength | Evidence |
|---|----------|----------|
| 1 | **Crisp, self-policing role boundaries** — every agent names the *other role* that owns what it is tempted to do (architect=HOW not WHAT, planner=WHAT not HOW, reviewer reports never fixes, tester never edits source). | every agent's "What NOT to do" section |
| 2 | **Well-designed read-only investigation tier** — `scout`/`quick`/`web-researcher` are terminal (can't spawn), capped (2–15 tool calls), and produce structured output. "Wide scout + clustering + parallel launch" is a strong context-management pattern. | `scout.md`, repeated in builder/architect/planner/reviewer/tester |
| 3 | **Prompt-injection awareness is built in**, not bolted on. | `web-researcher.md:32-36`, `orchestrator.md:33-37` |
| 4 | **Defenses against classic LLM failure modes**: "never claim success without verify", "one question per turn", retry caps (max 2), risk-gated rigor escalation. | builder, tester, architect, planner, po |
| 5 | **Clean core→adapter→host separation** with a single source of truth in `core/`. | `README_routing.md:7-10` |

---

## 4. Issues & Solutions

### Severity legend
- **P0** — can cause silent runtime misbehavior.
- **P1** — documentation contradicts reality; misleads maintainers.
- **P2** — cosmetic / hygiene.

---

### ISSUE-1 (P0): Storage path inconsistency — `plans/` vs `pathly/plans/`

**Problem.** Skills disagree on where feature state lives:
- `plans/<feature>/` — ~25 skill files (e.g. `go.md`, `pathly.md`).
- `pathly/plans/<feature>/` — ~8 skill files (e.g. `team.md` feature detection).
- `explorer.md` writes to `explorations/<topic>/`, but `explore.md` says
  `pathly/explorations/<topic>/`. Same split exists for `debugs/`.

An agent following `go.md` scans `plans/`, while `team.md` auto-detects from
`pathly/plans/*/STATE.json`. If both prefixes appear in a real deployment,
feature auto-detection **silently misses features** and state can be split
across two trees.

**Solution.**
1. Pick one canonical root. Recommended: `pathly/plans/` (namespaced, avoids
   collision with any host's own `plans/`).
2. Sweep all of `core/skills/` and `core/agents/` to use the single prefix.
3. Add a constant/anchor (e.g. a documented `STORAGE_ROOT = pathly/`) referenced
   in `SKILLS_OVERVIEW.md` and the feedback-protocol section so future files
   inherit it.
4. Add a CI check that greps for the wrong prefix and fails the build.

---

### ISSUE-2 (P1): `team-flow/` vs `team/` naming drift

**Problem.** `SKILLS_OVERVIEW.md` repeatedly states sub-skills "live in
`core/skills/team-flow/`" and routes to `team-flow/discover`, `team-flow/plan`,
etc. The actual directory is `core/skills/team/` and the entry skill is
`team.md`. ~13 references use a `team-flow/` path that does not exist on disk.
The user-facing dispatcher resolves correctly (`pathly.md` maps
`team`/`flow`/`tf` → `pathly-team`), but the **documentation of where files live
is wrong**.

**Solution.** Choose one name and apply everywhere:
- Option A (less churn): keep the directory `team/`, update all `team-flow/`
  doc references to `team/`.
- Option B (clearer intent): rename the directory to `team-flow/` and update the
  adapter `_meta` + dispatcher references.
Recommended: **Option A** — fewer moving parts, no adapter changes.

---

### ISSUE-3 (P1): Director logic triplicated across `core/`

**Problem.** Intent classification + rigor selection is implemented three times:
- `agents/planning/director.md`
- `skills/flow/go.md`
- inline "Behavior: go" in `skills/flow/pathly.md`

They mostly agree, but `go.md` adds engine selection (`team` vs `team-http`) and
a "Contextual State Panel" that the director contract never mentions. Three
copies of one decision table is exactly the drift the `core/` single-source rule
exists to prevent — and here the rule is violated *within* core.

**Solution.**
1. Make `go.md` the single source for the routing procedure.
2. Reduce `director.md` to the *role contract* (mindset, boundaries) and have it
   reference `go.md` for the decision table instead of restating it.
3. In `pathly.md`, replace the inlined "Behavior: go" with a delegation to the
   `go` skill (it already delegates other subcommands this way).

---

### ISSUE-4 (P2): `director` filed under `planning/`

**Problem.** `director` sits *above* the orchestrator conceptually
(`README_routing.md` architecture diagram), but its file lives in
`agents/planning/` next to `architect`/`planner`/`po`. It is neither planning nor
support cleanly.

**Solution.** Move to a top-level `agents/routing/` (or `agents/entry/`)
directory, or document explicitly why it is grouped with planning. Low priority —
purely organizational.

---

### ISSUE-5 (P2): Typo'd directory `skills/team/pathly-controlls/`

**Problem.** Directory name has a double-l typo (`controlls`) and contains only a
`.gitkeep`.

**Solution.** Rename to `pathly-controls/` or remove if unused.

---

### ISSUE-6 (P1): `SKILLS_OVERVIEW.md` drifts because it is hand-maintained

**Problem.** The file's own footer says "update this file after any
`core/skills/` change" — a manual discipline that has already slipped (see
ISSUE-2). As the system grows (~45 files across 3 adapters), manual sync will
keep failing.

**Solution.** Add a lightweight consistency checker (script + CI step) that
verifies:
- every skill referenced in docs exists on disk;
- no skill references a path prefix outside the canonical `STORAGE_ROOT`;
- every `core/skills/*.md` has matching `_meta` entries in each adapter;
- doc cross-references (`team-flow/...`, etc.) resolve to real files.
Optionally generate the skill-map section of `SKILLS_OVERVIEW.md` from the files
rather than maintaining it by hand.

---

## 5. Fix priority order

1. **ISSUE-1** (P0) — path inconsistency. Highest value; prevents silent state loss.
2. **ISSUE-2 / ISSUE-3 / ISSUE-6** (P1) — naming drift, triplicated logic, and the
   checker that stops all three from recurring.
3. **ISSUE-4 / ISSUE-5** (P2) — organizational/cosmetic.

---

## 6. After the fixes — what this project is and where its value lies

_(Forward-looking reflection, assuming the issues above are resolved.)_

**How I would describe it.** Pathly is an **operating system for AI-assisted
software development** — a thin, file-native orchestration layer that turns a
general-purpose coding model into a disciplined team of specialists. It is not a
chatbot wrapper and not an agent framework SDK; it is a *methodology encoded as
prompts*, with a state machine to keep that methodology honest.

**The core idea.** A single large model is capable but undisciplined — it
refactors when asked to fix, claims success without testing, and loses the
thread across a long task. Pathly's bet is that you get more reliable output by
**splitting one model into narrow roles with enforced boundaries**, forcing them
to communicate through inspectable files, and gating progress behind a
deterministic FSM. The filesystem is the memory; the FSM is the conductor; the
roles are the orchestra.

**The value I see.**
- **Reproducibility & auditability.** Because every handoff is a file
  (`STATE.json`, `EVENTS.jsonl`, `feedback/*.md`), a run is inspectable,
  resumable, and reviewable after the fact. This is rare in agent systems and is
  genuinely valuable for teams who need to trust the output.
- **Portability.** The core/adapter split means the *methodology* outlives any
  single host. The same contracts deploy to Claude Code, Codex, and Copilot.
  That is a real moat — the workflow is the asset, not the tool integration.
- **Guardrails that match how LLMs actually fail.** Verify-before-done,
  one-question-per-turn, retry caps, read-only investigation tiers — these are
  earned lessons, not theory.
- **Human-in-the-loop by design.** `HUMAN_QUESTIONS.md` as a first-class blocking
  state means the system asks instead of guessing on consequential decisions.

**What could improve it further (beyond the bug fixes).**
1. **Make `core/` machine-checkable.** Once the paths are unified (ISSUE-1), add
   the consistency checker (ISSUE-6) and a JSON schema for the feedback-file
   protocol so contracts can be validated, not just read.
2. **Close the loop on the lessons system.** `retro → LESSONS_CANDIDATE.md →
   lessons → LESSONS.md → planner injection` is a strong feedback loop — but it
   depends on humans running `lessons`. Consider surfacing candidate lessons
   automatically at `end`/`archive` time.
3. **Observability.** A small Studio/CLI view of the FSM timeline and per-stage
   token cost (the `EVENTS.jsonl` data already supports this) would make the
   system's behavior legible to users, not just to maintainers.
4. **Test the contracts behaviorally.** Golden-path transcript tests per skill
   (given inputs → expected routing/decision) would catch prompt drift the same
   way unit tests catch code drift.
5. **Reduce ceremony for the small case.** `nano` mode exists, but the cognitive
   overhead of the full vocabulary (rigor levels, feedback files, FSM states) is
   high for newcomers. A guided first-run that hides the machinery until needed
   would lower the adoption barrier.

**Bottom line.** The conceptual design is strong and unusually mature for a
prompt-based system: filesystem-as-truth, runtime-enforced tool boundaries,
roles that name their own anti-patterns, and a clean packaging split. The
weaknesses today are *consistency drift*, not conceptual flaws — the natural
entropy of hand-maintained Markdown contracts. Fix the path inconsistency, kill
the duplicated logic, and add a checker to hold the line, and what remains is a
genuinely good idea executed with real discipline: **a portable, auditable,
role-based methodology for getting trustworthy work out of coding models.**
