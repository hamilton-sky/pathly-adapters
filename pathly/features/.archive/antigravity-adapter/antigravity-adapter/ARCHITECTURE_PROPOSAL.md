---
name: Architecture Proposal
---
# antigravity-adapter — Architecture Proposal

## What this adapter is (and isn't)

The antigravity adapter is **purely configuration**. No new Python code is needed. The adapter adds:
1. A `_meta/` directory with YAML files that the existing `orchestrate.py` and `stitch.py` machinery already knows how to process.
2. Two small edits to `orchestrate.py` and `detect.py` to register the new host name.

The stitching pipeline is unchanged. `stitch_agent` and `stitch_skill` are already host-agnostic.

---

## Decision 1: Detection marker — `~/.gemini/antigravity-cli/`

**Options considered:**
- `~/.gemini/` — too broad; Gemini CLI, Gemini API SDK, and other Google tooling all create `~/.gemini/`
- `~/.gemini/antigravity-cli/` — specific to the `agy` installer; low false-positive risk
- Check for `agy` binary in PATH — fragile on systems where PATH differs per shell

**Decision:** Use `~/.gemini/antigravity-cli/` as the single detection marker. The `agy` installer creates this directory. If Antigravity changes its install location in a future release, the marker path in `detect.py` is the only place to update.

---

## Decision 2: Install paths

| What | Path | Rationale |
|---|---|---|
| Agents | `~/.gemini/antigravity-cli/agents/` | Mirrors `agy`'s global agent discovery path (analogous to `~/.claude/agents/`) |
| Skills | `~/.gemini/antigravity-cli/skills/` | Confirmed from Antigravity docs/research; nested `<skill>/SKILL.md` structure |
| Templates | `~/.gemini/antigravity-cli/plugins/pathly/templates/` | Follows the `<host>/plugins/pathly/` convention used by the claude and codex adapters |

**Open question:** Verify agent path from `agy --help` or docs. If `agy` reads agents from a different location (e.g. `~/.agents/` globally), update `install.yaml` before Conv 2.

---

## Decision 3: Skill YAML content — copy from claude adapter

Skill YAML files for antigravity are byte-for-byte copies of the claude adapter's skill YAMLs. The `stitch_skill` function generates the frontmatter; the body comes from `core/skills/`. No Antigravity-specific skill content is needed for v1.

**Rationale:** Skill content (the SKILL.md body) is host-neutral — it's instructions for the AI, not format metadata. The only host-specific piece is the frontmatter injected by `stitch_skill`, which is controlled by the `host_instructions` field in `install.yaml`. Since Antigravity doesn't have a documented `host_instructions` equivalent for v1, we omit it (matching the claude adapter, which also omits it).

---

## Decision 4: No plugin registration in v1

Codex requires a `codex_plugin_config.py` step to register a local marketplace and enable the Pathly plugin. Antigravity has a plugin system but the registration mechanism is not yet fully documented in public-facing sources.

**Decision:** Ship v1 without plugin registration. Users get agents and skills deployed; the plugin marketplace (for in-app discoverability) is a follow-up. A TODO comment in `README.md` tracks this gap.

**Follow-up scope:** Once Antigravity plugin registration is documented, add `antigravity_plugin_config.py` and a `plugin:` block in `install.yaml` — same pattern as codex.

---

## Decision 5: Model name assignment

The claude adapter uses abstract names (`sonnet`, `opus`, `haiku`). The codex adapter uses OpenAI model names (`gpt-5.4`, `gpt-5.5`). The antigravity adapter will use actual Gemini model names because Antigravity does not abstract them.

**Placeholder mapping (to be verified during Phase 0):**

| Category | Roles | Placeholder |
|---|---|---|
| Pro-tier (high capability) | architect | `gemini-2.5-pro` |
| Flash-tier (standard) | builder, designer, director, explorer, planner, po, reviewer, tester, web-researcher | `gemini-2.5-flash` |
| Lite-tier (fast/cheap) | quick, scout | `gemini-2.5-flash` or lighter model |

**Constraint:** Builder must run `agy models list` in Phase 0 and replace placeholders with verified names before writing any YAML file. If `agy` is unavailable, document placeholders as TODOs in `README.md`.

---

## Adapter sync rule (from `src/pathly_data/CLAUDE.md`)

> Any change to a core agent or skill must be reflected in all three adapter `_meta/` directories.

After this feature ships, the rule extends to **four adapters**. Any future core change must be reflected in `claude/`, `codex/`, `copilot/`, and `antigravity/` `_meta/` directories.
