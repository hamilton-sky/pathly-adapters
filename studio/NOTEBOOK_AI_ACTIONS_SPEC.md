# Notebook AI Actions — Design Spec

Covers three interrelated features:
1. **Prompt Exposure** — user can see and edit the prompt sent to Claude
2. **Split Configuration** — configurable granularity for both AI-split and cell-split
3. **Analysis Persistence** — analysis result survives panel close

---

## 1. Prompt Exposure

### The problem

Both Split and Analyze send a fixed prompt to Claude. Users who get a bad result have no way to understand why or adjust the behavior without rebuilding the app.

### Who this is for

- **End users**: "I ran Split and it made 12 tiny cells — I wish it had stayed coarser." One-time correction.
- **Power users / devs**: "I want every analysis to include a section on tone consistency." Saved default.

---

### The button group pattern

The main button (Split / Analyze) and a small settings icon form a **split-button pill** — one visual unit, two click targets.

```
┌──────────────┬──┐
│  ✂ Split     │⚙ │   ← left: runs the action · right: opens peek modal
└──────────────┴──┘

┌──────────────┬──┐
│  ⊞ Analyze   │⚙ │
└──────────────┴──┘
```

The `⚙` icon is `SlidersHorizontal` (Lucide). It shares the button pill's border via a left divider line — not a separate standalone button. Tooltip on the icon: `"View or edit the prompt sent to Claude"`.

---

### The peek modal

Opens anchored **below the ⚙ icon** on click. Not a full overlay — a small floating card.

```
┌────────────────────────────────────────────┐
│  PROMPT — Split                       ╳   │
│  Reads: pathly-build.md                    │
├────────────────────────────────────────────┤
│                                            │
│  You are restructuring a Pathly skill…     │   ← monospace textarea, editable
│  …                                         │      auto-grows, max 260px tall
│                                            │
├────────────────────────────────────────────┤
│  [Reset]        [Use once]  [Save default] │
└────────────────────────────────────────────┘
```

**Width:** 400px  
**Font:** `'Fira Mono'`, 11px, `color: var(--text-secondary)`  
**Surface:** `background: var(--bg-mantle)`, `border: 1px solid var(--bg-surface1)`, `border-radius: 8px`, `box-shadow: 0 4px 20px rgba(0,0,0,0.4)`  
**Context line:** skill file name (not full path), color `var(--text-muted)`, 10px

**Buttons:**

| Button | Behavior |
|---|---|
| Reset | Reverts textarea to the built-in default prompt (does not save) |
| Use once | Sends the edited prompt this run only — next run uses the default |
| Save default | Persists to `localStorage` key `prompt_override_split` / `prompt_override_analyze` — used every subsequent run |

**Close behavior:** clicking outside or pressing Escape closes without running. Opening the modal does **not** start the AI run — that still happens only when the main button (Split / Analyze) is clicked.

---

### State management

```ts
// In useNotebookAgentActions or a new usePromptOverride hook
const STORAGE_KEY_SPLIT   = 'prompt_override_split'
const STORAGE_KEY_ANALYZE = 'prompt_override_analyze'

// Read at run time (after any "Save default")
function getEffectivePrompt(
  builder: (path: string) => string,
  storageKey: string,
  filePath: string
): string {
  const saved = localStorage.getItem(storageKey)
  return saved ?? builder(filePath)
}
```

`useOnce` state: a `useRef<string | null>` — set when the user clicks "Use once", consumed by the next `handleSplit` / `handleAnalyze` call, then cleared. Falls back to `getEffectivePrompt` on the run after.

---

### For Split: granularity shortcut

Inside the Split peek modal, above the textarea, add a **Granularity** row:

```
Granularity:  [Coarse]  [● Medium]  [Fine]
```

This does not replace the full prompt editor — it appends a sentence to the prompt automatically:
- **Coarse** → `"Prefer larger sections — 8–15 lines of content per cell."`
- **Medium** (default) → no addition
- **Fine** → `"Prefer fine-grained cells — 2–5 lines of content per cell."`

The user can still edit the full prompt in the textarea and override this.

---

## 2. Split Configuration

### Two split paths, same config

There are two ways to split in the notebook:

