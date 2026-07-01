## Design System Output

# Design System — dbexplorer-trends-tab

> Stack: react · Date: 2026-06-11

## Query
New TrendsTab inside DBExplorer FeatureModal — 4 sections: Daily Cost Bar Chart, 18-Week Activity Heatmap, Cache Efficiency Line Chart, CSV Export Button.

---

## 1. Color Palette

### Chart: Daily Cost Bar Chart

| Use case | Token | Dark value |
|---|---|---|
| `costReported` bar fill | `var(--green)` | `#34D399` |
| `costEstimated` bar fill | `var(--runtime)` | `#2DD4BF` at `opacity: 0.45` |
| Bar chart background | `var(--bg-surface1)` | `#283044` |
| X/Y axis lines + ticks | `var(--text-disabled)` | `#4A5568` |
| Axis labels | `var(--text-muted)` | `#8899B0` |
| Tooltip background | `var(--bg-mantle)` | `#0B0F1A` |
| Tooltip border | `var(--border-color)` | `#283044` |
| Tooltip text | `var(--text-primary)` | `#E2E8F0` |

### Heatmap: 18-Week Activity

No suitable graduated-intensity tokens exist in tokens.css. Define 5 new variables (add to `tokens.css` `:root`):

| Variable | Dark value | Meaning |
|---|---|---|
| `--heatmap-level-0` | `#1E2433` (= `--bg-surface0`) | No activity |
| `--heatmap-level-1` | `rgba(52, 211, 153, 0.18)` | Low |
| `--heatmap-level-2` | `rgba(52, 211, 153, 0.38)` | Moderate |
| `--heatmap-level-3` | `rgba(52, 211, 153, 0.62)` | High |
| `--heatmap-level-4` | `var(--green)` = `#34D399` | Peak |

Light-theme overrides (add inside `[data-theme="light"]`):

| Variable | Light value |
|---|---|
| `--heatmap-level-0` | `#E2E8F0` |
| `--heatmap-level-1` | `rgba(4, 120, 87, 0.18)` |
| `--heatmap-level-2` | `rgba(4, 120, 87, 0.38)` |
| `--heatmap-level-3` | `rgba(4, 120, 87, 0.62)` |
| `--heatmap-level-4` | `#047857` |

### Chart: Cache Efficiency Line

| Use case | Token |
|---|---|
| Line stroke | `var(--accent)` |
| Dot fill (data point) | `var(--accent)` |
| Dot stroke | `var(--bg-mantle)` |
| Area fill under line | `var(--accent-bg)` |
| Gap (null segment) | No line drawn — `connectNulls={false}` |
| Summary stat value | `var(--accent)` |
| Summary stat label | `var(--text-muted)` |

### CSV Export Button

| State | Token |
|---|---|
| Default background | `var(--bg-surface1)` |
| Default border | `var(--border)` |
| Default text | `var(--text-secondary)` |
| Hover background | `var(--btn-b-hover-bg)` |
| Hover border | `var(--btn-b-hover-border)` |
| Hover text | `var(--btn-b-hover-color)` |
| Active background | `var(--btn-b-active-bg)` |

### Empty state (all sections)

| Token | Use |
|---|---|
| `var(--text-muted)` | Empty state message text |
| `var(--text-disabled)` | Icon/glyph if shown |

---

## 2. Typography

| Element | Size token | Weight token | Family |
|---|---|---|---|
| Section heading | `var(--font-size-sm)` = 11px | `var(--font-weight-semibold)` | base |
| Section meta (e.g., overall %) | `var(--font-size-sm)` | `var(--font-weight-normal)` | base |
| Axis labels | `var(--font-size-xs)` = 10px | `var(--font-weight-normal)` | mono |
| Y-axis dollar values | `var(--font-family-mono)` | `var(--font-weight-normal)` | mono |
| Tooltip value | `var(--font-size-sm)` | `var(--font-weight-semibold)` | mono |
| Tooltip label | `var(--font-size-xs)` | `var(--font-weight-normal)` | base |
| CSV button label | `var(--font-size-sm)` | `var(--font-weight-medium)` | base |
| Empty state text | `var(--font-size-sm)` | `var(--font-weight-normal)` | base |
| Cache summary stat | `var(--font-size-md)` = 14px | `var(--font-weight-semibold)` | mono |

---

## 3. Layout Rules

### Tab panel container
Matches existing `.mBody` in FeatureModal — inherits padding `16px 20px`. TrendsTab inner container uses `.container` pattern from AgentsTab: `display: flex; flex-direction: column; gap: 24px`.

### Section spacing
Use the same `.section` pattern as AgentsTab: `gap: 14px` between heading and content.

| Element | Value |
|---|---|
| Between sections | `var(--space-12)` = 24px (via container `gap`) |
| Section head → content gap | `var(--space-7)` = 14px |
| Chart left/right padding | 0 (Recharts `margin={{ left: 0, right: 16 }}`) |

### Daily Cost Bar Chart
| Property | Value |
|---|---|
| Chart height | 180px |
| Bar size | 10px per bar series |
| Bar gap within group | 2px |
| Bar category gap | 24% |

