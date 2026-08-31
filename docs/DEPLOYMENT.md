# Deployment Guide

## Prerequisites
- Python 3.11+
- pip or pipx

## Installation

### End-user install (recommended)
```bash
pipx install pathly-adapters
```

### Development install
```bash
git clone <repo>
cd pathly-adapters
pip install -e ".[dev]"
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|---|---|---|
| `PATHLY_FSM_HTTP_PORT` | `8765` | Port for the FSM HTTP server (validated 1–65535) |
| `PATHLY_FSM_HTTP_HOST` | `127.0.0.1` | Bind address. **Must be a loopback address** (`127.0.0.1`, `::1`, `localhost`). Any other value causes a startup error unless `PATHLY_EXPOSE_HOST=true` is also set. |
| `PATHLY_EXPOSE_HOST` | _(unset)_ | Set to `true` to allow a non-loopback `PATHLY_FSM_HTTP_HOST`. Prints a warning about unauthenticated SSE streams. Only needed when Studio and the FSM server run on different machines. |
| `PATHLY_PROJECT_ROOT` | _(none)_ | Absolute path to your project root — **required for the feedback-file watcher** |
| `PATHLY_API_SECRET` | _(auto)_ | Shared secret for `X-Pathly-Secret` auth. If unset, a 64-char hex token is auto-generated and saved to `~/.pathly/server_secret.txt` on first run. Set explicitly to pin the secret across restarts or share it with external callers. |
| `PATHLY_CORS_ORIGIN` | `*` | Allowed CORS origin for SSE stream (e.g. `http://localhost:3000`) |

## Running the FSM HTTP Server

### One-off (development)
```bash
export PATHLY_PROJECT_ROOT=/path/to/your/project
pathly-fsm-http
```

### Persistent (systemd — Linux)
Create `/etc/systemd/system/pathly-fsm.service`:
```ini
[Unit]
Description=Pathly FSM HTTP Server
After=network.target

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/path/to/your/project
Environment=PATHLY_FSM_HTTP_PORT=8765
Environment=PATHLY_FSM_HTTP_HOST=127.0.0.1
Environment=PATHLY_PROJECT_ROOT=/path/to/your/project
ExecStart=/usr/local/bin/pathly-fsm-http
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pathly-fsm
sudo systemctl start pathly-fsm
```

### Persistent (launchd — macOS)
Create `~/Library/LaunchAgents/com.pathly.fsm.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.pathly.fsm</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/pathly-fsm-http</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATHLY_PROJECT_ROOT</key>
    <string>/path/to/your/project</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardErrorPath</key>
  <string>/tmp/pathly-fsm.log</string>
</dict>
</plist>
```

Then: `launchctl load ~/Library/LaunchAgents/com.pathly.fsm.plist`

## Auth Token

The FSM server requires `X-Pathly-Secret` on all POST routes. The token is auto-generated on first run at `~/.pathly/server_secret.txt`. Studio reads it automatically via `shell:apiConfig` IPC.

**To rotate:** delete `~/.pathly/server_secret.txt`, then restart both the FSM server and Studio. Both will pick up the new value.

**To pin:** set `PATHLY_API_SECRET` in your environment before starting the server. The env var takes precedence over the file.

**Calling the API manually:**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -X POST http://127.0.0.1:8765/health -H "X-Pathly-Secret: $SECRET"
```

---

## Hook Setup

Feedback-file classification and TTL injection run as a file watcher inside
the FSM HTTP server (`pathly-fsm-http`), not as a per-tool hook. The watcher
requires `PATHLY_PROJECT_ROOT` to be set in the FSM server's own environment.
Add to your shell profile before starting `pathly-fsm-http`:

```bash
export PATHLY_PROJECT_ROOT=/path/to/your/project
```

Verify it's working by editing a `feedback/*.md` file under your project's
`pathly/features/<feature>/` directory and confirming the server injects TTL
frontmatter / `[REQ]`/`[ARCH]` tags within a couple of seconds.

Claude Code additionally gets a `Stop` hook (registered by
`pathly-setup claude --apply` into `~/.claude/settings.json`) that reports
session telemetry — unrelated to feedback classification.

## Health Check

```bash
curl http://localhost:8765/health
```

Expected response: `{"status": "ok", "server": "pathly-fsm-http"}`

## Running Pathly Studio

Studio is the local Electron UI for Canvas, Plan, Monitor, Conductor, and
Terminal. It uses the same local FSM server and project files as the host skills.

```bash
pathly-studio
```

Terminal sessions inside Studio use local Electron PTY IPC. The Conductor mini
terminal and the full bottom terminal share one xterm instance per terminal tab
id, so hiding a view keeps the process alive while bin actions kill and remove
the instance.

## Running headless (no desktop)

A pipeline run needs two processes: the FSM server, and a **spawn host** that actually launches
each stage's CLI. Studio is one spawn host; `pathly-pty-host` is the other, so a run can drain on a
server or in CI with no desktop present.

```bash
pathly-fsm-http &        # the FSM server
pathly-pty-host          # the spawn host
```

Run **exactly one** spawn host against a server — Studio or `pathly-pty-host`, not both. Each
answers every `TERMINAL_SPAWN` on the shared `/events/spawn` channel, so two hosts launch every
stage twice.

`pathly-pty-host` runs each stage as an ordinary subprocess (pipes, no pseudo-terminal, stdin
closed) and reports the result through the same `/runner/terminal/result` callback Studio uses, so
headless runs produce the same telemetry — cost, tokens, spans, invocations. Useful flags:

| Flag | Default | Purpose |
|---|---|---|
| `--host` / `--port` | `127.0.0.1:8765` | where the FSM server is listening |
| `--max-concurrent` | `5` | simultaneous CLI spawns; further spawns queue |
| `-v` / `--verbose` | off | log every spawn decision |

It exits cleanly on `SIGINT`/`SIGTERM`, killing each child's whole process group so no CLI outlives
the host. Stages configured as *interactive* are refused with a nameable error rather than hanging —
those need Studio and a human.

## Troubleshooting

### Server won't start
- Check `PATHLY_FSM_HTTP_PORT` is not already in use: `lsof -i :8765`
- Check Python version: `python --version` (requires 3.11+)

### Feedback files not classified / TTL not injected
- Ensure `PATHLY_PROJECT_ROOT` is set in the environment the FSM server was started in: `echo $PATHLY_PROJECT_ROOT`
- Ensure the feedback watcher feature flag is enabled (`PATHLY_FF_FEEDBACK_WATCHER`, on by default)
- Check the `pathly-fsm-http` server's own log output for watcher errors

## Releasing a New Version

1. Update adapter package version in `pyproject.toml`
2. Update Studio app version in `studio/package.json` and `studio/package-lock.json` when the release includes Studio changes
3. Update root `package.json` version to match `pyproject.toml`
4. Update version references in `README.md`, `CLAUDE.md`, `docs/SECURITY.md`, and `docs/PRODUCTION_READINESS.md`, then run `python scripts/check_version_sync.py` to confirm the JSON manifests (`package.json`, `studio/package.json`, codex `plugin.json`) match `pyproject.toml`
5. Add a `CHANGELOG.md` entry describing the changes
6. Commit and tag: `git tag v<version>`
7. Push tag: `git push origin v<version>`
8. GitHub Actions will run tests and publish to PyPI automatically
