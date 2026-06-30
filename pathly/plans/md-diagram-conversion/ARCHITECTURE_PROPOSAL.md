# Architecture Proposal — md-diagram-conversion

**Branch:** `claude/md-diagram-conversion-wze4x3`
**Layer:** Studio (Electron / React renderer)
**Status:** Implemented & shipped on `fix/goal-executor-cwd` (copy-in + Phase 7 review + Phase 8 acceptance done). See **As-built decisions** below.
**Rigor:** standard

> All file paths below are relative to `studio/src/renderer/src/` unless prefixed with `studio/`.

---

## As-built decisions (supersede the design where noted)

**R6 — Diagram prompts use presets BY DESIGN, not fragment composition.**
§5 below planned the diagram action to default to `composeClientSkill('development/diagram')` (fragments),
mirroring Split/Analyze. The build deliberately did **not** take that path: the diagram action resolves its
prompt via `resolvePrompt` over the editable `DIAGRAM_PRESETS` (gear/peek modal). This is intentional:

1. **Different output contract.** Split/Analyze write one whole derived file to `out_path`, so they compose
   `client-file-output` + `artifact-transform`. Diagram **appends a schema'd entry** (`DiagramEntry`) to a
   JSON sidecar (`.diagrams.json`) — a different shape those fragments don't describe. Reusing them cleanly
   isn't possible; it would need a bespoke append-contract fragment.
2. **Interactive UX.** Presets are user-editable and previewable (the gear modal, in both the header pill
   and the gallery panel) — better for a one-click editor action than an opaque composed prompt.
3. **The real artifact contract lives elsewhere.** A canonical "artifacts register on the board" mechanism
   (reusable `artifact-register` fragment + `artifact-manifest.yaml` + `ensure_attached` reconciler) is
   designed in **pathly-entity-model Phase 2** (not yet built). A one-off diagram fragment now would
   duplicate it and later be ripped out. **Future path:** when entity-model Phase 2 lands, make a generated
   diagram a first-class board artifact that registers via `artifact-register`, instead of (or alongside)
   the local sidecar. Pointer planted in `pathly/plans/pathly-entity-model/FEATURE_INDEX.md`.

Consequence: §5's `composeClientSkill` / `development/diagram` skill plan is **not** implemented and should be
read as superseded by this decision.

---

## 0. Reality check vs SPEC §7

The SPEC paths assume an `EditorHeader/SplitPill/` component and `components/HQ/…` roots. Neither
matches the codebase. The real shapes the design binds to:

| SPEC says | Reality | Consequence for design |
|---|---|---|
| `SplitPill` component to clone | No `SplitPill`. Pills are a **single shared, props-driven** `shared/ActionPill/ActionPill.tsx` | **Do not clone a pill.** Render a third `<ActionPill>` instance in `EditorHeader.tsx`. Zero new pill component. |
| `components/HQ/MarkdownEditor/…` | `components/MarkdownEditor/…` | All new gallery files land under `components/MarkdownEditor/DiagramGalleryPanel/`. |
| `EditorHeader/hooks/useEditorDiagramAction.ts` | hooks live at `MarkdownEditor/EditorHeader/hooks/` | Correct — new hook joins `useEditorAgentActions.ts` there. |
| (unmentioned) | The live run flow has a **`SendPreviewModal` confirm step** before spawn, and `resolveActionPrompt` defaults to **`composeClientSkill`** (fragment-composed prompt), not the bare template | Diagram must wire through the same confirm + compose path to stay a true sibling. |

This is the one substantive correction to the spec. Everything else in SPEC §1–§11 holds.

---

## 1. Layers touched

```
EditorHeader (header bar)         MarkdownEditor (panel slot)        shared / services
══════════════════════════        ═══════════════════════════        ════════════════
EditorHeader.tsx        (edit)    MarkdownEditor.tsx       (edit)     ActionPill        (reuse)
diagramPresets.ts       (add)     DiagramGalleryPanel/     (add)      PromptPeekModal   (reuse)
editorCli.ts            (edit)      DiagramGalleryPanel.tsx          SendPreviewModal  (reuse)
hooks/                              DiagramCard/                     cliEngine.ts      (reuse)
  useEditorDiagramAction (add)      DiagramRender/                   skillCompose.ts   (reuse)
                                    DiagramLightbox/                 window.pathly.fs  (reuse)
                                  diagramSidecar.ts        (add)
                                  useDiagramSidecar.ts     (add)
store/uiStore.ts         (edit)
studio/package.json      (edit — add `mermaid`)
```

