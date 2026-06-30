# md-diagram-conversion — ASCII Diagrams & Full User Story

> Designer artifact · Generated 2026-06-29

---

## 1. Full User Story (13 stories)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AS A  Studio user with an open Markdown file                               │
│  I WANT a Diagram action in the editor header (alongside Split & Analyze)   │
│  SO THAT I can generate visual explanations of my content with one click    │
└─────────────────────────────────────────────────────────────────────────────┘

S-01  Diagram button in header
      Given:  a Markdown file is open
      When:   I look at the editor header
      Then:   I see three pills: Split | Analyze | Diagram (Network icon, green)

S-02  AI generates diagram source
      Given:  I click Run on the Diagram pill
      When:   the agent runs (terminal tab opens)
      Then:   a <file>.diagrams.json sidecar is written with ≥1 diagram entry

S-03  Sidecar persists across reload
      Given:  I have generated diagrams for architecture.md
      When:   I close and reopen architecture.md
      Then:   the gallery panel reopens with the same cards (no re-generation)

S-04  Gallery panel with cards
      Given:  a diagram run completes successfully
      When:   the result chip shows "🖼 1"
      Then:   the DiagramGalleryPanel slides in from the right with DiagramCards

S-05  Mermaid renders as SVG
      Given:  a diagram card has style="mermaid"
      When:   the card renders
      Then:   a live SVG flowchart appears (themed from Studio tokens.css)

S-06  ASCII renders in pre
      Given:  a diagram card has style="ascii"
      When:   the card renders
      Then:   the boxes/text appear in a monospace <pre> block

S-07  PlantUML shows source + notice
      Given:  a diagram card has style="plantuml"
      When:   the card renders
      Then:   raw PlantUML source appears + notice "render engine not bundled yet"

S-08  Lightbox with zoom/pan
      Given:  I click View on a diagram card
      When:   the DiagramLightbox opens
      Then:   I can scroll-wheel to zoom (0.5×–4×) and drag to pan; Esc closes

S-09  Delete a diagram card
      Given:  a gallery has ≥1 card
      When:   I click Delete on a card
      Then:   the sidecar entry is removed; if last card, panel closes

S-10  Regenerate a diagram card
      Given:  I click Regenerate on a card
      When:   a new terminal tab opens and completes
      Then:   a new card appears alongside the original (append, not overwrite)

S-11  Panel auto-opens on run complete
      Given:  I trigger a diagram run while architecture.md is open
      When:   the run completes (PTY exits + poll succeeds)
      Then:   the gallery panel opens automatically (no manual click needed)

S-12  TypeScript clean
      Given:  all feature code is written
      When:   npm run typecheck && tsc --noEmit -p studio/tsconfig.node.json
      Then:   both commands exit 0 with no errors

S-13  Theme re-render
      Given:  Mermaid cards are visible
      When:   I flip Studio from dark to light mode
      Then:   all Mermaid SVGs re-render with the updated token colors
```

---

## 2. Studio Editor Header — Pill Layout

### 2a. Before the feature

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MARKDOWN EDITOR HEADER                                                 │
│                                                                         │
│  architecture.md                                         [Split] [Anl]  │
│  ──────────────────────────────────────────────────────────────────── │
│                         (editor body)                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2b. After the feature — Idle state (3 pills)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MARKDOWN EDITOR HEADER                                                 │
│                                                                         │
│  architecture.md                      [Split] [Analyze] [⬡ Diagram]    │
│                                                           ▲             │
│                                              new pill (Network icon)    │
│  ─────────────────────────────────────────────────────────────────── │
│                         (editor body)                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2c. Diagram pill — three segments (ActionPill component)

```
  ┌──────────────────────────────────────────────┐
  │   Diagram pill                               │
  │                                              │
  │  ┌─────────────┐  ┌─────┐  ┌─────────────┐  │
  │  │  ▶  Run      │  │  ⚙  │  │  🖼  Gallery │  │
  │  └─────────────┘  └─────┘  └─────────────┘  │
  │       ▲                          ▲           │
  │  triggers generate          opens gallery    │
  │  → SendPreviewModal         shows diagram    │
  │                             count (N)        │
  └──────────────────────────────────────────────┘

  State transitions:
  ┌─────────┐  click Run  ┌─────────────┐  success  ┌──────────┐
  │  idle   │ ──────────► │   running   │ ─────────► │   done   │
  │(Network)│             │(spinner 🔄) │            │(🖼 N, ✓) │
  └─────────┘             │"Diagramming"│            └──────────┘
       ▲                  └──────┬──────┘                 │
       │                        │ error                   │ click Run again
       │                  ┌─────▼──────┐                  │
       │                  │   error    │                  │
       └──────────────────│(red border)│ ◄────────────────┘
                          └────────────┘
