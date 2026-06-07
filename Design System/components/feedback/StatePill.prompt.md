Pathly feedback primitives — status & progress signals.

```jsx
import { Badge, StatePill, ProgressBar, Spinner } from window.DesignSystem_ba588c

<StatePill state="DONE" />
<StatePill state="BUILDING" />
<Badge variant="flow" label="flow" />
<Badge color="var(--blue)" label="events 47" />
<ProgressBar value={3} max={3} color="var(--purple)" label="3/3" />
<Spinner />
```

`StatePill` is the FSM-stage pill (PLANNING/BUILDING/REVIEWING/TESTING/RETRO/DONE) — pass `solid` for a filled header variant. `Badge` is a tinted monospace chip (presets: core/flow/integration/body/neutral, or any `color`). `ProgressBar` takes `value`/`max` and an optional fraction `label`.
