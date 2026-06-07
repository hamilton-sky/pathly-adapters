# Design System → Studio Sync

Tracks which design system tokens, components, and patterns have been
ported into the Studio app (`studio/src/renderer/src/`).

---

## Done

### Tokens (`studio/src/renderer/src/styles/tokens.css`)
- Spacing scale — `--space-0` through `--space-24`
- Radius scale — `--radius-xs` / `sm` / `md` / `lg` / `xl` / `full`
- Shadow tokens — `--shadow-sm` / `md` / `lg` / `modal`
- Layout rails — `--sidebar-width: 248px`, `--topbar-height: 44px`, `--terminal-height: 240px`
- Motion — `--transition-fast`, `--transition-snappy`, `--ease-out`
- Typography extras — `--font-weight-bold`, display sizes (`xl/2xl/3xl`), line heights, `--type-metric-family`
- **Pipeline state colors** — `--state-planning/building/reviewing/testing/retro/done/error`
- Semantic aliases — `--surface-app/chrome/card/raised/well`, `--text-body/meta/faint`
- Brand gradient — `--brand-gradient`

### Components
- **Button** — added `secondary` and `cta` variants (were missing; only `primary`, `ghost`, `destructive` existed)
- **Input** — background, border, border-radius, font-size now use token vars; focus ring added

### Component CSS — hard-coded pixel sweep
Replaced hard-coded `px` font-sizes, border-radii, and transitions with token vars in:
- `components/ui/Button.module.css`
- `components/sidebar/Sidebar.module.css`
- `components/Monitor/Monitor.module.css`
- `components/Monitor/StageCard.module.css`
- `components/Monitor/StageModal.module.css`
- `components/FlowEditor/shared/panel.module.css`

---

## Left to do

### Token adoption — remaining CSS files
Hard-coded pixel values still exist in these files (not yet swept):
- `components/FlowWizard/**/*.module.css` (8 step files)
- `components/Monitor/OutputTab.module.css`
- `components/FlowEditor/VisualView/**/*.module.css` (StateNode, ExportControls, etc.)
- `components/topbar/**` (no module.css found yet — verify)
- `components/Settings/RadioCard.module.css`, `PaletteSwatch.module.css`
- `components/HQ/**/*.module.css` (StepQueue, ThinkingBlock, FlowControlBar, etc.)
- `components/Terminal/**`
- `components/SetupScreen/SetupScreen.module.css`

### Components — spec gaps still open
| Component | Gap |
|---|---|
| **Input** | No `label` prop, no leading icon support (DS spec has both) |
| **Button** | No `icon` prop (DS Button accepts an icon slot) |
| **Badge** | Studio `Badge.tsx` exists but doesn't match DS spec variants (`core`, `flow`, `integration`) |
| **StatePill** | Not ported as a standalone component — used ad-hoc in `Monitor` |
| **ProgressBar** | DS component exists; Studio uses inline progress bars without a shared component |
| **Spinner** | DS component exists; Studio has its own inline loader — no shared component |
| **Tabs** | DS has underline + pill variants; Studio uses ad-hoc tab patterns |
| **Card** | DS component exists; Studio has no shared Card component |
| **Tooltip** | Studio `Tooltip.tsx` exists — verify it matches DS spec |
| **ContextMenu** | Studio `ContextMenu.tsx` exists — verify it matches DS spec |

### Color format
- DS uses `color-mix(in srgb, ...)` for derived tokens (accent tints, badge backgrounds)
- Studio uses hard-coded `rgba(...)` equivalents — works in all modern browsers but diverges from the DS source; standardise when convenient

### Design System kit updates (separate from Studio)
UI kit HTML files in `Design System/ui_kits/` and the root-level mocks:
- `ui_kits/db-explorer/` — updated (CSS extracted, pill position, search bar, Conversations tab)
- `Monitor.html` — minor fixes pending (PASS/DONE badge chips, token format)
- `Canvas.html` — not yet reviewed
- `Skill Notebook.html` — not yet reviewed
- `Flow Builder.html` — not yet reviewed (maps to `FlowWizard`)

---

## Commit reference
`feat: sync design system tokens + component token adoption`
Branch merged into: `hamiton/backend-refactor`
