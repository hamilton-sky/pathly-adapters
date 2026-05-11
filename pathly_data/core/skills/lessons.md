# lessons

This is the canonical, tool-agnostic Pathly behavior for the lessons workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Skill Contract

**Consumes:** `LESSONS_CANDIDATE.md` + `plans/.archive/*/RETRO.md` (up to last 6)
**Produces:** `LESSONS.md` (active lessons, planner reads this)
**When to run:** After any `retro` workflow, or manually when you want to update active lessons.

---

## Step 1: Read source material

Read in order:
1. `LESSONS_CANDIDATE.md` — all candidate lessons (may not exist yet)
2. Up to 6 most recent `plans/.archive/*/RETRO.md` files — scan the "What to Improve Next Time" sections

If neither exists, report: "No lessons found. Run retro on completed features first." and stop.

---

## Step 2: Find repeating patterns

Group candidates by similarity. A pattern qualifies for promotion if:
- It appears in **2 or more features** (same failure type, same stage, or same missing plan element)
- The failure stage is consistent (planning / implementation / review / test)

Do NOT promote:
- One-off issues specific to a single unusual feature
- Vague observations without a clear injection point
- Anything without a concrete "what to add to the plan"

---

## Step 3: Write LESSONS.md

Write `LESSONS.md` in the project root. Structure:

```markdown
# LESSONS.md — Active

_Last updated: <today> | Sources: <N> features_
_Max 12 lessons. Planner reads this before every plan._

---

## L-001: <brief title>

### Pattern
<what goes wrong — one sentence>

### Rule
<what the plan MUST do — one sentence>

### Injection
- <exact line or section to add to a specific plan file>
- <add more only if needed>

### Sources
<feature-a>, <feature-b> | Stage: <stage>

---

## L-002: ...
```

Rules for writing LESSONS.md:
- Maximum 12 lessons total
- If promoting would exceed 12, drop the lesson with the fewest sources
- Keep existing lessons that are still valid — this is an update, not a rewrite
- Order by number of source features descending (most-evidenced first)
- If two lessons conflict, keep the one with more source features; note the conflict in a comment

---

## Step 4: Report

```
LESSONS.md updated.

Active lessons: <N>
New this run: <titles of newly added lessons>
Dropped: <titles removed, if any>

Planner will apply these on the next `plan` run.
```
