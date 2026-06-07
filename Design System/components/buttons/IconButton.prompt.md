Pathly IconButton — square icon-only control for toolbars, topbars and row actions.

```jsx
import { IconButton } from window.DesignSystem_ba588c
import { Menu, Trash2 } from 'lucide-react'

<IconButton title="Open sidebar"><Menu size={15} /></IconButton>
<IconButton title="Delete" variant="danger"><Trash2 size={14} /></IconButton>
<IconButton title="HQ" active><Brain size={14} /></IconButton>
```

Always pass `title` (tooltip + aria-label). Variants: `default`, `danger`, `muted`. Sizes: `sm` (26px) / `md` (30px). `active` renders the selected accent state.
