---
name: Flow Diagram
---
# antigravity-adapter — Flow Diagram

## Adapter install pipeline

```
Developer runs:
  pathly-setup antigravity --apply
         |
         v
  cli.py: parse args
         |
         v
  detect.py: _HOST_MARKERS["antigravity"]
    → checks ~/.gemini/antigravity-cli/ exists?
         |
    yes  |  no
         |──────→ (skipped if no-args mode)
         v
  orchestrate.py: ALLOWED_HOSTS["antigravity"]
    → _load_install_yaml("antigravity")
         |
         v
  adapter_meta_path("antigravity")
    = src/pathly_data/adapters/antigravity/_meta/
         |
         ├─── *.yaml (agent) ──────────────────────────────────┐
         │      stitch_agent(core_agents/<name>.md, meta.yaml)  │
         │              ↓                                        │
         │      → dest = ~/.gemini/antigravity-cli/agents/      │
         │        <name>.md  ←─── written by materialize()      │
         │                                                       │
         ├─── *_skill.yaml ──────────────────────────────────── │
         │      stitch_skill(core_skills/<name>.md, meta.yaml)  │
         │              ↓                                        │
         │      → skills_dest =                                  │
         │          ~/.gemini/antigravity-cli/skills/            │
         │        <skill>/SKILL.md ←─── materialize()           │
         │                                                       │
         └─── templates/* ──────────────────────────────────── │
                core/templates/**/*.md                          │
                      ↓                                         │
                → ~/.gemini/antigravity-cli/                    │
                    plugins/pathly/templates/                   │
                  <template>.md ←─── materialize()             │
                                                               │
         ┌─────────────────────────────────────────────────────┘
         v
  .pathly-manifest.json written to each dest
    (tracks owned files for repair/uninstall)
         |
         v
  stdout: [antigravity] Wrote N file(s) to ~/.gemini/...
```

## Detection flow (auto-detect mode)

```
pathly-setup  (no args)
      |
      v
detect_hosts()
  checks each host's _HOST_MARKERS:
  ┌─────────────────────────────────────────────┐
  │ claude    → ~/.claude/           exists? ───▶ included
  │ codex     → ~/.codex/            exists? ───▶ included
  │ copilot   → ~/.vscode/           exists? ───▶ included
  │ antigravity→~/.gemini/antigravity-cli/ ?  ───▶ included
  └─────────────────────────────────────────────┘
      |
      v
  _run_host() called for each detected host
  (independent — failure in one does not block others)
```

## Uninstall flow

```
pathly-setup antigravity --uninstall
      |
      v
  _run_host_uninstall("antigravity")
      |
      ├── uninstall(agents dest)   → removes manifest-tracked .md files
      ├── uninstall(skills dest)   → removes manifest-tracked skill dirs
      └── uninstall(templates dest)→ removes manifest-tracked templates
```
