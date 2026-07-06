# Implementation Plan — CliMonitorBar UI/UX Design Review (near-term)

> Rigor: lite · 1 conversation · Builder role

---

## Phase 1 — CSS + TSX styling pass (Conversation 1)

Delivers Stories 1, 2, 3. All changes are CSS-module-local or a single className swap.

### Step 1 — Add `.sectionLabelPrimary` to CliMonitorBar.module.css

Location: `studio/src/renderer/src/components/CliMonitorBar/CliMonitorBar.module.css`

Add after the existing `.sectionLabel` rule:

```css
.sectionLabelPrimary {
  composes: sectionLabel;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--foreground);
}
```

If `--foreground` is not available, use `var(--color-foreground)` or inherit. Match the existing token vocabulary in the file.

### Step 2 — Apply `.sectionLabelPrimary` to FLOW label (CliMonitorBar.tsx:126)

Location: `studio/src/renderer/src/components/CliMonitorBar/CliMonitorBar.tsx`, line ~126.

Change:
```tsx
<div className={s.sectionLabel}>FLOW</div>
```
to:
```tsx
<div className={s.sectionLabelPrimary}>FLOW</div>
```

Do NOT change ACTIVE or RECENT labels — they keep `s.sectionLabel`.

### Step 3 — Fix `.body` padding token (CliMonitorBar.module.css:105)

Location: `studio/src/renderer/src/components/CliMonitorBar/CliMonitorBar.module.css`, `.body` rule.

Change `padding: 4px` (or equivalent) to:
```css
padding: var(--space-2) var(--space-1);
```

### Step 4 — Bump `.btn` height + add `:disabled` rule (FlowControlBar.module.css)

Location: `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.module.css`

- Lines ~20-21: change `.btn` height from `28px` → `30px` and icon-btn variant from `24px` → `26px`.
- Add after the existing `.btn:hover:not(:disabled)` block:
```css
.btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}
```

Verify the `.btnDisabled` class (line ~62) and `:hover:not(:disabled)` guard are unaffected — they compose cleanly with the new pseudo-class rule.

### Step 5 — Skip confirmations

- Do NOT edit step 8 (`.flowSection border-bottom`) — skip.
- Do NOT add `.sectionLabelMeta` (step 3c) — skip.
- Verify (read-only) that steps 1, 2, 4, 5, 6 are still present as expected in source.

### Step 6 — Type-check

Run:
```bash
cd studio && npx tsc --noEmit
```

Fix any type errors before completing.

---

## Out of scope (do not implement)

- North-star `CliCommandCenter` modal (`CliCommandCenter.tsx`, `FlowCard`, `EngineCard`, `uiStore.cliCommandCenterOpen`)
- `useSessionActions` hook extraction — useful future refactor but not required by this goal's stories
- Any Python / FSM / IPC / backend changes

---

## Delivery checklist

- [ ] `.sectionLabelPrimary` class present in CliMonitorBar.module.css
- [ ] FLOW label in CliMonitorBar.tsx uses `s.sectionLabelPrimary`
- [ ] ACTIVE/RECENT labels unchanged (still `s.sectionLabel`)
- [ ] `.btn` height = 30px / icon-btn = 26px in FlowControlBar.module.css
- [ ] `.btn:disabled` rule present (opacity: 0.38, cursor: not-allowed)
- [ ] `.body` padding = `var(--space-2) var(--space-1)` in CliMonitorBar.module.css
- [ ] No step 8 border-bottom added (skip)
- [ ] No `.sectionLabelMeta` added (skip)
- [ ] `tsc --noEmit` passes clean