```

---

## 3. Full Screen Layout — Gallery Panel Open

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Studio — Markdown Editor (full view when gallery is open)                     │
│                                                                                 │
│  ┌─────────────────────────────────────────────────┐ ┌───────────────────────┐ │
│  │ EDITOR HEADER                                   │ │  DIAGRAM GALLERY      │ │
│  │ architecture.md   [Split] [Analyze] [⬡ 🖼 2]   │ │  ─────────────────── │ │
│  ├─────────────────────────────────────────────────┤ │  [+ New ▾]      [✕]  │ │
│  │                                                 │ │                       │ │
│  │  # Architecture                                 │ │  ┌───────────────┐    │ │
│  │                                                 │ │  │  DiagramCard  │    │ │
│  │  ## Overview                                    │ │  │  ●mermaid  ok │    │ │
│  │  The system consists of three layers:           │ │  │  Jun 29 · claude│   │ │
│  │  - API gateway                                  │ │  │               │    │ │
│  │  - Processing pipeline                          │ │  │  ┌──[A]──►[B]┐│    │ │
│  │  - Storage layer                                │ │  │  │    SVG    ││    │ │
│  │                                                 │ │  │  └───────────┘│    │ │
│  │  ## Components                                  │ │  │               │    │ │
│  │  ...                                            │ │  │  [View] [↺] [🗑]│   │ │
│  │                                                 │ │  └───────────────┘    │ │
│  │                                                 │ │                       │ │
│  │                                                 │ │  ┌───────────────┐    │ │
│  │                                                 │ │  │  DiagramCard  │    │ │
│  │                                                 │ │  │  ●ascii    ok │    │ │
│  │                                                 │ │  │  Jun 29 · claude│   │ │
│  │                                                 │ │  │               │    │ │
│  │                                                 │ │  │ +------+      │    │ │
│  │                                                 │ │  │ | API  |──►DB │    │ │
│  │                                                 │ │  │ +------+      │    │ │
│  │                                                 │ │  │               │    │ │
│  │                                                 │ │  │  [View] [↺] [🗑]│   │ │
│  │                                                 │ │  └───────────────┘    │ │
│  │                                                 │ │                       │ │
│  └─────────────────────────────────────────────────┘ └───────────────────────┘ │
│                                                        ▲ width: 380px          │
│                                                        absolute right panel    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Prompt Config Modal — PromptPeekModal (6 presets)

```
┌──────────────────────────────────────────────────────────────────────┐
│  PROMPTPEEKMODAL — Diagram Options                         [✕ close] │
│  ────────────────────────────────────────────────────────────────── │
│                                                                      │
│  Style preset                                                        │
│                                                                      │
│  Renders anywhere ─────────────────────────────────────────────     │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐    │
│  │ ● Flowchart │ │  Sequence    │ │ Mindmap  │ │ Architecture │    │
│  │  (Mermaid)  │ │  (Mermaid)   │ │(Mermaid) │ │  (Mermaid)   │    │
│  └─────────────┘ └──────────────┘ └──────────┘ └──────────────┘    │
│  ┌─────────┐                                                         │
│  │  Boxes  │                                                         │
│  │ (ASCII) │                                                         │
│  └─────────┘                                                         │
│                                                                      │
│  Needs render engine ──────────────────────────────────────────     │
│  ┌──────────┐                                                        │
│  │  UML     │  ⚠ PlantUML render engine not bundled                │
│  │(PlantUML)│                                                        │
│  └──────────┘                                                        │
│                                                                      │
│  Engine   [claude ▾]      Prompt  [edit prompt text…]               │
│                                                                      │
│  ──────────────────────────────────────────────────────────────     │
│                                                  [Cancel] [Confirm]  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. SendPreviewModal — Confirm before spawn

