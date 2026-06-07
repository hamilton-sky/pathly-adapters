Pathly Input — single-line text field; accent focus ring, optional leading icon.

```jsx
import { Input } from window.DesignSystem_ba588c

<Input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter…" />
<Input label="Feature path" value={p} onChange={set} />
<Input icon={<Search size={13} />} placeholder="Search the skill text…" />
```

Sizes `sm` / `md`. Pass `label` for an uppercase field label above the input.
