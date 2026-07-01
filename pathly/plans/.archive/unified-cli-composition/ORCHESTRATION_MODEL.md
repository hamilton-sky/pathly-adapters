# Orchestration Model — one spawn primitive, context = the knobs

> **Status:** design decision (recorded 2026-06-28). Resolves the "which orchestration
> surface is canonical — FSM flow vs goal-executors vs board-DAG" question by reframing
> it: there is no canonical *surface*; there is one **spawn primitive** whose **context**
> decides everything. Companion to [DESIGN.md](DESIGN.md) (the CLI-composition P0/P1) and
> [../../../docs/WHAT_IS_PATHLY.md](../../../docs/WHAT_IS_PATHLY.md).

---

## The reframe: two axes, not three surfaces

The three "surfaces" (FSM flow · goal→task-DAG executors · board-DAG scheduler) are not
competing engines. They are cells in a grid of **(is there a goal behind it?) × (what
execution shape?)**:

```
                         EXECUTION SHAPE  (how the agents run)
                   single        loop          team          flow (FSM)
               ┌────────────┬─────────────┬─────────────┬───────────────┐
  STANDALONE   │ MD editor: │     —       │     —       │ ad-hoc flow   │
  (no goal)    │ Analyze /  │             │             │ run any flow  │
               │ Split/Summ │             │             │ you define    │
               ├────────────┼─────────────┼─────────────┼───────────────┤
  ON A GOAL    │ board      │ frontier    │ team exec   │ team task →   │
  (DAG-backed) │ single     │ loop        │             │ runs an FSM   │
               └────────────┴─────────────┴─────────────┴───────────────┘
```

- A user can **define and run a flow of agents** (FSM), any shape (the **flow** column, standalone).
- A user can **run single / loop / team on a goal** (the **ON A GOAL** row).
- **Planner & consultation** are *decomposers*: they create the goal's DAG (`type=task` +
  `depends_on`) for **any plan type** (coding, research, …). The user's chosen **executor**
  then runs that DAG. The DAG is already plan-agnostic; the decomposer prompt must become so too.
- **Standalone single** agents (MD-editor Analyze/Split/Summary) are the degenerate cell:
  one transform, no goal.

The FSM flow is just **one execution shape** (a fixed-shape pipeline), not a separate world.

---

## The keystone: the spawn context (a.k.a. the "on a goal" flag)

Every agent spawn carries a small **context object**. The presence of `goal_id` IS the
"on a goal" flag. That one input selects the composition profile, the lifecycle, and the
feedback surface — so the same machinery serves every cell of the grid:

```
   spawn(skill, ctx)
        ctx = { goal_id?, scope, executor, kind:'transform'|'agent', driver }
                              │
              ┌───────────────┴────────────────┐
         goal_id PRESENT                   goal_id ABSENT
        "on a goal"                       "standalone"
              │                                 │
              ▼                                 ▼
   ┌──────────────────────────┐   ┌──────────────────────────────┐
   │ GOAL-BACKED profile       │   │ STANDALONE profile            │
   │ fragments:                │   │ fragments:                    │
   │  comms-post               │   │  client-file-output           │
   │  catalog-pull             │   │  artifact-transform           │
   │  board-start-context      │   │  (transforms) — or just the   │
   │  task-dag-post            │   │  skill body (a bare agent)    │
   │ lifecycle: claim →        │   │ lifecycle: write output file, │
   │  complete / fail the task │   │  done                         │
   │ feedback: goal RunPill    │   │ feedback: the action's own    │
   │  + board status posts     │   │  pill; no board lifecycle     │
   └──────────────────────────┘   └──────────────────────────────┘
```

This is the same **fragments** system from [DESIGN.md](DESIGN.md), *parameterized* by
context. P0 builds the **standalone-transform** profile; the **goal-backed** profile is
`comms-post` + `catalog-pull` + `board-start-context` + `task-dag-post`, already specced.

### Why this resolves "which surface is canonical?"

It makes it a non-question. **The spawn is the one primitive; the context is the knobs.**
No surface "wins" — the context decides how an agent is wired.

```
  ONE spawn primitive
     knobs ─┬─ goal context?   (goal_id present → board-wired)   ← the flag
            ├─ execution shape (single | loop | team | flow)
            ├─ driver          (headless [default] | interactive — both VISIBLE PTYs)
            └─ kind            (transform | agent)
```

**Visibility is not a knob — it is a constant.** Every CLI-engine spawn opens a *visible*
PTY tab (`aiRouter.ts` reveals it via `openTab`, "like every other CLI-engine spawn"); there
is no hidden/background spawn. The headless↔interactive split is the **loop driver**, not
visibility: **headless** (default) injects the prompt and the PTY **exits when the agent
finishes** (queued through the spawn gate); **interactive** lets the human type and the shell
**stays open** (rejected over cap). Both run in a visible tab — the in-place pill is just the
primary feedback layered on top of it.