### 18-Week Activity Heatmap
| Property | Value |
|---|---|
| Grid | `display: grid; grid-template-columns: repeat(18, 1fr)` |
| Cell size | 12px × 12px |
| Cell gap | 3px |
| Cell border-radius | `var(--radius-xs)` = 3px |
| Level coloring | `background: var(--heatmap-level-N)` via `data-level` attribute |
| Total width (approx) | 18 × (12 + 3) − 3 = 267px — left-align, no stretch |

### Cache Efficiency Line Chart
| Property | Value |
|---|---|
| Chart height | 140px |
| Y-axis domain | `[0, 100]` |
| Y-axis tick format | `{value}%` |
| Dot radius | 3px |
| Active dot radius | 5px |
| Summary stat position | Above chart, right-aligned in section head row |

### CSV Export Button
| Property | Value |
|---|---|
| Height | 28px |
| Padding | `4px 12px` |
| Border-radius | `var(--radius-md)` = 5px |
| Border | `var(--border)` |
| Placement | Below heatmap, left-aligned |

---

## 4. Empty State Spec

| Section | Message | Color | Font size |
|---|---|---|---|
| Daily Cost Bar Chart | "No cost data recorded yet" | `var(--text-muted)` | `var(--font-size-sm)` |
| Activity Heatmap | "No activity in the last 18 weeks" | `var(--text-muted)` | `var(--font-size-sm)` |
| Cache Efficiency | "No cache data available" | `var(--text-muted)` | `var(--font-size-sm)` |

All empty states: `text-align: center; padding: 2rem;` — mirrors AgentsTab `.empty` class. Reuse `.empty` directly.

---

## 5. Component-Level UX Rules

### Daily Cost Bar Chart — tooltips
- Recharts `<Tooltip>` with custom content.
- Format: date label on top (`MMM DD`), then two rows: `Reported: $0.0000` / `Estimated: $0.0000`.
- Cursor style: `fill: var(--bg-surface1)` at `opacity: 0.5`.
- Y-axis tick formatter: `(v) => '$' + v.toFixed(4)` — always 4 decimal places.
- X-axis tick formatter: day string already in `MMM DD` format — render as-is.

### Daily Cost Bar Chart — stacking
- Use Recharts `stackId="cost"` on both Bar series.
- `costReported` renders first (bottom), `costEstimated` renders on top.
- Legend: small colored square + label. Reported = `var(--green)`, Estimated = `var(--runtime)` at reduced opacity. Place legend at `verticalAlign: 'top'` with `height: 28`.

### Activity Heatmap — tooltips
- Pure CSS grid, no Recharts. Use a native `title` attribute on each `<div>` cell: `"MMM DD — N runs"`.
- On hover: cell `opacity` transitions from 1.0 to 0.8 (`transition: opacity 150ms ease-out`).
- `data-level` values 0–4 drive background via CSS attribute selectors — no JS class toggling.
- Render order: columns = weeks (left = oldest, right = most recent), rows = day-of-week (top = Mon, bottom = Sun).

### Cache Efficiency Line Chart — gap behavior
- `connectNulls={false}` — when a run has zero denominator (cache_reads + cache_misses = 0) pass `null` for that data point; Recharts renders a visible gap in the line.
- Dot renders only on non-null points.
- Summary stat above chart shows overall cache hit rate across all non-null runs as `XX.X% cache hit`.

### CSV Export
- Button label: "Export CSV".
- On click fires a callback; does not navigate or reload.
- Disabled state (no data): `opacity: 0.4; cursor: not-allowed; pointer-events: none`.

---

## 6. CSS Variable Extensions

Add to `tokens.css` `:root` (after the existing `--badge-*` block):

```css
/* --- Heatmap intensity levels ----------------------------------- */
--heatmap-level-0: #1E2433;
--heatmap-level-1: rgba(52, 211, 153, 0.18);
--heatmap-level-2: rgba(52, 211, 153, 0.38);
--heatmap-level-3: rgba(52, 211, 153, 0.62);
--heatmap-level-4: var(--green);
```

Add inside `[data-theme="light"]`:

```css
--heatmap-level-0: #E2E8F0;
--heatmap-level-1: rgba(4, 120, 87, 0.18);
--heatmap-level-2: rgba(4, 120, 87, 0.38);
--heatmap-level-3: rgba(4, 120, 87, 0.62);
--heatmap-level-4: #047857;
```

No other theme overrides required — all other themes use `var(--green)` and `var(--bg-surface0)` as their base, so levels 1–3 interpolate correctly against each theme's green anchor.

---

## Builder Notes

- Reuse `.container`, `.section`, `.sectionHead`, `.sectionTitle`, `.sectionMeta`, `.empty` class names from `AgentsTab.module.css` — do not duplicate; import or mirror the same pattern in `TrendsTab.module.css`.
- All Recharts responsive wrappers use `<ResponsiveContainer width="100%" height={N}>`.
- The heatmap grid is a single `<div className={styles.heatmap}>` containing 126 `<div>` cells with `data-level={0|1|2|3|4}`.
- The tab strip in FeatureModal uses `TabId` union — add `'trends'` to that union and a corresponding entry in the `tabs` array.
- Stack: react + recharts (already a project dependency).
```
