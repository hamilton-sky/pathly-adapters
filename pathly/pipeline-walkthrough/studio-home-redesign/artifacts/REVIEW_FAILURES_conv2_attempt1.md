# Review Failures — studio-home-redesign (Conv 1+2 final)

## Violations

### V1 — Dead `gridColumn` CSS in list/flex mode
**File:** `studio/src/renderer/src/components/HomeScreen.tsx` — lines 682, 687, 692

The three section wrapper divs inside the pinned/unpinned rendering block apply `gridColumn: '1 / -1'` unconditionally:

```tsx
<div style={{ gridColumn: '1 / -1' }}>           {/* line 682 — "Pinned" label */}
<div style={{ gridColumn: '1 / -1', ... }} />    {/* lines 687–691 — divider */}
<div style={{ gridColumn: '1 / -1' }}>           {/* line 692 — "Recent Projects" label */}
```

When `viewMode === 'list'` the parent is a flex container, not a grid. `gridColumn` has no effect in flex layout, making this dead CSS. The property should only be applied in grid mode.

**Rule violated:** IMPLEMENTATION_PLAN.md Phase 6 (section label wrappers) + pre-review context: "Should be conditional: `viewMode === 'grid' ? { gridColumn: '1 / -1' } : {}`"

**Severity:** Correctness — non-fatal today but will cause layout bugs if any future grid-spanning behaviour is expected to also apply in list mode, and it documents incorrect intent in the code.

---

### V2 — Subtitle `marginBottom` deviates from plan
**File:** `studio/src/renderer/src/components/HomeScreen.tsx` — line 603

Implementation: `marginBottom: '36px'`
Plan (IMPLEMENTATION_PLAN.md Phase 3): `marginBottom: '32px'`

**Rule violated:** IMPLEMENTATION_PLAN.md Phase 3 — "Add `marginBottom: '32px'` to the subtitle (total header-to-content gap)"

**Severity:** Minor cosmetic deviation from spec.

---

## Warnings (non-blocking)

- `HomeScreen.tsx:650` — The empty-state outer div is missing `textAlign: 'center'` (plan Phase 7 specifies it). With flex + `alignItems: 'center'` the visual result is similar, but text content inside `<span>` elements will not be centered if they wrap.

---

## Pass

- `types/index.ts` — `pinned?: boolean` field added correctly at line 69, no other type changes.
- Phase 2 — Sun/Moon toggle, LayoutGrid/List toggle: icons, active/inactive colors (`t.accent` / `t.textMuted`), button size (28×28px), borderRadius (6px) — all match plan.
- Phase 3 — Subtitle present, `maxWidth: 1100px` correct, grid/list conditional layout correct.
- Phase 4 — `getCardAccent` helper matches plan spec; `borderTop` accent + hover glow with `boxShadow` applied correctly.
- Phase 5 — Footer row layout (topic count + timeAgo left, Open button right) matches plan.
- Phase 6 — Pin/star button logic, `updateProject` call, pinned/unpinned split, section labels and divider all correct.
- Phase 7 — Empty state: FolderOpen icon, "No projects yet" title, "Open a folder to get started" subtitle — all present.
- No hardcoded credentials or injection risks found.
- No cross-layer dependency violations.
- All lucide-react icons sourced from existing dependency; no new dependencies introduced.
