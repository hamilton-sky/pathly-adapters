---
name: Architecture Proposal
---
# studio-polish — Architecture Proposal

## Skeleton loader pattern

```
FlowEditor/index.tsx

  loading === true
    └─► <SkeletonLoader />         ← inline component, same container
          4× <div class="shimmer"> ← CSS-only animation
          uses var(--bg-surface0/1)

  loading === false
    └─► <TabBar> Visual | YAML </TabBar>
        <VisualView> or <YamlView>
```

**Why CSS-only:** No JS timers means the skeleton automatically stops when the component unmounts. The existing `prefers-reduced-motion` override in index.html sets `--transition-base: 0ms`; the shimmer can use `animation-duration: var(--shimmer-duration, 1.4s)` and the reduced-motion media query can set `--shimmer-duration: 0ms`.

## Button loading prop pattern

```tsx
// Before
<button disabled={saving}>Save</button>

// After
<Button loading={saving}>Save</Button>

// Button.tsx internals:
// loading → disabled + .loading CSS class → ::after spinner
```

This keeps loading state as a UI concern inside the Button primitive, not scattered across every call site.

## Unsaved-changes guard (local state, not store)

```
FlowEditor
  state: pendingNavigation: SidebarItem | null

  selectedItem changes?
    └─► isDirty(currentPath) && newPath !== currentPath?
          YES → pendingNavigation = newItem  (show dialog)
          NO  → proceed to switch

  Dialog "Discard"
    └─► clearDirty(currentPath) → pendingNavigation = null → switch
  
  Dialog "Cancel"
    └─► pendingNavigation = null (no switch)
```

**Why local state:** The dirty-check concern belongs to FlowEditor. The store holds the dirty set; FlowEditor interprets it. If the navigation guard ever needs to be global (e.g. nav bar), promote to a store action then.

## installer module dependency graph (after split)

```
cli.py              ← entry: argparse, interactive menu, main()
  └─ imports ──────► orchestrate.py  ← _run_host, _run_host_uninstall
                         └─ imports ─► stitch.py
                         └─ imports ─► materialize.py
                         └─ imports ─► detect.py
                         └─ imports ─► resources.py
                         └─ imports ─► codex_plugin_config.py

setup_command.py    ← shim: from .cli import main; __all__ = ['main']
```

**Rule:** `orchestrate.py` does NOT import from `cli.py`. The dependency is one-directional: cli → orchestrate → implementation modules.
