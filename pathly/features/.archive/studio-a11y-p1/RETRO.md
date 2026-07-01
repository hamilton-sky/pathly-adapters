# Studio A11y Phase 1 — Retrospective

## Plan Quality

**Conversation sizing:** Conversations 1 and 2 were well-sized (4 phases and 3 phases respectively, clean completion). Conversation 3 was slightly underestimated — the ContextMenu ARIA work itself was right-sized, but touching that file surfaced pre-existing `useTheme()`/inline-style CLAUDE.md violations that triggered an unplanned fourth fix conversation.

**Surprises:**
1. The reviewer flagged pre-existing `ContextMenu.tsx` violations (useTheme + inline styles) as in-scope because we modified that file. The plan explicitly said "keep pre-existing inline styles" but the reviewer applied CLAUDE.md rules strictly — correct behavior, but it required an unplanned CSS module extraction.
2. The FSM gate required `VERIFY.md` and `REVIEW.md` artifacts that weren't mentioned in any conversation prompt. Two gate failures needed manual resolution mid-pipeline.

**Missing from plan:** A pre-flight check of existing CLAUDE.md violations in every file listed as a touchpoint. ContextMenu had pre-existing `useTheme()` + inline-style violations before we added a single ARIA attribute. Listing it as a touchpoint implicitly brought those violations in scope for the reviewer.

## What Worked

- Conversation split at natural seams (chips / modals / menu+tokens) worked cleanly — no cross-conversation dependencies caused confusion.
- `useFocusTrap` as a shared hook was the right call — both modals consumed it identically with zero duplication.
- All 6 edge cases (EC-1 through EC-6) handled correctly on the first build attempt — EDGE_CASES.md did its job.
- `role="switch"` + `aria-checked` string literals (`"true"`/`"false"`) is the correct ARIA pattern; builder got it right.
- 22/22 acceptance criteria passed on first tester run.

## What to Improve Next Time

- **Pre-flight CLAUDE.md scan:** Before listing any file as a touchpoint, grep it for existing `useTheme()` calls and inline `style={{` props. Add a Phase 0 sub-task: "Check target files for pre-existing violations; if found, add a fix phase or explicitly note as accepted tech debt."
- **Document FSM gate artifacts in prompts:** The pipeline requires `VERIFY.md` (after build) and `REVIEW.md` (after review). Add a standard line to every conversation prompt: "After verification passes, write `pathly/plans/<feature>/VERIFY.md` with first line `RESULT: PASS`."
- **ContextMenu was a ticking clock:** Any time a file with inline styles is a touchpoint, assume the reviewer will require a CSS module extraction. Either budget for it or scope it out explicitly.

## Seed for Next Storm

> Phase 1 a11y fixes are complete: chip toggles are semantic buttons, modals have focus traps + dialog ARIA, ContextMenu has full keyboard navigation, disabled tokens replace opacity. Phase 2 scope (Tooltip `:focus-visible`, icon button 44px targets, muted text contrast, tab bar arrow keys) is well-defined and ready to plan. Key learning: always pre-flight check files for existing CLAUDE.md violations before listing them as touchpoints.