```
┌──────────────────────────────────────────────────────────────┐
│  ⬡  Generate Diagram                              [✕ close]  │
│  ──────────────────────────────────────────────────────────  │
│                                                              │
│  Style:   Flowchart (Mermaid)                               │
│  Engine:  claude                                             │
│  File:    architecture.md                                    │
│                                                              │
│  Preview prompt:                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Read the file at {{FILE}} and the sidecar at         │   │
│  │ {{SIDECAR}}. Generate a Mermaid flowchart diagram    │   │
│  │ that explains the architecture. Append one JSON      │   │
│  │ entry to the sidecar file.                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│                                        [Cancel]  [▶ Run]    │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Diagram Card — Anatomy

```
┌──────────────────────────────────────────────────┐
│  DiagramCard                                     │
│  ┌────────────┬──────────────┬──────────────┐    │
│  │ ● mermaid  │  status: ok  │  Jun 29 2026 │    │
│  │  (badge)   │              │  claude       │    │
│  └────────────┴──────────────┴──────────────┘    │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  DiagramRender (mode="card", max-h: 160px) │  │
│  │                                            │  │
│  │  [mermaid] ──► SVG preview (scaled)        │  │
│  │  [ascii]   ──► <pre> mono text             │  │
│  │  [plantuml]──► <pre> source + notice       │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐  │
│  │  View    │  │ ↺ Regen.  │  │  🗑 Delete   │  │
│  └──────────┘  └────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────┘
```

---

## 7. Lightbox — Full Resolution View

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LIGHTBOX OVERLAY (z-index: --z-modal, full viewport)                  │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
│  ░░░░░  ┌────────────────────────────────────────────────────┐  ░░░    │
│  ░░░░░  │  Flowchart — architecture.md          [✕ Esc]      │  ░░░    │
│  ░░░░░  ├────────────────────────────────────────────────────┤  ░░░    │
│  ░░░░░  │                                                    │  ░░░    │
│  ░░░░░  │   DiagramRender (mode="full")                      │  ░░░    │
│  ░░░░░  │                                                    │  ░░░    │
│  ░░░░░  │    ┌─────────┐     ┌────────────┐     ┌──────┐    │  ░░░    │
│  ░░░░░  │    │  API GW │────►│  Pipeline  │────►│  DB  │    │  ░░░    │
│  ░░░░░  │    └─────────┘     └────────────┘     └──────┘    │  ░░░    │
│  ░░░░░  │         │                │                         │  ░░░    │
│  ░░░░░  │         ▼                ▼                         │  ░░░    │
│  ░░░░░  │    ┌─────────┐     ┌────────────┐                 │  ░░░    │
│  ░░░░░  │    │  Auth   │     │  Cache     │                 │  ░░░    │
│  ░░░░░  │    └─────────┘     └────────────┘                 │  ░░░    │
│  ░░░░░  │                                                    │  ░░░    │
│  ░░░░░  │   scroll-wheel: zoom 0.5×–4×                       │  ░░░    │
│  ░░░░░  │   drag: pan across SVG                             │  ░░░    │
│  ░░░░░  └────────────────────────────────────────────────────┘  ░░░    │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
│  ░ click backdrop or press Esc to close ░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
└─────────────────────────────────────────────────────────────────────────┘

  Zoom/pan implementation (CSS transform, no library):
  ┌──────────────────────────────────────────────────────┐
  │  wheel event → scale += delta * 0.1                 │
  │  scale = clamp(scale, 0.5, 4.0)                     │
  │  pointerdown + pointermove → translate(dx, dy)      │
  │  transform: scale(var(--zoom)) translate(var(--tx))  │
  └──────────────────────────────────────────────────────┘
```

