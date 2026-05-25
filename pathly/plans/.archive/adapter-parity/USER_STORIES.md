---
name: User Stories
---
# adapter-parity — User Stories

## S1: Copilot users can archive completed features

**As a** Copilot user,
**I want** the `/pathly archive` and `/pathly archive-artifacts` skills available,
**so that** I can archive completed features the same way Claude users can.

**Acceptance criteria:**
- `src/pathly_data/adapters/copilot/_meta/archive_skill.yaml` exists and is valid YAML
- `src/pathly_data/adapters/copilot/_meta/archive-artifacts_skill.yaml` exists and is valid YAML
- Both `src/pathly_data/adapters/copilot/_meta/archive_skill.yaml` and `src/pathly_data/adapters/copilot/_meta/archive-artifacts_skill.yaml` exist, are valid YAML, and have the same `skill`, `filename`, and `natural_language` fields as the equivalent Claude files

## S2: Copilot and Codex users can commit changes via Pathly

**As a** Copilot or Codex user,
**I want** the `/pathly commit` skill available,
**so that** I can commit work without leaving the Pathly flow.

**Acceptance criteria:**
- `src/pathly_data/adapters/copilot/_meta/commit_skill.yaml` exists with same schema as Claude's
- `src/pathly_data/adapters/codex/_meta/commit_skill.yaml` exists with same schema as Claude's

## S3: Explorer agent has a behavioral contract

**As a** developer working on any adapter,
**I want** `src/pathly_data/core/agents/research/explorer.md` to exist,
**so that** the `explorer.yaml` metadata files in all three adapters have a backing contract.

**Acceptance criteria:**
- `src/pathly_data/core/agents/research/explorer.md` exists with frontmatter (`name`, `description`)
- The file describes the explorer agent's role, tool boundaries, inputs/outputs, and handoff contracts
- The description is consistent with the `description:` field in each adapter's `explorer.yaml`

## S4: Copilot install.yaml has no dead hooks config

**As a** developer maintaining the Copilot adapter,
**I want** the `hooks:` key in `install.yaml` to either be wired up or removed,
**so that** there is no silent gap between declared config and installed behavior.

**Acceptance criteria:**
- Option A (remove): `hooks:` key is absent from `copilot/_meta/install.yaml`; `pathly-setup --host copilot` installs without hook files and no regression
- Option B (implement): `setup_command.py` reads the `hooks:` block and materializes hook scripts to the correct Copilot extension directory
- Either way: no `hooks:` key that declares files without installing them

## S5: Studio focus rings use the theme token everywhere

**As a** Studio user switching between themes,
**I want** focus rings to change with the theme,
**so that** the `#89b4fa` Mocha blue doesn't bleed into Nord, Paper, or Solarized themes.

**Acceptance criteria:**
- `TopBar.module.css` contains zero occurrences of the literal string `#89b4fa`
- `Sidebar.module.css` contains zero occurrences of the literal string `#89b4fa`
- All `:focus-visible` rules in both files use `var(--focus-ring)` or `var(--accent)`
- `filterInput` in Sidebar has a visible focus ring when tabbed to (`:focus-visible` rule exists)
- Switching to the Paper theme shows a brown/orange focus ring, not blue, on focused sidebar items
