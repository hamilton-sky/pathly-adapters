Pathly Tabs — horizontal tab bar with count badges.

```jsx
import { Tabs } from window.DesignSystem_ba588c

const [tab, setTab] = React.useState('timeline')
<Tabs activeId={tab} onChange={setTab} tabs={[
  { id:'timeline', label:'Timeline', count:9 },
  { id:'events',   label:'Events',   count:33 },
  { id:'agents',   label:'Agents',   count:8 },
  { id:'sql',      label:'SQL' },
]} />
```

`variant="underline"` (default) for in-panel tabs; `variant="pill"` for a top-level accent-tinted view switch.
