# Pathly Workspace Sidebar

A drop-in, self-contained file-tree sidebar for the Pathly app. Each component
lives in its own folder with its own CSS module, so you can copy the whole
`pathly-sidebar/` directory into the project (e.g. `src/components/pathly-sidebar/`)
and use it as-is, or lift individual pieces.

## Usage

```tsx
import { Sidebar, useFileTree } from '@/components/pathly-sidebar'

export function WorkspacePane() {
  const { controller } = useFileTree({
    // all optional
    projectName: 'acme-api',
    onSelectFile: (path) => openInEditor(path), // your handler
  })
  return <Sidebar controller={controller} liveCount={2} />
}
```

`useFileTree` owns all state (tree, expand/collapse, selection, filter, menu,
rename, create, delete, drag state, toast). `Sidebar` is presentational and
drives everything through the returned `controller`.

## What it does

- **File tree** with folders-first sorting, expand/collapse, and a filter box.
- **Animated icons**
  - Files use lucide `FileText` and **rotate a full turn on row hover**.
  - Folders use lucide `Folder` ↔ `FolderOpen` and **animate open/closed** —
    open while expanded, and preview-open on hover.
- **Right-click _and_ ⋯ menu** (same menu): Open in Editor (files), New File /
  New Folder (folders), Copy Path, Copy Relative Path, Rename, Delete.
- **Inline create & rename** with an in-row input.
- **Drag & drop** any file/folder into another folder (or the root). Blocks
  dropping into itself, a descendant, or its current parent. Uses the
  `PATHLY_DRAG_MIME` payload on `dataTransfer`.
- **Delete confirmation** modal and a **copy toast**.
- **Collapse-all** action in the header.
- Plan folders (`pathly/plans/<name>`) show a lifecycle **state pill**.

## Dependencies

- `react` (17+/18)
- [`lucide-react`](https://lucide.dev) — already used by Pathly.

## Styling

CSS-module files use Pathly's existing custom properties (`--bg-mantle`,
`--accent`, `--text-muted`, `--radius-md`, `--shadow-lg`, …), so it inherits the
active theme automatically. No extra global CSS required.

The icon animations rely on one attribute contract: `TreeRow` renders each row
with `data-pw-row`, and `FileIcon` / `FolderIcon` key their hover animation off
`:global([data-pw-row]):hover`. Keep that attribute if you build your own row.

## Structure

```
pathly-sidebar/
├── index.ts                 barrel export
├── types.ts                 shared types + FileTreeController
├── hooks/useFileTree.ts     all state + operations
├── lib/
│   ├── kinds.ts             kind/state colours, classification
│   ├── treeUtils.ts         add / rename / remove / move / canDropInto
│   └── sampleTree.ts        demo data
├── Sidebar/                 container (composes everything)
├── TreeRow/                 one row: icons, drag&drop, hover actions, rename
├── CreateRow/               inline new-file / new-folder input
├── ContextMenu/             right-click / ⋯ dropdown
├── DeleteDialog/            delete confirmation modal
├── Toast/                   transient "Copied …" toast
├── FileIcon/                rotate-on-hover file glyph
├── FolderIcon/              open/close folder glyph
└── StatePill/               plan lifecycle badge
```

## Notes

- Single-clicking a file only **selects** it (fires `onSelectFile`); it never
  auto-opens the markdown editor. Opening is explicit via the menu.
- Swap in your own data with `useFileTree({ initialTree, initialCollapsed })`.
  `TreeNode` is `{ name, type: 'file' | 'folder', state?, children? }`.
