# Conversation Prompts — CliMonitorBar UI/UX Design Review (near-term)

---

## Conversation 1 — CSS + TSX styling pass

> Role: builder · Delivers: Stories 1, 2, 3

Read the following files before making any changes:
- `pathly/features/cli-command-center/goals/studio-climonitorbar-panel-a-ui-ux-design-review-3453c9bb/IMPLEMENTATION_PLAN.md`
- `pathly/features/cli-command-center/goals/studio-climonitorbar-panel-a-ui-ux-design-review-3453c9bb/USER_STORIES.md`
- `pathly/features/cli-command-center/goals/studio-climonitorbar-panel-a-ui-ux-design-review-3453c9bb/ARCHITECTURE_PROPOSAL.md`

Also read the current source files before editing them:
- `studio/src/renderer/src/components/CliMonitorBar/CliMonitorBar.module.css`
- `studio/src/renderer/src/components/CliMonitorBar/CliMonitorBar.tsx`
- `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.module.css`

### Task

Implement the 3 remaining design review changes (Steps 3a/3b, 7a/7b, 9):

**Step 3a — Add `.sectionLabelPrimary` to CliMonitorBar.module.css**
Add a new CSS class after `.sectionLabel` with elevated font-weight (600) and letter-spacing (0.08em). Use `composes: sectionLabel` if the module uses composition, or duplicate the base and add the overrides.

**Step 3b — Apply it to the FLOW label in CliMonitorBar.tsx:126**
Change `s.sectionLabel` → `s.sectionLabelPrimary` on the FLOW div only. ACTIVE and RECENT labels stay as-is.

**Step 7a/7b — FlowControlBar button sizing + disabled state in FlowControlBar.module.css**
- `.btn` height: 28px → 30px. Icon-btn variant: 24px → 26px.
- Add `.btn:disabled { opacity: 0.38; cursor: not-allowed; }` after the existing hover rule.

**Step 9 — Body padding token in CliMonitorBar.module.css**
Change `.body` hardcoded padding value to `var(--space-2) var(--space-1)`.

### Skip / do not touch

- Do NOT add `.sectionLabelMeta` (step 3c — superseded)
- Do NOT add `border-bottom` to `.flowSection` (step 8 — already present via FlowControlBar wrapper)
- Do NOT change ACTIVE or RECENT labels
- Do NOT touch `CodeIntelControl.tsx`, `SpawnQueuePanel`, any store files, or Python files

### Acceptance check

After editing, run:
```bash
cd studio && npx tsc --noEmit
```

All 3 stories from USER_STORIES.md must be satisfied. Report what was changed and confirm tsc passes.
