Pathly Button — the app-wide action button; accent-tinted by default.

```jsx
import { Button } from window.DesignSystem_ba588c

<Button variant="primary" onClick={save}>Save</Button>
<Button variant="cta" icon={<Download size={14} />}>Export Skill</Button>
<Button variant="secondary" size="sm">Refresh</Button>
<Button variant="destructive" size="sm">Abort</Button>
<Button loading>Running…</Button>
```

Variants: `primary` (accent tint — default), `cta` (solid accent fill, one per view), `secondary` (bordered toolbar button), `ghost`, `destructive`. Sizes: `sm` (4×10, 11px) and `md` (6×14, 13px). Pass `icon` for a leading glyph, `loading` for an inline spinner.
