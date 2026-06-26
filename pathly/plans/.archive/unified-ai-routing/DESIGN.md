# DESIGN — unified-ai-routing

Scope: the small UI surface introduced by the Router. Reuses existing Studio tokens
(`tokens.css`) and component rules (CSS modules, `data-*` variants, responsiveness,
one-component-per-subfolder, no inline styles).

## Design System Output

### Component: `AiTargetSelector/`
A single grouped dropdown that lists **Models** and **CLI Engines** in one control.

- **Structure** (own subfolder + CSS module):
  ```
  AiTargetSelector/
    AiTargetSelector.tsx        // ≤150 lines; renders the grouped <select>/listbox
    AiTargetSelector.module.css
  ```
- **Groups:** `Models` (from `modelManager` catalog: Ollama / GGUF / Brightsky) and
  `CLI Engines` (from `ADAPTER_META`, headless-capable only). Optional `Off` for summary use.
- **Value:** `{ type: 'model' | 'engine', id }` — the canonical `AiSelection`.
- **States** via `data-state`:
  - `data-state="ready"` — accent dot, selectable.
  - `data-state="unavailable"` — muted, e.g. Ollama not running / engine `noHeadless` → disabled option.
  - `data-state="loading"` — availability check in flight.
- **Tokens:** `var(--bg-mantle)`, `var(--border)`, `var(--text-primary)`, `var(--accent)`,
  `var(--text-muted)`. No hardcoded colors.
- **Responsiveness:** `width:100%`, `min-width:0`; the trigger label truncates with ellipsis,
  never forces overflow. Verified ≤200px.

### Consumers
- **ArtifactsView toolbar:** replace the current `localStorage` "Upload summary" `<select>`
  with `AiTargetSelector` (default = app default). Drop/upload uses the selected target.
- **Per-artifact:** each artifact card gets a small **target chip** (shows the saved
  `summary_selection`) + a **Re-summarize** icon button (`RotateCw`, `type="button"`,
  `aria-label="Re-summarize"`), reusing `MsgCard` action-row styling.
- **HQ:** `ModelSelector` keeps its current rich UX but sources its list from `modelManager`
  (no visual change required this feature).
- **Settings:** `SummarySettings` (3-bucket radio) is **removed**; the per-artifact + app-default
  selectors supersede it.

### Conversation 6 affordance (board)
- `phase`-type board messages render as a thin, muted timeline row in the Command Center
  (icon + `PHASE_START/DONE` + stage name), visually distinct from decisions/artifacts.
  No interaction; observability only.

### Interaction states (summary run)
- Trigger → card shows an inline spinner on the target chip.
- Success → summary text fills in; chip returns to ready.
- Error → chip shows `data-state="error"` (red) + tooltip with the failure; never blocks the board.

### Accessibility
- Selector: `aria-label`, keyboard-navigable options, `aria-expanded` on the trigger.
- Re-summarize button: explicit `type="button"` + `aria-label`.