---

## 8. Component Architecture Tree

```
MarkdownEditor.tsx
│
├─ <EditorHeader/>
│   ├─ <ActionPill name="Split"   …/>          (existing)
│   ├─ <ActionPill name="Analyze" …/>          (existing)
│   └─ <ActionPill name="Diagram" …/>          ◄─ NEW (3rd instance, same component)
│       ├─ Run segment     → handleDiagramRun()
│       ├─ ⚙ gear segment  → <PromptPeekModal presets={DIAGRAM_STYLES}/>
│       └─ 🖼 chip         → setMdEditorDiagramPanelOpen(true)
│
├─ <AnalysisPanel/>                            (existing, right panel)
│
└─ <DiagramGalleryPanel/>                      ◄─ NEW (right panel, same slot)
    │  powered by useDiagramSidecar(mdEditorPath)
    │
    ├─ panel header: "Diagrams"  [+ New ▾]  [✕]
    │
    ├─ <DiagramCard id="dg_1"/>
    │   ├─ badge: mermaid | ascii | plantuml
    │   ├─ <DiagramRender mode="card"/>
    │   │   ├─ <MermaidView/>           (style=mermaid → lazy import → SVG)
    │   │   ├─ <pre>                    (style=ascii → text node)
    │   │   └─ source + notice          (style=plantuml)
    │   └─ [View] [↺ Regen] [🗑 Delete]
    │
    ├─ <DiagramCard id="dg_2"/>
    │   └─ …
    │
    └─ <DiagramLightbox/>                (opens over panel on View click)
        └─ <DiagramRender mode="full"/>
            └─ zoom/pan wrapper (CSS transform)
```

---

## 9. New File Structure

```
studio/src/renderer/src/
│
├─ components/
│   └─ MarkdownEditor/
│       ├─ EditorHeader/
│       │   ├─ diagramPresets.ts               NEW  ── 6 presets, 2 groups
│       │   ├─ editorCli.ts                    EDIT ── +CLI_KEY_DIAGRAM, PRESET_KEY_DIAGRAM
│       │   ├─ EditorHeader.tsx                EDIT ── +3rd <ActionPill>
│       │   └─ hooks/
│       │       └─ useEditorDiagramAction.ts   NEW  ── spawn hook (clone of split branch)
│       │
│       ├─ DiagramGalleryPanel/
│       │   ├─ DiagramGalleryPanel.tsx         NEW  ── panel shell + card list
│       │   ├─ DiagramGalleryPanel.module.css  NEW  ── .panel shape (copy from AnalysisPanel)
│       │   ├─ diagramSidecar.ts               NEW  ── pure I/O: read/append/remove/write
│       │   ├─ useDiagramSidecar.ts            NEW  ── data hook: load on file change
│       │   │
│       │   ├─ DiagramCard/
│       │   │   ├─ DiagramCard.tsx             NEW  ── one card: badge/date/engine/actions
│       │   │   └─ DiagramCard.module.css      NEW
│       │   │
│       │   ├─ DiagramRender/
│       │   │   ├─ DiagramRender.tsx           NEW  ── style dispatch (mermaid/ascii/plantuml)
│       │   │   └─ MermaidView.tsx             NEW  ── lazy mermaid + SVG + theme tokens
│       │   │
│       │   └─ DiagramLightbox/
│       │       ├─ DiagramLightbox.tsx         NEW  ── full-res overlay + zoom/pan
│       │       └─ DiagramLightbox.module.css  NEW
│       │
│       └─ MarkdownEditor.tsx                  EDIT ── mount <DiagramGalleryPanel>
│
├─ store/
│   └─ uiStore.ts                              EDIT ── +diagram action slot, +paths map, +panel flag
│
└─ studio/package.json                         EDIT ── +mermaid (renderer dep)
```

---

## 10. Data Flow — End-to-End