### Add

| File | Why | Budget |
|---|---|---|
| `MarkdownEditor/EditorHeader/diagramPresets.ts` | `DIAGRAM_STYLES` + per-style `PromptPreset[]` (flowchart, sequence, mindmap, architecture, boxes, uml) | ≤ 150 |
| `MarkdownEditor/EditorHeader/hooks/useEditorDiagramAction.ts` | Spawn flow — clone of the split branch of `useEditorAgentActions` | ≤ 150 |
| `MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.tsx` (+ `.module.css`) | Side-panel shell + card list + `[+ New ▾]` | ≤ 120 |
| `MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.tsx` (+ `.module.css`) | One card: badge / status / date / engine + View·Regenerate·Delete | ≤ 120 |
| `MarkdownEditor/DiagramGalleryPanel/DiagramRender/DiagramRender.tsx` | Style dispatch: mermaid → `MermaidView`; ascii → `<pre>`; plantuml → source + notice | ≤ 80 |
| `MarkdownEditor/DiagramGalleryPanel/DiagramRender/MermaidView.tsx` | Lazy `mermaid` import + `render()` → SVG, themed | ≤ 120 |
| `MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx` (+ `.module.css`) | Full-res modal: zoom/pan for SVG, large mono for ASCII | ≤ 150 |
| `MarkdownEditor/DiagramGalleryPanel/diagramSidecar.ts` | Pure I/O: parse / append / delete / write `.diagrams.json` (no React) | ≤ 120 |
| `MarkdownEditor/DiagramGalleryPanel/useDiagramSidecar.ts` | Data hook: load sidecar on file change, expose `diagrams` + `reload` + `removeDiagram` | ≤ 90 |

### Edit

| File | Change |
|---|---|
| `MarkdownEditor/EditorHeader/EditorHeader.tsx` | Add a third `<ActionPill>` (Diagram) after the Analyze pill; wire `diagramCli`/`diagramPreset` state + `PromptPeekModal` + `SendPreviewModal` branch (`kind: 'diagram'`) |
| `MarkdownEditor/EditorHeader/editorCli.ts` | Add `CLI_KEY_DIAGRAM`, `PRESET_KEY_DIAGRAM` constants |
| `store/uiStore.ts` | Add `'diagram'` to the action union, `mdEditorDiagramsPath` map + panel-open flag + setters + selectors (mirror analysis) |
| `MarkdownEditor/MarkdownEditor.tsx` | Render `<DiagramGalleryPanel />` in the panel slot beside `<AnalysisPanel />` |
| `studio/package.json` | Add `mermaid` (renderer dependency) |

> **No new IPC.** Sidecar I/O reuses `window.pathly.fs.read / write / delete`
> (signatures confirmed in `types/global.d.ts:124–128`). Matches the PO constraint.

---

## 2. Component tree

```
MarkdownEditor.tsx
├─ <AnalysisPanel/>            (existing — absolute right panel, z-index 20)
├─ <DiagramGalleryPanel/>      NEW — same slot pattern, one panel open at a time
│   ├─ panel header (title + close)
│   ├─ [+ New ▾] style menu  ──► onRun(style) → hook spawn
│   ├─ body: DiagramCard[] (from useDiagramSidecar)
│   │   └─ <DiagramCard/>      style badge · status · date · engine
│   │       ├─ <DiagramRender/>          compact preview
│   │       │   ├─ <MermaidView/>        (style==='mermaid')
│   │       │   ├─ <pre>                 (style==='ascii')
│   │       │   └─ source + notice       (style==='plantuml')
│   │       └─ View · Regenerate · Delete
│   └─ <DiagramLightbox/>       NEW — opens over panel; full-res, zoom/pan
│       └─ <DiagramRender/>      reused, large mode (data-mode="full")
└─ <EditorHeader/>
    └─ <ActionPill ariaName="Diagram"…/>   3rd pill, after Analyze
        ├─ Run            → openDiagramPreview() → SendPreviewModal → handleDiagram()
        ├─ gear (⚙)       → <PromptPeekModal presets={diagramPresetsFor(style)}/>
        └─ result chip 🖼  → toggle mdEditorDiagramPanelOpen (count = diagrams.length)
```

