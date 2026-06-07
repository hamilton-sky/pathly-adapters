Pathly overlay primitives — Tooltip & ContextMenu.

```jsx
import { Tooltip, ContextMenu } from window.DesignSystem_ba588c
import { Pencil, Trash2 } from 'lucide-react'

<Tooltip label="New Pathly window" description="Open multiple projects" shortcut="⌘N">
  <IconButton title="New"><Copy size={14} /></IconButton>
</Tooltip>

<ContextMenu items={[
  { label:'Rename', icon:<Pencil size={14} />, onClick:rename },
  { separator:true },
  { label:'Delete', icon:<Trash2 size={14} />, danger:true, onClick:del },
]} />
```

`Tooltip` wraps a trigger and shows on hover after a short delay. `ContextMenu` renders just the menu surface (rows use the app-wide hover→accent treatment) — you supply the trigger/positioning.
