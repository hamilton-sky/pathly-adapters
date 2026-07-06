# Board Evaluation — Code-Intel / GitNexus Removal

_Evaluated: 2026-07-06 by evaluator agent_

## Classification
CODE (DONE — no implementation tasks remain)

## Summary

The code-intel initiative is fully shipped to master and GitNexus has been completely removed
from all live code. `codebase-memory-mcp` is the sole code-graph engine at every layer: the
Python backend (`runner/code_context.py` + `code_context_cli.py`), the Studio settings hook
(`useCodeContextSettings.ts`), and all 11 agent `.md` + YAML configs. The three now-archived
plan folders (`gitnexus-integration/`, `code-intel-proxy/`, `code-context-injection/`) were
moved to `pathly/features/.archive/`; their former `pathly/plans/` paths no longer exist.
The board's artifact catalog still holds three stale entries pointing to those gone paths.

## What is done

| Layer | Status |
|---|---|
| `runner/code_context.py` — `_resolve_tool()` | Returns `"codebase-memory-mcp"` only; gitnexus removed |
| `runner/code_context_cli.py` — `CliProvider` | Queries codebase-memory-mcp via `list_projects` + `query_graph` Cypher |
| `studio/…/useCodeContextSettings.ts` | `CodeContextTool = 'codebase-memory-mcp'` only; `parseTool` maps any legacy value to it |
| `blueprints/code/query.py` | Clean; no gitnexus refs; role-tiered gateway |
| Agent `.md` + YAML tool-lists | `mcp__codebase-memory-mcp__*` everywhere; `mcp__gitnexus__*` zero refs |
| `_mcp/gitnexus.json` | Removed from all 4 adapters; `codebase-memory-mcp.json` in place |
| `core/skills/fragments/code-query.md` | Wired into `development/execute-task` (loop) + `development/drain-dag` (single) |
| `pathly/plans/gitnexus-integration/` | Archived to `pathly/features/.archive/gitnexus-integration/` |
| `pathly/plans/code-intel-proxy/` | Archived to `pathly/features/.archive/code-intel-proxy/` |
| `pathly/plans/code-context-injection/` | Archived to `pathly/features/.archive/code-context-injection/` |

## Key unknown / risk

The `codebase-memory-mcp` binary is NOT on this box's PATH (it was validated from a scratchpad
copy only). The backend is wired and returns `null` gracefully (agents fall back to Grep), but
live code-structure data requires `codebase-memory-mcp install` on PATH then re-index.

## Stale board artifacts (cleanup needed)

The project board catalog has three entries pointing to paths that no longer exist:
- `pathly/plans/gitnexus-integration/APPROACH.md` → now at `.archive/`
- `pathly/plans/code-intel-proxy/APPROACH.md` → now at `.archive/`
- `pathly/plans/code-context-injection/APPROACH.md` → now at `.archive/`

These are cosmetic catalog orphans — they don't break anything, but they mislead agents that
query the catalog. The archived files remain readable at their `.archive/` paths.

## SEQUENCING.md note

`pathly/project/SEQUENCING.md` was written 2026-06-28 as a point-in-time decision record for
a now-fully-executed sequencing. It references gitnexus as the prerequisite, which is
historically accurate. It should be treated as an archived record — do not sync it to current
code. The actual execution deviated from it (gitnexus replaced by codebase-memory-mcp) and
that deviation is recorded in the memory at `memory/project_code_intel_initiative.md`.

## Recommended next steps

- Install `codebase-memory-mcp` binary on PATH (`codebase-memory-mcp install`) for live data
- Run `codebase-memory-mcp cli index_repository {"repo_path": "C:/Users/Yafit/pathly-adapters"}` to index the repo
- (Optional) Supersede or delete the three stale catalog entries on the project board
- No code changes needed — the removal is complete