**Panel-sharing decision:** `DiagramGalleryPanel` does **not** subclass or share code with
`AnalysisPanel` — they share only the CSS `.panel` shape (absolute, `width: 380px`, right-edge,
`z-index: 20`). Copy that block into `DiagramGalleryPanel.module.css` rather than extracting a
shared `SidePanel` wrapper. Rationale below (§8).

---

## 3. State design (mirror analysis exactly)

`uiStore.ts` already carries the analysis triple: a per-file path map, a panel-open flag, and a
per-action run slot. Diagram mirrors each.

### 3.1 Action slot (run state)

```ts
// Widen the action union from {'split'|'analyze'} to include 'diagram'.
export interface MdEditorActionRecord {
  split?:   MdEditorActionSlot
  analyze?: MdEditorActionSlot
  diagram?: MdEditorActionSlot   // NEW — same MdEditorActionSlot shape
}
// setMdEditorAction signature widens its action param to include 'diagram'.
setMdEditorAction: (filePath, action: 'split' | 'analyze' | 'diagram', patch | null) => void
```

`setMdEditorAction`'s reducer is action-agnostic (keys by string) — widening the type is the
**only** change needed; no reducer-body edits.

### 3.2 Sidecar path + panel flag (mirror `mdEditorAnalysisPaths` / `mdEditorAnalysisPanelOpen`)

```ts
mdEditorDiagramsPaths: Record<string, string>   // forFile → "<file>.diagrams.json"
mdEditorDiagramPanelOpen: boolean

setMdEditorDiagramsPath: (p: string | null, forFile?: string) => void   // copy setMdEditorAnalysisPath
setMdEditorDiagramPanelOpen: (v: boolean) => void                        // copy setMdEditorAnalysisPanelOpen
```

- Reset on file switch: extend the `setMdEditorPath` early-return block to also clear
  `mdEditorDiagramPanelOpen` (line ~200, same `path !== s.mdEditorPath` guard as analysis).
- Auto-open on completion: `setMdEditorDiagramsPath` opens the panel only when the finished run is
  for the visible file (same `key === s.mdEditorPath` guard as `setMdEditorAnalysisPath`).
- **Persistence:** do **not** add diagram keys to `partialize` (line 248) — like analysis, run/panel
  state is session-only; durability comes from the sidecar file on disk, not localStorage.

### 3.3 Selectors

```ts
export const selectMdEditorDiagram = (s) =>
  s.mdEditorActions[s.mdEditorPath ?? '']?.diagram          // run slot for the visible file
export const selectMdEditorDiagramsPath = (s) =>
  s.mdEditorDiagramsPaths[s.mdEditorPath ?? ''] ?? null     // sidecar path for the visible file
```

> The per-file keying is **load-bearing** (`useEditorAgentActions` comment lines 54–58): the header
> is a single instance that does not remount on navigation, so a run finishing while the user is on
> another file must update *that file's* slot, never the visible one. Diagram inherits this for free
> by keying everything on the captured `forFile`.

---

## 4. Sidecar I/O — `<file>.diagrams.json`

All sidecar logic lives in **`diagramSidecar.ts`** (pure, no React) so it is unit-testable and the
hook/card stay thin.

```ts
// diagramSidecar.ts — pure functions over window.pathly.fs
const sidecarPath = (file: string) => file + '.diagrams.json'

async function readSidecar(file): Promise<DiagramSidecar>     // read → JSON.parse → {version,source,diagrams:[]} (empty on miss/parse-fail)
async function appendDiagram(file, entry): Promise<void>      // READ-MODIFY-WRITE: read, push, write whole file
async function removeDiagram(file, id): Promise<void>         // read, filter out id, write
async function writeSidecar(file, sidecar): Promise<void>     // JSON.stringify(…, null, 2) → fs.write
```

