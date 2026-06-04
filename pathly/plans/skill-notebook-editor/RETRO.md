# Retro — skill-notebook-editor

Date: 2026-06-04

---

## What we built

A Jupyter-style Skill Notebook Editor embedded in Pathly Studio that lets developers compose AI agent skills visually. Skills open as interactive cell canvases where `##`-delimited body sections are fixed anchors and fragment capabilities can be dragged in from a live catalog, reordered, deleted, and previewed as a fully assembled prompt. The feature spans a Python FSM layer (4 new endpoints, a body parser, and a catalog reader) and a TypeScript Studio layer (new store, sidebar CATALOG mode, DnD canvas, preview panel, and notebook header with undo/redo).

---

## What went well

- Clean conversation breakdown: 1 Python conv + 3 TypeScript convs kept scope tight and each builder agent delivered 0 typecheck errors at handoff.
- FSM endpoint design was well-specified up front — `GET /skills/catalog`, `POST /skills/parse`, `POST /skills/preview`, and `PUT /skills/export` were all wired and returning valid JSON by end of Conv 1 with all smoke tests passing.
- Typecheck discipline held across all four conversations; the reviewer never had to chase type errors.
- Native HTML5 DnD (no external library) kept the dependency footprint clean and matched the non-functional requirement.
- Reviewer's two fixes (aria-labels and `loadSkill` try/catch) were small and precise — the final review round-trip was fast.
- The DESIGN.md + DESIGN_SPEC.md + preview.html pre-work meant builders had visual and structural reference before touching code.

---

## What was hard

- `scope_gate` repeatedly blocked the `BUILDING -> REVIEWING` transition in Convs 1 and 2 — required manual intervention to clear `SCOPE_VIOLATION.md` and advance the FSM. The gate fired four times before the feature progressed cleanly.
- In Convs 3 and 4 the gate was skipped with `no_build_baseline`, indicating the gate cannot yet diff TypeScript additions. This is a gap in automation coverage for Studio-heavy features.
- Six test failures surfaced at the TESTING stage that were not caught earlier: Sidebar routing to skill-notebook, `loadSkill` fragment cell shape, pop animation timing, global drag-active state, keyboard shortcut scope, and CSS token compliance. These required a full builder re-entry after what was supposed to be the final conversation.
- The FSM cycled back from REVIEWING to BUILDING between Convs 2 and 3 and again after the final review, creating ambiguity about whether the review-fix loop was intentional or a state machine quirk.

---

## Lessons

- Pre-define a `scope_gate` baseline snapshot for TypeScript features before starting Build, or mark the gate as `skip` for net-new file additions to avoid repeated manual unblocking.
- Add a lightweight acceptance smoke-check at the end of each conversation (not just typecheck) to surface test failures before the dedicated TESTING stage. The 6 post-review failures were all detectable from the user stories.
- Design-stage preview HTML is high value — builders referenced it throughout all four convs and it prevented misalignment on visual structure.
- Splitting Python and TypeScript into separate conversations is the right pattern; cross-language boundary confusion was zero.
- Reviewer fixing aria-labels and error handling (not logic bugs) suggests a checklist prompt for accessibility and error boundaries would catch these before review.

---

## Metrics

| Metric | Value |
|---|---|
| Conversations | 4 (1 Python + 3 TypeScript) |
| Review fixes | 2 (aria-label, loadSkill try/catch) |
| Test failures fixed | 6 |
| Final typecheck errors | 0 |
| Stories delivered | 8 (US-01 through US-08) |
| scope_gate blocks | 4 (manual clearance required) |
| Total cost (build + review + test) | ~$1.45 USD |
| Total wall time (build convs) | ~26 min |