| Path | Where | Current behavior |
|---|---|---|
| Toolbar **Split** button | AI-powered, runs Claude | Always produces `##` sections |
| Body cell `···` menu → "Split into cells" | Local parser, no AI | Splits on `# ` and `##` hardcoded |

Both should share a **split depth** setting.

---

### SkillSplitModal header controls

Add a control row to the `SkillSplitModal` header, between the subtitle and the cells list:

```
Split on:  [# H1 only]  [## H2]  [### H3]
```

Default: `##` (current behavior preserved). Selecting a different level re-runs `parseMdToCells` on the current content with the new depth.

Updated `parseMdToCells` signature:

```ts
function parseMdToCells(raw: string, depth: 1 | 2 | 3 = 2): ProposedCell[]
```

Depth 1 → split on `# ` only  
Depth 2 → split on `#` and `##` (current default)  
Depth 3 → split on `#`, `##`, and `###`

The selected depth is passed in as a `splitDepth` prop from the parent (BodyCell / NotebookHeader). Parent stores it in local state — not persisted, resets per session.

---

## 3. Analysis Persistence

### The problem

Closing the AnalysisPanel deletes the `.analysis` file. Users cannot reopen it. This makes the feature feel destructive — one accidental close loses the report.

---

### Recommended approach: persistent toolbar indicator

Add a **"View Analysis"** toggle button to the toolbar, right of the Analyze button. It behaves exactly like the existing "Review draft" button.

```
[Analyze ⚙]   [⊞ Analysis ✦]      ← ✦ glow means a report exists
```

**Icon:** `FileSearch` (Lucide)  
**States:**

| State | Visual |
|---|---|
| No analysis file | Button dimmed, `aria-disabled`, tooltip: "No analysis yet — run Analyze first" |
| File exists, panel closed | Button glows amber (`data-has-analysis="true"`), tooltip: "Analysis ready — click to open" |
| Panel open | Button active/pressed style, tooltip: "Close analysis panel" |

Clicking toggles the panel open/closed **without deleting the file**.

---

### AnalysisPanel changes

Remove the current "close = delete" behavior. Replace with a footer row:

```
┌─────────────────────────────────────────┐
│  ANALYSIS — pathly-build                │
│  ...rendered markdown report...         │
│                                         │
│  [Open in editor]       [Discard ╳]    │  ← footer
└─────────────────────────────────────────┘
```

**Open in editor** → opens the `.analysis` file in the notebook source editor (same code path as opening any `.md` file via the file tree). The user can read, copy, or annotate it freely.

**Discard** → deletes the `.analysis` file, closes the panel, clears the toolbar indicator.

**Auto-replace:** when a new Analyze run starts, it overwrites the existing `.analysis` file. The panel refreshes automatically (it already polls the file path from the store).

---

### uiStore additions

```ts
notebookAnalysisPath: string | null      // already exists
notebookAnalysisPanelOpen: boolean       // NEW — decouples file existence from panel visibility
setNotebookAnalysisPanelOpen: (v: boolean) => void
```

The toolbar indicator derives its glow from `notebookAnalysisPath !== null`. The toggle controls `notebookAnalysisPanelOpen`. AnalysisPanel renders when `notebookAnalysisPanelOpen && notebookAnalysisPath`.

---

## Implementation order (suggested)

1. **Tooltip text** — done (contextual labels with skill name)
2. **Analysis persistence** — add `notebookAnalysisPanelOpen` to store, add toolbar button, update AnalysisPanel footer — ~2h
3. **Split depth config** — update `parseMdToCells`, add header control to `SkillSplitModal` — ~1h
4. **Prompt peek modal** — new `PromptPeekModal` component + `usePromptOverride` hook, split-button pill in header — ~3h
5. **Granularity shortcut** in peek modal — ~30min

---

## Open question (from PO)

Before building the full peek modal: is the primary user pain **"I got a bad result and don't know why"** (read-only transparency is enough) or **"I want to tune the behavior regularly"** (editable + save is needed)?

If the answer is "bad result debugging" → ship the Analysis persistence (#2) first, add a "View last prompt" read-only link in the AnalysisPanel footer before building the full edit flow.