### Append is read-modify-write, but performed **by the agent**, not the renderer

The generating agent owns the append (SPEC §4: *"the generating agent appends an entry"*) — the
prompt instructs it to read `.diagrams.json`, push one entry, and write the whole file. The renderer:

```
Run ─► spawn agent ─► agent reads+writes sidecar ─► PTY exits
                                                       │
  poll .diagrams.json (pollForFile)  ◄─────────────────┘
       │  parse → diagrams[]  → store path → panel auto-opens → cards render
```

So the renderer **reads** the sidecar (on file open, and after each run via the poll), and **writes**
only for **Delete** (`removeDiagram`, renderer-side read-modify-write). Regenerate = a fresh Run (the
agent appends a new entry); it does not mutate the old one.

### Sync rules

| Event | Action |
|---|---|
| File opened (`mdEditorPath` change) | `useDiagramSidecar` reads sidecar → populates cards |
| Run completes | `pollForFile('.diagrams.json')` (reuse the 5×600ms poller) → set `mdEditorDiagramsPath` → hook reloads cards |
| Delete card | renderer `removeDiagram(file, id)` → reload; if `diagrams.length === 0`, clear path + close panel |
| Regenerate card | re-spawn Run with that card's `style` (+ its stored prompt preset) — agent appends a new entry |

### Race condition: rapid regenerate / double-run

Two agents writing the **same** sidecar concurrently (last-writer-wins) loses an entry. Mitigations:

1. **Guard at the slot** — `handleDiagram` early-returns if `mdEditorActions[file].diagram.status === 'running'` (the split/analyze hooks already do this at lines 108/181). One in-flight diagram run per file. This is the primary defense and matches existing behavior.
2. Concurrency is then only possible across *different* files, which target *different* sidecars — no contention.
3. **Residual risk** (documented, not fixed in v1): a stale-tab reconciliation could let a second run start while the first's PTY is mid-write. Accepted — the run-guard makes the window sub-second and the existing actions carry the identical risk. See §7 Risks.

---

## 5. Spawn pipeline wiring (name the exact reuse points)

`useEditorDiagramAction.ts` is a near-verbatim clone of the **split branch** of
`useEditorAgentActions.ts`, swapping only the output path, the compose `kind`, and the
post-exit handling. It reuses, unchanged:

| Reused symbol | From | Role in diagram flow |
|---|---|---|
| `buildCliArgv(cli, prompt)` → `buildHeadlessArgv` | `editorCli.ts` → `cliEngine.ts` | Resolve engine argv (dash-safe, headless) |
| `resolveActionPrompt(…, kind)` pattern | `useEditorAgentActions.ts:14` | Precedence: once-prompt > stored override > `composeClientSkill` > bare builder |
| `composeClientSkill(skill, cli, transform, opts)` | `services/skillCompose.ts` | Fragment-composed default prompt (pass a new `'development/diagram'` skill id + `kind:'diagram'` transform) |
| `getSpawnCwd(file)` | `commentUtils.ts:80` | cwd for the PTY |
| `addTab / openTab / updateTabStatus / closeTab` | `terminalStore` | Visible terminal tab lifecycle |
| `window.pathly.terminal.spawn / onExit / kill` | preload IPC | Spawn PTY, await exit, stop |
| `pollForFile(path)` (5 × 600 ms) | `useEditorAgentActions.ts:45` | Poll the sidecar after exit |
| `attachProgress(tabId,…)` | `editorProgress.ts` | Milestone toasts + elapsed timer |
| `setMdEditorAction(file,'diagram',…)` | `uiStore` | Drive the pill's running/success/error state |
| `clearIfStill` + stale-run `useEffect` | `useEditorAgentActions.ts:81,95` | Self-heal a stuck pill; clone into diagram array `['split','analyze','diagram']` |

### What differs from split

```
split branch                          diagram branch
────────────                          ──────────────
outPath = file + '.split.draft'   →   outPath = file + '.diagrams.json'
on success: setSplitDraftPath +   →   on success: setMdEditorDiagramsPath(sidecar, forFile)
            switch to 'editor' view              (panel auto-opens via the setter's guard)
isErrorResult(content) on raw     →   parse JSON; treat unparseable / ERROR: as failure
   .split.draft body                     (validate it is a {diagrams:[…]} object)
compose kind: 'split'             →   compose kind: 'diagram', skill 'development/diagram'
```

