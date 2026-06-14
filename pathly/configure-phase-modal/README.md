# ConfigurePhaseModal

The redesigned **Configure phase** dialog, split into small, reusable,
TypeScript components. Every component lives in its own folder with a `.tsx`
file and a co-located CSS Module, and is styled **only** with Pathly design
tokens (`var(--accent)`, `var(--bg-surface0)`, `var(--radius-md)`, …) — so it
re-themes automatically across all 12 palettes.

## Structure

```
ConfigurePhaseModal/
├── ConfigurePhaseModal.tsx          # standalone container (props/callbacks)
├── ConfigurePhaseModal.connected.tsx# ← app-wired container (store + fetch)
├── ConfigurePhaseModal.module.css
├── configurePhaseModalData.ts       # catalogs + default prompts
├── types.ts                         # StageName · ChipVariant · PhaseConfig
├── index.ts                         # barrel exports
└── components/
    ├── Modal/                       # scrim + dialog shell (portal)
    ├── StatePill/                   # BUILDING / TESTING … status pill
    ├── SectionLabel/                # uppercase label + divider rule
    ├── Chip/                        # one selectable pill
    ├── AddChip/                     # dashed “+ add” affordance
    ├── ChipGroup/                   # label + chip row + add  (single-select)
    ├── SegmentedControl/            # generic 2–3 option toggle
    ├── IconButton/                  # mono icon + label (edit / copy)
    ├── Button/                      # primary · ghost · quiet
    ├── AssemblyRecipe/              # host → agent → skill → assembled
    └── PromptPreview/               # toggle + inline edit + markdown body
```

Each piece is independent: `Modal`, `Chip`, `SegmentedControl`, `Button`,
`StatePill`, etc. are generic enough to reuse anywhere in the app.

## Usage

```tsx
import { ConfigurePhaseModal } from './ConfigurePhaseModal'

<ConfigurePhaseModal
  stage="BUILDING"
  onClose={() => setOpen(false)}
  onApply={(config) => saveStageConfig(config)}   // { host, agent, skill }
  onReset={() => clearStageConfig()}
  onOpenNotebook={(skill) => openSkillNotebook(skill)}
  skillPrompt={liveSkillMarkdown}                 // optional live text
  agentPrompt={liveAgentMarkdown}                 // optional → enables agent tab
/>
```

The modal manages its own `host` / `agent` / `skill` selection and reports out
through callbacks. Pass `hosts` / `agents` / `skills` to override the catalogs,
or `initial` to seed the current values.

## Wiring into the real Monitor app

Two containers ship in this folder:

| File | Owns | Use when |
| --- | --- | --- |
| `ConfigurePhaseModal.tsx` | local state only; side-effects via props | tests, Storybook, any host app |
| `ConfigurePhaseModal.connected.tsx` | Zustand store, `/flows/stage-config` fetches, catalog hooks, `window.pathly.fs` prompt loading, notebook nav, adapter map, **`CatalogDropdown`** | the actual Monitor — this is a drop-in for your existing `ConfigurePhaseModal.tsx` |

**To replace the old modal in `Monitor/ConfigurePhaseModal/`:**

1. Copy this whole folder’s `components/`, `types.ts`, and
   `ConfigurePhaseModal.module.css` in (the new CSS modules co-locate with each
   component, so the old monolithic `PromptPreview.module.css` /
   `AssemblyFlowBar.tsx` can be deleted).
2. Keep your existing `configurePhaseModalData.ts`, `hooks/`, and
   `CatalogDropdown/` — the connected container imports them unchanged.
3. Rename `ConfigurePhaseModal.connected.tsx` → `ConfigurePhaseModal.tsx`.
   Its public API is identical to today’s — `{ stage, onClose }` — so the call
   site in the Monitor (`<ConfigurePhaseModal stage={…} onClose={…} />`) needs
   **no change**.

The connected container holds `host`/`agent`/`skill` itself (so the fs-driven
prompt preview keeps working) and feeds the catalog browser back in through the
new `trailing` slot on `ChipGroup`.

## Requirements

- React 18 + TypeScript with CSS-Modules support
- `lucide-react` (icons) and `marked` (markdown) — already used in the app
- The global Pathly token stylesheet loaded once (provides the CSS variables)
