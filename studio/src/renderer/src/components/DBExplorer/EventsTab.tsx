import type { EventData } from './dbExplorerData'
import styles from './EventsTab.module.css'

interface EventsTabProps {
  events: EventData[]
}

export function EventsTab({ events }: EventsTabProps): JSX.Element {
  return (
    <div>
      <p className={styles.sublabel}>Pipeline Events</p>
      <div className={styles.eventList}>
        {events.map((ev, i) => (
          <div key={i} className={styles.eventRow}>
            <span className={styles.dotWrap}>
              <EventDot color={ev.dotColor} />
            </span>
            <span className={styles.time}>{ev.time}</span>
            <span className={styles.type}>{ev.type}</span>
            <span className={styles.detail}>{ev.detail}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function EventDot({ color }: { color: string }): JSX.Element {
  const ref = (el: HTMLSpanElement | null): void => {
    if (el) el.style.setProperty('--dot-color', color)
  }
  return <span className={styles.dot} ref={ref} />
}