(This is the same "unify the knobs" direction already recorded for the runner/interactive
primitive — the "on a goal" flag is simply another knob.)

---

## Vocabulary: fragment · skill · profile

Keep three layers, three names — never blur them:

| Layer | Name | Means | Example |
|---|---|---|---|
| atomic block | **fragment** | one reusable prompt block (`fragments/*.md`) | `comms-post`, `client-file-output` |
| task body | **skill** | "what to do" — the agent's task | `development/summarize`, `team/build` |
| context bundle | **profile** | "how it connects to Pathly" — the fragments chosen by context | `standalone-transform`, `goal-backed` |

> **Composition is keyed by skill, not flow.** The manifest comment says it plainly: a skill
> reused across flows composes *identically*. What varies by context is the **profile**.

One equation, every cell of the grid:

```
composed prompt = skill (body)
                + defaults              (always: progress-logging)
                + profile[context]      (the wiring — selected by goal_id presence)
                + skill's own fragments (intrinsic extras)
                  └─ dedup, then drop cap-gated (e.g. spawn-rules if !can_spawn)
```

**The profile is selected, not branched.** This is the `goal_id`-as-flag idea from the keystone
made concrete: instead of an `if goal_id:` in code AND the transform fragment list copy-pasted
across five skills, the standalone/goal-backed bundles live in a manifest `profiles:` map
(renamed from today's `blocks:`) and the resolver looks one up by context. That single change is
BOTH the P1 "spawn-context flag" work AND the DRY of the five transform skills.

Fragments themselves cluster by what they wire — a naming **convention** now; a role-prefix file
rename is deferred (the fragment set is still growing through P1):

```
  board      comms-post · catalog-pull · board-start-context · task-dag-post
  capture    client-file-output · artifact-transform · completion-report
  lifecycle  progress-logging · feedback-protocol
  delegate   spawn-rules · scout-choreography
```

---

## Phased path: C now → A as the north star

- **Now (Solution C — crisp two-lane boundary, low risk):**
  - Draw the boundary in docs + UI: **FSM flows = fixed governed pipelines**;
    **goal→DAG = ad-hoc / dynamic goals**. The `team` executor is the **single documented
    bridge** (a DAG task that needs a full pipeline spawns an FSM flow).
  - Make the spawn **context** explicit (`goal_id?`, `executor`, `kind`) and route the
    fragment composition profile off it.
  - Unify the two entry points' labeling so the user always knows which lane they're in.
- **North star (Solution A — board-DAG as the universal substrate):**
  - Introduce **"a flow = a DAG template"**: `decompose` can stamp a pipeline as a DAG,
    and the FSM becomes a **pipeline executor** over that DAG.
  - Migrate incrementally through the existing `team` seam until the **board-DAG is the one
    substrate** and the FSM is one executor among many.
  - This is what lets a user **visually define / create / monitor any multi-agent flow on
    the board** — the product vision.

---

## Naming fixes (cheap; do alongside C — flagged by the blind-scout audit)

- `start_run(interactive=True)` **default** is the bug — the *name* is fine. The code
  (`terminal.py:205-227`) shows `interactive` correctly selects the **driver**: `True` →
  `resolve_interactive_argv` (human can type; requires `PATHLY_RUNNER_EARLY_ADVANCE=1`),
  `False` → headless one-shot. **Both are visible PTYs**, so do NOT rename it to `visible_pty=`
  (visibility is a constant, not a knob). The fix is to **flip the default to `False`** so the
  headless-primary framing holds — the current `True` default even raises without the
  early-advance flag (so callers already pass `interactive=False` everywhere).
- The **FSM is named like an orchestrator but is passive** (it never spawns). Document
  loudly, or rename: FSM = "transition engine"; the **supervisor** is the orchestrator/driver.
- `runnerStore` defaults to `'interactive'` → align with the headless-primary framing.

---

## Acceptance for this model (when C is done)

1. A single spawn entry point accepts a context `{ goal_id?, scope, executor, kind }`; the
   fragment composition profile is selected by `goal_id` presence (board-backed vs standalone).
2. The two UI lanes (define/run a flow · create/run a goal) are clearly labeled; the user
   never has to guess which engine runs their work.
3. `team` is the only documented FSM↔DAG bridge; `single`/`loop` are board-DAG only;
   the FSM flow does not silently reach into the DAG.
4. The decomposer (planner/consultation) produces a plan-type-agnostic DAG (coding,
   research, …), and any executor can run it.
