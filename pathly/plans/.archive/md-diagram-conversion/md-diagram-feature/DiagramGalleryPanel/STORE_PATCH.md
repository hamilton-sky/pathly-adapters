# Store patch — `src/store/uiStore.ts`

The Diagram feature stores its run state and panel/path the same way AI-Split and
AI-Analyze already do. Apply these additions (Conv 1 · STATE SCAFFOLD). Nothing
here removes or changes existing behaviour — it's purely additive.

### 1. Action record + action union

```ts
export interface MdEditorActionRecord {
  split?: MdEditorActionSlot
  analyze?: MdEditorActionSlot
  diagram?: MdEditorActionSlot          // NEW
}
```

```ts
// widen the action parameter everywhere setMdEditorAction is typed:
setMdEditorAction: (
  filePath: string,
  action: 'split' | 'analyze' | 'diagram',   // + 'diagram'
  patch: Partial<MdEditorActionSlot> | null,
) => void
```

`setMdEditorAction`'s implementation is generic over the action key, so no body change
is needed — only the type widens.

### 2. State fields (next to the analysis fields)

```ts
// in interface UiState:
/** Sidecar paths per notebook file — keyed by mdEditorPath */
mdEditorDiagramPaths: Record<string, string>
mdEditorDiagramPanelOpen: boolean
setMdEditorDiagramPanelOpen: (v: boolean) => void
setMdEditorDiagramPath: (p: string | null, forFile?: string) => void
```

```ts
// in the create() initial state:
mdEditorDiagramPaths: {},
mdEditorDiagramPanelOpen: false,
```

### 3. Actions (clone of setMdEditorAnalysisPath / …PanelOpen)

```ts
setMdEditorDiagramPath: (p, forFile) => set((s) => {
  const key = forFile ?? s.mdEditorPath ?? ''
  if (!key) return {}
  if (p === null) {
    const next = { ...s.mdEditorDiagramPaths }
    delete next[key]
    return { mdEditorDiagramPaths: next }
  }
  return {
    mdEditorDiagramPaths: { ...s.mdEditorDiagramPaths, [key]: p },
    // auto-open the gallery when the run was for the visible file
    ...(key === s.mdEditorPath ? { mdEditorDiagramPanelOpen: true } : {}),
  }
}),

setMdEditorDiagramPanelOpen: (v) => set({ mdEditorDiagramPanelOpen: v }),
```

### 4. Close the panel on file switch

In the existing `setMdEditorPath`, add the diagram panel beside the analysis one:

```ts
setMdEditorPath: (path) => set((s) => ({
  mdEditorPath: path,
  ...(path !== s.mdEditorPath ? { mdEditorAnalysisPanelOpen: false } : {}),
  ...(path !== s.mdEditorPath ? { mdEditorDiagramPanelOpen: false } : {}),   // NEW
})),
```

### 5. Selectors (next to selectMdEditorAnalysisPath)

```ts
export const selectMdEditorDiagramPath = (s: UiState): string | null =>
  s.mdEditorDiagramPaths[s.mdEditorPath ?? ''] ?? null

export const selectMdEditorDiagram = (s: UiState): MdEditorActionSlot | undefined =>
  s.mdEditorActions[s.mdEditorPath ?? '']?.diagram
```

### 6. Persistence (if uiStore `partialize`s its persisted keys)

Add `mdEditorDiagramPaths` to the persisted key list so generated diagrams survive a
reload (story S-03), exactly as `mdEditorAnalysisPaths` is persisted.
