# Phone Notifications from Pathly

Design notes and options for getting Pathly / Claude on your computer to push
messages to your phone (WhatsApp, Telegram, ntfy.sh, etc.).

## Findings

### Pathly itself has no phone integration

`pathly-adapters` is an installer that materializes Pathly agent and skill
files into Claude Code, Codex, and Copilot (`README.md:3`, host table at
`README.md:64-71`). The only network surface it exposes is the local FSM
HTTP server on `127.0.0.1:8765` (`README.md:80-97`). Nothing in this repo
reaches the public internet, and nothing talks to your phone.

To get phone notifications, we'd add a new piece that bridges Pathly's
local event stream to a public push channel.

### What Pathly already exposes that we can build on

The FSM HTTP server publishes an SSE event stream of `EVENTS.jsonl`:

```
GET http://127.0.0.1:8765/events/stream
```

Events include things like stage transitions, agent completion, action
completion, and human-input-required signals. Any notifier we add can
subscribe to this stream and forward selected events — no changes to
the FSM engine itself.

## Options for the push channel

| Option           | Setup     | Cost     | Trust model                             | Best for                                  |
|------------------|-----------|----------|-----------------------------------------|-------------------------------------------|
| **ntfy.sh**      | 1 minute  | Free     | Public topic, knowledge-of-name = read  | Personal "ping me" alerts                 |
| **Telegram bot** | 5 minutes | Free     | Bot token, you DM the bot               | Personal use, more polished UI            |
| **Pushover**     | 5 minutes | ~$5 once | Per-device API key                      | Reliable mobile delivery, no extra app    |
| **Twilio SMS**   | 30 min    | Per-msg  | Account + verified number               | Production, reach any phone               |
| **Twilio WhatsApp** | 30 min | Per-msg  | Account + WhatsApp sandbox or business  | WhatsApp specifically                     |
| **Meta WhatsApp Cloud API** | Hours | Per-msg | Verified Meta business account     | Official WhatsApp at scale                |
| **Email**        | 0 min     | Free     | Existing mail account                   | Lowest setup, phone's mail app notifies   |

### Why ntfy.sh stood out for a first version

- Zero account, zero API key. A single `curl -d "msg" ntfy.sh/<topic>` works.
- iOS and Android apps subscribe to a topic name.
- Supports title, priority, tags, action buttons, attachments, markdown.
- Self-hostable if the public server's open-topic model isn't acceptable.

**Caveat:** the public `ntfy.sh` server is open. Anyone who guesses your
topic name can read (and post to) it. Mitigations: use a long random
topic, use ntfy.sh Pro auth, or self-host.

## Recommended solution

### Packaging

Ship the bridge as a Pathly skill inside this repo, installed via
`pathly-setup` like every other skill. Rationale: the bridge needs to
talk to the local FSM HTTP server, so it lives next to the FSM.

Files to add:

- `src/pathly_data/core/skills/utilities/notify.md` — user-facing skill.
  Commands like `/pathly notify setup <topic>`, `/pathly notify test`,
  `/pathly notify on|off`. Writes config to `~/.pathly/notify.json`.
- `src/pathly_orchestrator/notify_daemon.py` (or similar) — small Python
  process. Subscribes to `http://127.0.0.1:8765/events/stream`, filters
  events by type, POSTs to `https://ntfy.sh/<topic>` with a formatted
  title and body. Started lazily, the same way `pathly-fsm-http` is.
- `pyproject.toml` — new console-script entry point `pathly-notify`.

### Payload (per event)

```
Title:    Pathly: <feature> — <stage transition>
Priority: high  if status=failed or human-input-required, else default
Tags:     event_type, status
Body:     feature=<name>
          from_stage=<x> -> to_stage=<y>
          status=<ok|failed|paused>
          actor=<agent or human>
          ts=<iso8601>
          extra: <any non-empty event fields>
```

### Default event filter

Forward by default:

- `STAGE_DONE`
- `FEATURE_DONE`
- any event with `status=failed`
- any event flagged as needing human input (e.g. `HUMAN_INPUT_REQUIRED`)

Suppress by default (too noisy):

- per-tool call events
- per-token telemetry events

User-tunable via `~/.pathly/notify.json`.

### Security

- Generate topics with `secrets.token_urlsafe(12)`. Don't let users pick
  short topic names.
- Print the topic once at setup with a "treat this like a password" note.
- Never log the topic to `EVENTS.jsonl` or activity logs.
- Document that anyone with the topic name can also POST to it — so if a
  topic leaks, the user should rotate it.

## Alternatives we did not pick (and why)

- **Modify the FSM engine to call ntfy.sh directly.** Invasive; the FSM
  lives in `hamilton-sky/pathly`, not this repo. Subscribing to the
  existing SSE stream is non-invasive.
- **Claude Code `Stop` hook only.** Fires when Claude finishes a turn,
  not when the FSM transitions. Wrong granularity for Pathly state.
- **Hook into `record_activity` HTTP endpoint.** Would require
  intercepting requests in-process. SSE consumption from outside is
  cleaner.
- **Dedicated protocol server.** Possible but over-engineered for a one-way push. A
  background daemon + a tiny skill is simpler and survives Claude Code
  restarts.

## Open questions before implementing

1. Should the daemon auto-start on the first `/pathly` command (like
   `pathly-fsm-http` does via `fsm-call`), or only when the user opts in
   with `/pathly notify on`?
2. Should `pathly-setup --uninstall` also stop the daemon and remove
   `~/.pathly/notify.json`?
3. Do we want a one-line `pathly-notify send "<msg>"` CLI for ad-hoc
   manual pings (useful for scripts and CI), in addition to the
   FSM-event bridge?
4. Multi-project support: if the user has several repos and one ntfy
   topic, should the daemon prefix every message with the repo name?

## Rough size estimate

Three files, ~150 lines total. No new runtime dependencies beyond
`requests` (already transitively available) or the stdlib `urllib`.