### Header wiring (mirror split/analyze in `EditorHeader.tsx`)

- Add `diagramCli` / `diagramPreset` state via `loadEditorCli(CLI_KEY_DIAGRAM)` / `loadPreset(PRESET_KEY_DIAGRAM)`.
- Add `'diagram'` to the `pendingRun.kind` union; `submitPendingRun` dispatches `handleDiagram(prompt)`.
- The 3rd `<ActionPill>`:
  - `mainIcon` = an `Image`/`Network` lucide glyph, `tone="green"` (or a new tone token).
  - **result chip** `resultLabel="Gallery"`, `resultIcon=<Image/>`, `resultReady={diagramCount > 0}`,
    `onOpenResult={() => setMdEditorDiagramPanelOpen(v => !v)}` — `ActionPill` already supports the
    chip with a count via `resultLabel`. Pass `🖼 N` by composing the label string.
- The `useEditorDiagramAction` hook is invoked alongside `useEditorAgentActions` (separate hook call,
  same instance lifetime).

---

## 6. Mermaid rendering

### Lazy import (bundle isolation)

`mermaid` is large (~500 KB min+gz, pulls d3). **Never** static-import it. `MermaidView.tsx`:

```
useEffect(run once per content change):
  const mermaid = (await import('mermaid')).default     // dynamic import → own async chunk
  mermaid.initialize({ startOnLoad:false, theme:'base', themeVariables:{…tokens…}, securityLevel:'strict' })
  const { svg } = await mermaid.render(uniqueId, content)
  set svg into a ref via dangerouslySetInnerHTML wrapper
```

- **One module-level promise cache** so `import('mermaid')` + `initialize` run once per session, not per card. Subsequent `render()` calls reuse the loaded instance.
- `securityLevel: 'strict'` — agent-generated diagram source is untrusted input; strict mode strips script/HTML injection.
- Unique render id per call (`dg_<id>_<n>`) — `mermaid.render` requires a unique DOM id or it collides across cards.

### SSR / mount safety

- Studio is a pure client renderer (Electron + Vite, no SSR) — no `window`-undefined hazard. But the
  dynamic import means the SVG is **async**: render a `loading` then a `render-error` state
  (catch `mermaid.render` throws → show the raw source in `<pre>` with an error note, never crash the card).
- Guard against unmount-after-await: capture an `active` flag in the effect and bail if the component
  unmounted before the import resolved.

### Theming from `tokens.css`

Mermaid takes theme via JS `themeVariables`, not CSS — but the **values** must come from `tokens.css`,
not hard-coded hexes. Read them at init time:

```
const cs = getComputedStyle(document.documentElement)
themeVariables: {
  background:    cs.getPropertyValue('--bg-base'),
  primaryColor:  cs.getPropertyValue('--bg-surface0'),
  primaryTextColor: cs.getPropertyValue('--text-primary'),
  lineColor:     cs.getPropertyValue('--text-muted'),
  // …map the handful mermaid honors
}
```

This is the **one sanctioned exception** to "no values outside CSS" — mermaid's API simply does not
accept a stylesheet. Re-read tokens on theme switch (the SVG must re-render when `useUiStore.theme`
changes — subscribe to it as a `MermaidView` dependency so a light/dark flip re-renders all cards).

---

## 7. Dependency direction

All new files import **downward / sideways** only — no upward imports, no layer violations.

```
DiagramGalleryPanel.tsx
  → useDiagramSidecar.ts → diagramSidecar.ts → window.pathly.fs   (leaf)
  → DiagramCard → DiagramRender → MermaidView → import('mermaid')  (leaf dep)
  → DiagramLightbox → DiagramRender (shared)
  → uiStore (sibling store)

useEditorDiagramAction.ts
  → editorCli.ts → cliEngine.ts        (existing service)
  → commentUtils.ts (getSpawnCwd)      (existing util)
  → skillCompose.ts                    (existing service)
  → terminalStore / uiStore / toastStore (sibling stores)
  → editorProgress.ts                  (sibling util)

EditorHeader.tsx → ActionPill / PromptPeekModal / SendPreviewModal (all existing shared)
```

