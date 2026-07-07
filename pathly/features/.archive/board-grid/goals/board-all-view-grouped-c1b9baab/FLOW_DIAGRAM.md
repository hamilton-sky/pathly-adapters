# board-grid — Flow Diagram

## Data flow (runtime)

```
CommsPanel
  │ messages: Message[]  (from useCommsPanel — already fetched)
  │ boardView === 'grid'
  ▼
GridView(messages, boardKey, boardScope)
  │
  ├─ ResizeObserver → narrow? (width ≤ 220)
  │     yes → <PlaceholderBanner>
  │     no  ↓
  │
  ├─ gridBands(messages)
  │     ┌────────┬────────┬────────┬──────────┐
  │     │ goals[]│ tasks[]│ msgs[] │ artifacts│
  │     └────────┴────────┴────────┴──────────┘
  │
  ├─ BAND_ORDER.map → (skip empty bands)
  │     <section>
  │       <header sticky>  "Goals · 3"
  │       <div.grid>  container-query: 1/2/3 col
  │         band.map(m => <Tile message={m} onOpen={open} />)
  │
  └─ open(m: Message) dispatch
        m.type === 'goal'     → setOpenGoalId(m.id)
        m.type === 'task'     → setOpenGoalId(m.goal_id ?? null)
        m.type === 'artifact' → setOpenArtifact(m)
        else                  → setOpenMessage(m)

          ┌──────────────────────────────────────────────┐
          │ Modals (portaled to document.body)           │
          │  openGoalId    → GoalDetailModal             │
          │  openArtifact  → ArtifactModal               │
          │  openMessage   → MessageDetailModal          │
          │                   └── MsgCard (read-only)   │
          └──────────────────────────────────────────────┘
```

## Container-query responsive breakpoints

```
GridView root (ResizeObserver)
  │
  ├── width > 220px  →  bands render
  │     ▼
  │   .grid (container-type: inline-size; container-name: gridband)
  │     ├── width < 400px  → 1 column
  │     ├── 400 ≤ w < 600  → 2 columns
  │     └── width ≥ 600    → 3 columns
  │
  └── width ≤ 220px  →  PlaceholderBanner (nothing else renders)
```

## Component tree (new files only)

```
CommsPanel/
  GridView/
    GridView.tsx          ← state owner (modal states, resize)
    GridView.module.css
    gridBands.ts          ← pure function (no React)
    Tile/
      Tile.tsx            ← presentational (badge + title + meta)
      Tile.module.css
  MessageDetailModal/
    MessageDetailModal.tsx  ← portal shell wrapping MsgCard
    MessageDetailModal.module.css
```

## BoardViewToggle — tab order

```
[Messages] [Goals & Tasks] [Artifacts] [All ←NEW]
    ↑             ↑              ↑           ↑
  CommsMsgList  GoalsView    ArtifactsView  GridView
  MessagesFilter NewGoalButton SummaryConfig  (null rightAction)
```