```
  USER                  UI LAYER              STORE              DISK / AGENT
   │                       │                    │                     │
   │  click Run            │                    │                     │
   │──────────────────────►│                    │                     │
   │                       │ openDiagramPreview()                     │
   │                       │──── PromptPeekModal ───►                 │
   │  select "Flowchart"   │                    │                     │
   │──────────────────────►│                    │                     │
   │                       │──── SendPreviewModal ──►                 │
   │  confirm              │                    │                     │
   │──────────────────────►│                    │                     │
   │                       │ handleDiagram(prompt)                    │
   │                       │ setMdEditorAction('diagram', running)    │
   │                       │────────────────────►│                    │
   │                       │ spawn PTY (terminal tab opens)           │
   │                       │──────────────────────────────────────────►
   │                       │                    │                     │
   │  pill shows spinner   │                    │      agent runs:    │
   │◄──────────────────────│                    │      read MD file   │
   │                       │                    │      generate source│
   │                       │                    │      write sidecar  │
   │                       │                    │         ◄───────────│
   │                       │ PTY exits                               │
   │                       │◄─────────────────────────────────────────│
   │                       │ pollForFile(.diagrams.json) 5×600ms     │
   │                       │──────────────────────────────────────────►
   │                       │      sidecar found on disk  ◄────────────│
   │                       │ parse JSON → validate                    │
   │                       │ setMdEditorDiagramsPath(sidecar, file)   │
   │                       │────────────────────►│                    │
   │                       │   store sets mdEditorDiagramPanelOpen=true
   │                       │◄────────────────────│                    │
   │                       │ setMdEditorAction('diagram', done)       │
   │                       │────────────────────►│                    │
   │  pill: 🖼 1 chip       │                    │                    │
   │◄──────────────────────│                    │                    │
   │  gallery auto-opens   │                    │                    │
   │◄──────────────────────│                    │                    │
   │                       │ useDiagramSidecar reads .diagrams.json  │
   │                       │──────────────────────────────────────────►
   │                       │      diagrams[]   ◄──────────────────────│
   │                       │ render DiagramCard[]                     │
   │  cards appear         │                    │                    │
   │◄──────────────────────│                    │                    │
```

---

## 11. Sidecar File Format

```
architecture.md.diagrams.json
─────────────────────────────
{
  "version": 1,
  "source": "architecture.md",
  "diagrams": [
    {
      "id":        "dg_k2j9m",
      "title":     "Pipeline flow",
      "style":     "mermaid",           ← mermaid | ascii | plantuml
      "content":   "flowchart LR\n  A[API GW] --> B[Pipeline]\n  B --> C[(DB)]",
      "status":    "kept",              ← draft | kept
      "engine":    "claude",
      "model":     null,                ← seam for future per-model picker
      "createdAt": "2026-06-29T14:30:00Z"
    },
    {
      "id":        "dg_x7p1q",
      "title":     "Storage boxes",
      "style":     "ascii",
      "content":   "+-------+    +-------+\n| Cache |───►| Disk  |\n+-------+    +-------+",
      "status":    "kept",
      "engine":    "claude",
      "model":     null,
      "createdAt": "2026-06-29T14:35:00Z"
    }
  ]
}

Renderer operations:
  READ:   useDiagramSidecar on mount / after poll
  WRITE:  agent (append on generate); renderer (delete only → removeDiagram)
  NEVER:  renderer appends (agent owns that path to prevent races)
```

---

## 12. State Machine — Diagram Pill

