---
name: Flow Diagram
---
# Studio A11y Phase 1 — Flow Diagrams

## Focus Trap: Modal Open/Close Lifecycle

```
User action
    │
    ▼
Modal mounts
    │
    ├─ useFocusTrap(ref) runs
    │      │
    │      ├─ store previousFocus = document.activeElement
    │      ├─ find all focusable children in ref.current
    │      ├─ focus first child
    │      └─ attach keydown listener (Tab / Shift+Tab cycling)
    │
    │   ┌──────────────────────────────────────┐
    │   │  Tab pressed                          │
    │   │    focus on last child?               │
    │   │      yes → focus first child          │
    │   │      no  → default Tab behavior       │
    │   │  Shift+Tab pressed                    │
    │   │    focus on first child?              │
    │   │      yes → focus last child           │
    │   │      no  → default Shift+Tab          │
    │   └──────────────────────────────────────┘
    │
    ▼
Modal unmounts (Escape / button click)
    │
    ├─ useFocusTrap cleanup
    │      ├─ remove keydown listener
    │      └─ previousFocus.focus() (if still in DOM)
    │
    └─ Focus returns to triggering element
```

---

## ContextMenu Keyboard Navigation

```
Context menu opens
    │
    ├─ role="menu" on container
    ├─ role="menuitem" + tabIndex=-1 on each item
    └─ useEffect: focus item[0]

User presses key
    │
    ├─ ArrowDown ──► setHoveredIndex((i+1) % n) + itemRefs[next].focus()
    ├─ ArrowUp ────► setHoveredIndex((i-1+n) % n) + itemRefs[prev].focus()
    ├─ Home ───────► setHoveredIndex(0) + itemRefs[0].focus()
    ├─ End ────────► setHoveredIndex(n-1) + itemRefs[n-1].focus()
    ├─ Enter/Space ► item.onClick() → onClose()
    └─ Escape ─────► onClose() [existing handler, unchanged]
```

---

## Chip Toggle State Machine

```
Chip (button role="switch")
    │
    ├─ aria-checked="false"  →  [Space/Enter]  →  aria-checked="true"
    │      visual: inactive                          visual: active (color token)
    │
    └─ aria-checked="true"   →  [Space/Enter]  →  aria-checked="false"
           visual: active                            visual: inactive

readOnly chip (span, not button):
    │
    └─ Not in tab order. No keyboard interaction. Purely presentational.
```
