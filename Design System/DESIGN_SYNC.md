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
- `components/Monitor/OutputTab.module.css`
- `components/FlowEditor/shared/panel.module.css`
- `components/FlowEditor/UnsavedChangesModal.module.css`
- `components/FlowWizard/FlowWizard.module.css`
- `components/FlowWizard/WizardFooter/WizardFooter.module.css`
- `components/FlowWizard/StepIndicator/StepIndicator.module.css`
- `components/FlowWizard/Step0Entry–Step7TransitionRules` (8 step files)
- `components/FlowWizard/YamlPreview/YamlPreview.module.css`
- `components/Settings/RadioCard.module.css`
- `components/Settings/PaletteSwatch.module.css`
- `components/SetupScreen/SetupScreen.module.css`

### Shared components (DS → Studio)
All ported as TypeScript + CSS modules under `components/ui/`:
- **Badge** — `Badge/Badge.tsx` + `Badge.module.css`; 5 preset variants (`core/flow/integration/body/neutral`) + custom color via `--badge-color`; replaced old `useTheme()` version
- **StatePill** — `StatePill/StatePill.tsx` + `StatePill.module.css`; FSM stage dot + label, tint + solid modes
- **ProgressBar** — `ProgressBar/ProgressBar.tsx` + `ProgressBar.module.css`; dynamic width/color via CSS custom properties
- **Spinner** — `Spinner/Spinner.tsx` + `Spinner.module.css`; size + color via CSS custom properties
- **Tabs** — `Tabs/Tabs.tsx` + `Tabs.module.css`; underline (in-panel) and pill (view-switch) variants, count badges
- **Card** — `Card/Card.tsx` + `Card.module.css`; optional title/actions header, interactive hover mode
- **Input** — moved to `Input/Input.tsx`; added `label`, `icon`, `size` props matching DS spec
- **Button** — added `icon` prop (leading icon slot)

---

## Left to do

### Token adoption — remaining CSS files
- `components/FlowEditor/VisualView/parts/ExportControls.module.css` — non-standard values (`border-radius: 7px`, `font-size: 12.5px`), skip or add custom tokens
- `components/HQ/**/*.module.css` — not yet swept
- `components/Terminal/**/*.module.css` — not yet swept
- `components/topbar/**/*.module.css` — verify existence

### Components — open verification
| Component | Status |
|---|---|
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

## Commit references
- `feat: sync design system tokens + component token adoption` — tokens + Button/Input initial update
- `feat: port DS components + complete token adoption sweep` — 6 new shared components, Input/Button updates, 19 CSS files swept
Branch: `hamiton/backend-refactor`
