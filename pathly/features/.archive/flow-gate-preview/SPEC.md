# Flow Gate Preview — SPEC (planner decompose target)

A self-contained spec for Pathly's **planner** to decompose into a task DAG.

## Goal
Before a **flow** runs (board Run → Flow tab, team goal-executor, consultation-in-Evaluate),
show a **gate preview** so a human can see — and optionally trim — each stage's prompt before
any agent spawns. Single-agent / task / loop runs already get this transparency; flows don't.

## Who it's for / value
A supervisor about to launch a multi-stage flow wants to (a) see exactly what each stage will
send, and (b) trim a stage's sections for *this run only*, without editing the persistent
per-stage config.

## Requirements (user stories)
1. Clicking **Run** on a flow opens a modal with a small **vertical stepper** of the flow's stages.
2. Clicking a **stage** shows that stage's **composed prompt** in a collapsible banner.
3. Clicking **Sections** opens that stage's prompt in the Sections modal (assemble mode) to
   include/exclude sections and add abilities / system-prompts.
4. Trims are **use-once** (this run only) — never persisted to the stage config, never shown in
   the phase inspector.
5. **Confirm** runs the flow with each stage's trim applied.
6. Single-agent / task / loop gates are **unchanged**.

## Acceptance criteria
- The gate opens on the board Run → Flow path; the stepper lists the flow's real stages.
- Each stage's banner shows the **same** prompt that stage would spawn (compose parity).
- A trimmed stage spawns the trimmed prompt; an untrimmed stage composes normally.
- Trims do not appear in the phase inspector (not persisted).
- Renderer `tsc` clean; backend has a unit test for the per-stage override.

## Phases (natural DAG seams)
- **P1** — frontend gate + per-stage compose, wired into the board Run → Flow path; collect trims.
- **P2** — backend transient per-stage override channel (`/runner/start` → per-stage spawn).
- **P3** — the same gate for the team goal-executor + consultation-in-Evaluate entry points.

## References (already on this board)
- `BRIEF.md` — confirmed requirements + reuse targets.
- `DESIGN.md` — the architect's component/module breakdown + the transient-override data flow.
