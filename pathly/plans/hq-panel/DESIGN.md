# Design System — HQ Panel (ChatPanel Upgrade)

> Stack: React 18 + Vite + CSS Modules · 2026-06-01

## Query
Pipeline command center panel — flow control, stage/adapter/cost status, live FSM decision menu, session continuity, reroute interaction.

## Design System Output

Script queries run:
- `--domain ux`: pipeline command center, destructive action confirm, live feed aria-live keyboard navigation
- `--domain style`: status strip indicators (Real-Time Monitoring pattern), toolbar button groups
- `--domain product`: chat panel + analytics dashboard hybrid

Applied guidelines:
- Real-Time Monitoring: live status indicators (pulsing), streaming data, alert notification prominence, connection status shown at all times
- Interaction / Disabled States (severity: medium): `opacity: 0.45` + `cursor: not-allowed` on disabled controls, never same style as enabled
- Interaction / Confirmation Dialogs (severity: high): confirm before irreversible actions — inline confirm, not modal
- Accessibility / Keyboard Navigation (severity: high): tab order matches visual order, no keyboard traps
- AI Interaction / Streaming (severity: medium): stream menu options token-by-token with typewriter reveal, never hold until 100% complete
- Analytics Dashboard: data-dense, drill-down, cool/neutral palette — applies to the status strip

## Builder Notes
- Reference this file when implementing HQ panel components
- All colors from `tokens.css` CSS custom properties — no hardcoded hex
- Stack: React 18 + CSS Modules (no Tailwind, no shadcn)