No store imports a component; no component reaches into `main/`. `diagramSidecar.ts` is the lowest
leaf (only touches the `window.pathly.fs` bridge). Clean.

### Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Mermaid bundle size** inflates the renderer | Med | Dynamic `import('mermaid')` → separate async chunk, loaded only when a mermaid card first renders. Verify with `electron-vite build` chunk report. |
| **Theming fragility** — mermaid ignores CSS; hard-coded colors drift from tokens | Med | Read `tokens.css` vars via `getComputedStyle` at init; re-init on theme change. No hex literals in JS. |
| **Sidecar race** on rapid regenerate / double-run | Low | Per-file run-guard (one in-flight diagram per file) already blocks concurrent same-file writes. Cross-file runs target different sidecars. Residual sub-second window documented & accepted. |
| **Untrusted diagram source** (agent output → mermaid → SVG) | Med | `securityLevel: 'strict'`; never `dangerouslySetInnerHTML` raw agent text — only the sanitized SVG mermaid returns. ASCII goes in `<pre>` (text node, no HTML). |
| **Malformed JSON sidecar** (agent writes invalid JSON) | Low | `readSidecar` returns empty `{diagrams:[]}` on parse failure; poll treats unparseable result as run-failure → error toast, no crash. |
| **150-line budgets** on Card/Lightbox creeping up | Low | Pre-split per SPEC §7; Render dispatch + MermaidView already isolated. Hold the line. |
| **`mermaid.render` id collision** across cards | Low | Unique id per render call (`dg_<id>_<n>`). |

---

## 8. Key decisions & trade-offs

### D1 — Reuse `ActionPill`, do not clone a `DiagramPill`
The SPEC's "clone of SplitPill" is moot: there is no SplitPill, only a generic props-driven
`ActionPill` already shared by Split, Analyze, and the board's Evaluate. **Decision:** add a third
`<ActionPill>` instance. *Trade-off:* the SPEC's file `DiagramPill/DiagramPill.tsx` is **not created**
— this is a deliberate deviation that removes ~120 lines of duplicate UI and keeps one pill to
maintain. The "DiagramPill" is configuration, not a component.

### D2 — Copy the `.panel` CSS block, do not extract a shared `SidePanel`
`AnalysisPanel` and `DiagramGalleryPanel` share an absolute-positioned right panel shape.
**Decision:** duplicate the ~13-line `.panel` CSS block rather than extract a wrapper.
*Trade-off:* a tiny, well-understood CSS duplication vs. a premature abstraction that would couple two
panels with different bodies (markdown report vs. card gallery + lightbox). Per CLAUDE.md's
"extract on the *next* logical sub-section" rule, two consumers of a 13-line block is below the
extraction threshold. If a 3rd side panel appears, revisit.

### D3 — Lightbox renders via the **same** `DiagramRender`, in a `data-mode="full"` variant
**Decision:** `DiagramRender` takes a `mode: 'card' | 'full'` prop; the lightbox passes `'full'`,
which removes the size clamp and enables the zoom/pan wrapper. *Trade-off:* one component renders both
sizes (DRY, mermaid SVG generated once-per-content) vs. two renderers. The zoom/pan transform lives in
`DiagramLightbox` (a `transform: scale()/translate()` on a wrapper driven by a CSS custom property), so
`DiagramRender` stays presentation-only and within budget.

### D4 — Agent owns the sidecar append; renderer only reads + deletes
**Decision:** keep SPEC §4's contract — the agent does the read-modify-write append. The renderer never
races the agent on append. *Trade-off:* the renderer can't show a card until the run completes and the
poll succeeds (no optimistic card), but it guarantees the on-disk sidecar is the single source of truth
and survives reload for free. Matches how Analyze treats `.analysis`.

### D5 — Zoom/pan = CSS transform, not a canvas/library
**Decision:** SVG zoom/pan via wheel→scale + drag→translate, applied as a `transform` on the SVG
wrapper through a CSS custom property (the sanctioned inline-style exception for dynamic values).
*Trade-off:* no `svg-pan-zoom` dependency (another bundle); ~30 lines of pointer math in the lightbox.
Good enough for "read a complex diagram"; not a full diagramming surface.

