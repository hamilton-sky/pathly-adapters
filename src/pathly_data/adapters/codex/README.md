# Codex Adapter

Codex exposes Pathly as plugin skills, not as custom slash commands in current
Codex builds. Do not document `/pathly` as a Codex command unless a future Codex
release supports plugin-defined slash commands.

Use explicit natural-language skill prompts. These give Codex the strongest
signal to select the Pathly plugin:

```text
Use Pathly help
Use Pathly doctor on this project
Use Pathly to add password reset
Use Pathly to debug checkout button does nothing
Use Pathly to explore how auth state flows
Use Pathly flow for checkout-flow
```

Once the plugin is selected, use the packaged `pathly-fsm-call` helper for the
HTTP lifecycle steps instead of hand-writing raw `curl` calls. That bridge is
the Codex-side equivalent of the fully wired host integration:

```text
pathly-fsm-call next-action ...
pathly-fsm-call complete-stage ...
pathly-fsm-call record-activity ...
```

Short forms may work when Codex confidently selects the plugin:

```text
Pathly help
Pathly doctor
Pathly add password reset
Pathly debug checkout button does nothing
Pathly explore how auth state flows
Pathly flow checkout-flow
```

If Codex responds by inspecting the current workspace instead of saying it is
using Pathly, the plugin was not selected. Retry with `Use Pathly ...`, confirm
Pathly is enabled in Settings -> Plugins, then restart Codex after changing a
local marketplace plugin.

Codex reserves slash commands such as `/help` for its own UI. If a user types
`/pathly`, current Codex versions may report it as an unrecognized command.

## Install Globally On One Machine

Codex local plugins are registered through a marketplace root. Once the
marketplace is added, Pathly is available from any Codex workspace on that
machine.

```powershell
git clone https://github.com/hamilton-sky/pathly
cd pathly
pip install -e pathly-adapters/
pathly-setup codex --apply
```

`pathly-setup codex --apply` writes the local marketplace under
`~/.codex/pathly-marketplace`, enables `pathly@pathly-local` in
`~/.codex/config.toml`, and refreshes the marketplace with
`codex plugin marketplace remove/add` when the Codex CLI is available. If the
CLI is not available or the refresh fails, the config file registration remains
as a fallback.

Restart Codex after installing or changing the local marketplace. If the plugin
was enabled but not selected in an existing thread, start a fresh thread after
the restart.

## Role Execution In Codex

Core Pathly skills use host-neutral directions such as `Spawn builder`.
Generated Codex skills prepend `SKILL_EXECUTION.md` so those directions match
the capabilities exposed in the current Codex session:

- If a named Pathly role is callable, Codex may invoke it directly.
- Otherwise, Codex executes lifecycle-role work in the current agent.
- Generic sub-agent delegation is used only when the user requested delegation
  and the active Codex tool policy permits it.

The installed `agents/*.toml` files preserve role contracts for Codex surfaces
that load custom agents; their presence does not guarantee named-agent
invocation in an already running session.

Manual PowerShell equivalent:

```powershell
$market = "C:\tmp\pathly-marketplace"
$plugin = "$market\plugins\pathly"
New-Item -ItemType Directory -Path "$market\.agents\plugins" -Force
New-Item -ItemType Directory -Path "$plugin" -Force
New-Item -ItemType Junction -Path "$plugin\.codex-plugin" -Target ".\adapters\codex\.codex-plugin"
New-Item -ItemType Junction -Path "$plugin\skills" -Target ".\adapters\codex\skills"
New-Item -ItemType Junction -Path "$plugin\core" -Target ".\core"

# Write marketplace.json as shown in the root README, then:
codex plugin marketplace remove pathly-local
codex plugin marketplace add $market
```

Every user needs their own local clone or installed package path. Do not point a
friend's Codex install at a path that only exists on your machine.

Recommended CLI fallback from inside a Codex workspace:

```text
pathly-setup codex --dry-run
pathly-setup codex --apply
```

The Codex adapter uses `_meta/*.yaml` metadata files that are stitched with
content from `core/agents/` and `core/skills/` at install time. The resulting
agent files are deployed to `~/.codex/agents/`, skills to `~/.agents/skills/`,
and a plugin bundle to `~/.codex/plugins/pathly/` by
`pathly-setup codex --apply`.

Claude Code keeps its own model-specific wrappers under
`adapters/claude/` for the Claude plugin package.
