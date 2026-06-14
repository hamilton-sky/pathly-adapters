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
| `PATHLY_PROJECT_ROOT` | _(none)_ | Absolute path to your project root — **required for hooks** |
| `PATHLY_API_SECRET` | _(auto)_ | Shared secret for `X-Pathly-Secret` auth. If unset, a 64-char hex token is auto-generated and saved to `~/.pathly/server_secret.txt` on first run. Set explicitly to pin the secret across restarts or share it with external callers. |
| `ANTHROPIC_API_KEY` | _(none)_ | Enables feedback auto-classification (optional) |
| `PATHLY_CORS_ORIGIN` | `null` | Allowed CORS origin for SSE stream (e.g. `http://localhost:3000`) |

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

Hooks require `PATHLY_PROJECT_ROOT` to be set in Claude Code's environment. Add to your shell profile or Claude Code settings:

```bash
export PATHLY_PROJECT_ROOT=/path/to/your/project
```

Verify hooks are working by checking `~/.pathly/hook.log` after a feedback file is written.

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

## Troubleshooting

### Server won't start
- Check `PATHLY_FSM_HTTP_PORT` is not already in use: `lsof -i :8765`
- Check Python version: `python --version` (requires 3.11+)

### Hooks not running
- Ensure `PATHLY_PROJECT_ROOT` is set: `echo $PATHLY_PROJECT_ROOT`
- Check `~/.pathly/hook.log` for skip messages

### Feedback files not classified
- Set `ANTHROPIC_API_KEY` in your environment
- Check `~/.pathly/hook.log` for errors

## Releasing a New Version

1. Update adapter package version in `pyproject.toml`
2. Update Studio app version in `studio/package.json` and `studio/package-lock.json` when the release includes Studio changes
3. Update root `package.json` version to match `pyproject.toml`
4. Update version references in `README.md`, `docs/SECURITY.md`, `docs/PRODUCTION_READINESS.md`, and `docs/SYSTEM_REVIEW.md`
5. Add a `CHANGELOG.md` entry describing the changes
6. Commit and tag: `git tag v<version>`
7. Push tag: `git push origin v<version>`
8. GitHub Actions will run tests and publish to PyPI automatically