### D6 — `plantuml` is source-only, gated in the picker
**Decision:** the style menu groups "Renders anywhere" (mermaid, ascii) vs "Needs render engine"
(plantuml); plantuml cards show source in `<pre>` + the "render engine not bundled yet" notice.
*Trade-off:* honest seam for the deferred render engine; zero new deps now.

---

## 9. Implementation sequence (ordered commits)

Each step is independently typecheck-clean (`npm run typecheck`) and leaves the editor working.

| # | Commit | Files | Gate |
|---|---|---|---|
| 1 | **State scaffold** — widen action union to `'diagram'`; add `mdEditorDiagramsPaths`, `mdEditorDiagramPanelOpen`, setters, selectors; clear-on-file-switch | `store/uiStore.ts` | typecheck clean; existing pills unaffected |
| 2 | **CLI/preset keys + presets** — `CLI_KEY_DIAGRAM`, `PRESET_KEY_DIAGRAM`; `diagramPresets.ts` (`DIAGRAM_STYLES` + 6 presets with `{{FILE}}`/`{{SIDECAR}}`) | `editorCli.ts`, `diagramPresets.ts` | typecheck clean |
| 3 | **Sidecar I/O** — `diagramSidecar.ts` (read/append/remove/write) + types (`Diagram`, `DiagramSidecar`) | `diagramSidecar.ts` | unit-testable; no UI yet |
| 4 | **Spawn hook** — `useEditorDiagramAction.ts` cloned from split branch; output = `.diagrams.json`; compose `kind:'diagram'`; reuse `pollForFile` | `hooks/useEditorDiagramAction.ts` | spawns a tab, writes sidecar, sets run slot |
| 5 | **Header pill** — 3rd `<ActionPill>` + `PromptPeekModal` + `SendPreviewModal` diagram branch; wire `diagramCli`/`diagramPreset` | `EditorHeader.tsx` | Run generates a diagram; result chip shows count |
| 6 | **Gallery panel + card** — `DiagramGalleryPanel`, `useDiagramSidecar`, `DiagramCard`; View/Regenerate/Delete; mount in `MarkdownEditor.tsx` | gallery files, `MarkdownEditor.tsx` | cards render from sidecar; delete/regenerate work |
| 7 | **Render dispatch** — `DiagramRender` (ascii `<pre>`, plantuml source+notice) | `DiagramRender.tsx` | ascii + plantuml render |
| 8 | **Mermaid** — add `mermaid` to `studio/package.json`; `MermaidView` lazy import + token theming + strict mode | `package.json`, `MermaidView.tsx` | mermaid renders as SVG; dynamic chunk verified |
| 9 | **Lightbox** — `DiagramLightbox` full-res + zoom/pan; card click + View open it | `DiagramLightbox.tsx` | full-res view with zoom/pan; Esc/backdrop close |
| 10 | **Polish** — responsive ≤200px, `data-style`/`data-status` variants, all `type="button"`, theme re-render on flip; final `npm run typecheck` + `tsc -p studio/tsconfig.node.json` | all | both typechecks clean; manual §10 pass |

> Steps 1–5 deliver a working "generate + persist + count" loop; 6–9 deliver the visible gallery and
> full-res view; 10 is compliance. A reviewer can stop after step 5 for an end-to-end smoke test.

---

## 10. Verification (from SPEC §10)

- `npm run typecheck` (renderer) **and** `tsc --noEmit -p studio/tsconfig.node.json` (only if a
  main-process change sneaks in — none expected) both clean.
- Manual: open MD → generate Mermaid (SVG) → generate ASCII (`<pre>`) → generate a 3rd → 3 cards →
  click a card → lightbox with zoom/pan → delete one → reload file → remaining diagrams persist from
  the sidecar.

---

## 11. Open questions for product

**None.** The single substantive deviation (no `DiagramPill` component — render a third `ActionPill`
instead) is a strict simplification that preserves the SPEC's UX and reuse intent, so it needs no
product adjudication. Proceeding on the assumptions stated above.
