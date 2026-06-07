Pathly Card — the standard surface container; optional header with title + actions.

```jsx
import { Card, Button, StatePill } from window.DesignSystem_ba588c

<Card title="fsm-sqlite" actions={<StatePill state="DONE" />}>
  <p>Body content…</p>
</Card>

<Card interactive onClick={open}>Clickable feature card</Card>
```

Pass `interactive` for clickable cards (hover lifts the border to accent). Header is omitted entirely when there's no `title`/`actions`.