```
                    ┌─────────────────────────────────────────────┐
                    │         mdEditorActions[file].diagram        │
                    └─────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │    ┌──────┐                                                      │
  │    │      │  null / undefined                                    │
  │    │ NONE │◄──────────────────────────── file switch             │
  │    │      │                                                      │
  │    └──┬───┘                                                      │
  │       │ handleDiagram(prompt) called                             │
  │       ▼                                                          │
  │    ┌─────────┐                                                   │
  │    │         │  {status:'running', startedAt, tabId, forFile}   │
  │    │ RUNNING │                                                   │
  │    │         │  → pill shows spinner, "Diagramming…"            │
  │    │         │  → stop button replaces gear                     │
  │    └──┬──┬───┘                                                   │
  │       │  │                                                        │
  │  PTY  │  │ PTY exit + poll success → parse JSON OK              │
  │ stop  │  └──────────────────────────────────┐                   │
  │       │                                     ▼                   │
  │       │                              ┌─────────────┐            │
  │       │                              │    DONE      │            │
  │       │                              │{status:'done'}│           │
  │       │                              │ → chip 🖼 N  │            │
  │       │                              │ → panel opens│            │
  │       │                              └──────┬───────┘            │
  │       │                                     │ click Run again    │
  │       │  poll fail / parse fail             │                   │
  │       ▼                                     │                   │
  │    ┌─────────┐                              │                   │
  │    │  ERROR  │◄─────────────────────────────┘ (if error)        │
  │    │{status: │  → red pill border                               │
  │    │ 'error'}│  → error toast with retry                        │
  │    └──┬──────┘                                                   │
  │       │ clearIfStill (stale-run reconciler)                     │
  │       └───────────────────────────────────────────────────────► │
  │                                                        NONE     │
  └──────────────────────────────────────────────────────────────────┘
```

---

## 13. Mermaid Render Pipeline (MermaidView.tsx)

```
  DiagramCard mounts with content="flowchart LR\n  A-->B"
         │
         ▼
  useEffect (deps: [content, theme])
         │
         ├─ already loaded? ──► skip dynamic import
         │
         │ first call:
         ├─ const m = await import('mermaid')     ← lazy chunk, ~500KB
         │         (cached in module-level promise after first call)
         │
         ├─ cs = getComputedStyle(document.documentElement)
         │
         ├─ m.initialize({
         │     startOnLoad: false,
         │     theme: 'base',
         │     securityLevel: 'strict',           ← agent source = untrusted
         │     themeVariables: {
         │       background:       cs('--bg-base'),
         │       primaryColor:     cs('--bg-surface0'),
         │       primaryTextColor: cs('--text-primary'),
         │       lineColor:        cs('--text-muted'),
         │     }
         │   })
         │
         ├─ const { svg } = await m.render('dg_<id>_<n>', content)
         │                                  ▲
         │                         unique per render call (no collision)
         │
         ├─ if (!active) return            ← unmount guard
         │
         ├─ setSvg(sanitized svg)          ← dangerouslySetInnerHTML (mermaid output only)
         │
         └─ catch(err) → show <pre> fallback with error note (never crash card)

  On theme flip:
         theme dep changes → effect re-runs → re-initialize with new token values
         → re-render → SVG updates to light/dark colors
```

---

## 14. Delivery Milestones (Conversation Sequence)

```
  Conv 0   PREFLIGHT           Read-only scan. 10 touchpoints noted. Both typechecks pass.
  ──────   ──────────────────────────────────────────────────────────────────────────────
  Conv 1   STATE SCAFFOLD      uiStore.ts: +diagram slot, +paths map, +panel flag.
           Observable: setMdEditorAction(path,'diagram',null) compiles.

  Conv 2   SIDECAR + HOOK      diagramSidecar.ts (read/append/remove/write).
           + diagramPresets.ts (6 presets). + useEditorDiagramAction.ts.
           Observable: devtools call → .diagrams.json appears on disk.

  Conv 3   PILL IN HEADER      EditorHeader.tsx: 3rd <ActionPill>. Run works end-to-end.
           Observable: pill visible; spinner on run; 🖼 1 chip after completion.

  Conv 4   GALLERY + CARDS     DiagramGalleryPanel, DiagramCard, useDiagramSidecar.
           Observable: panel auto-opens; cards from sidecar; delete/regen work.

  Conv 5   RENDER + LIGHTBOX   DiagramRender, MermaidView (+ mermaid dep), DiagramLightbox.
           Observable: SVG in card; lightbox with zoom/pan; Esc closes.

  Conv 6   POLISH + VERIFY     Compliance sweep. Both typechecks clean. 9-step smoke test.
           Observable: npm run typecheck exits 0; theme flip re-renders SVGs.
```

---

_End of ASCII Diagrams artifact._
