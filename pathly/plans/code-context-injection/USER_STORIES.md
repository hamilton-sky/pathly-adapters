# User Stories — code-context-injection (Approach B)

Approach B of the MCP-delivery fork: Pathly injects code-structure context into runner-mode
prompts itself, host-agnostic. See `APPROACH.md`. Complements (does not replace) the host-MCP
Approach A in gitnexus-integration / lsp-integration.

---

## Story 1 — Provider interface + safe-off default

**Who:** Maintainer wiring Pathly-native code context.
**What:** A `CodeContextProvider` interface in `runner/code_context.py` with a `none` backend that
returns `""`, plus a `build_block(...)` entry point that selects the configured backend.
**Why:** Pathly must ship safe-off — the feature can be present and disabled, and must never break
a prompt.

**Acceptance criteria:**
- `src/pathly_orchestrator/runner/code_context.py` exists with a `build_block(scope, files, role,
  token_budget) -> str` function and a `CodeContextProvider` abstraction.
- The default backend is `none`; `build_block` returns `""` when backend is `none` or unset.
- `build_block` **never raises** — any backend error is caught and yields `""` (the "never break
  the prompt" idiom from the context-retrieval spec, F9).
- The module imports nothing from `supervisor/` or `http_server/` (layer rule).

---

## Story 2 — A working backend returns blast-radius / callers for in-scope files

**Who:** Developer running a runner-mode build/review task with a code-intel tool installed.
**What:** A `cli` backend queries the configured tool (gitnexus impact or serena
`find_referencing_symbols`) for the files in scope and returns a structured result.
**Why:** This is the actual code awareness — the callers/blast-radius the agent needs.

**Acceptance criteria:**
- A `cli` backend shells out to the configured tool and parses its output into a list of
  `{symbol/file, callers/impacted}` entries.
- If the tool binary is missing or errors, the backend returns empty (→ `build_block` yields `""`),
  no crash.
- Given a known symbol in this repo, the backend returns at least its real referencing sites.

---

## Story 3 — The 🧭 advisory channel is injected into runner-mode prompts

**Who:** A builder/reviewer/explorer agent spawned by the runner.
**What:** When a task has files in scope, the assembled prompt gains a token-budgeted
`🧭 Code structure (advisory — verify before acting)` block with the backend's result.
**Why:** Guarantees the structural context is present regardless of whether the agent would have
called a tool — the determinism Approach A can't provide.

**Acceptance criteria:**
- The runner prompt-assembly call site calls `build_block(...)` and appends the returned block to
  the agent prompt (only when non-empty).
- The block is clearly labeled advisory ("verify before acting"), parallel to the 💡 board channel.
- The block respects a token budget (mirrors `comms_context.py` `k`-caps); oversized results are
  truncated/summarized, not injected whole.
- With backend `off`, no block appears and the prompt is byte-identical to today.

---

## Story 4 — Content-hash caching + staleness

**Who:** Developer running several tasks over the same files.
**What:** Backend results are cached keyed by `(path, content-hash)`; unchanged files reuse the
cache, changed files re-query.
**Why:** Avoid re-paying query cost per task; keep results correct after edits.

**Acceptance criteria:**
- A second `build_block` over unchanged files does not re-invoke the backend (cache hit).
- Editing a file changes its content-hash and forces a re-query for that file only.
- Cache is bounded (no unbounded growth across a long run).

---

## Story 5 — Backend config switch wired into the install/export choice flow

**Who:** User installing/configuring Pathly.
**What:** A setting (`code_context.backend = off|cli|mcp`, `code_context.tool = gitnexus|serena`)
is exposed in the same install/export selection that already chooses adapters, with an
Off / Host-MCP (A) / Pathly-native (B) / Both choice.
**Why:** One coherent place for the user to pick how code intelligence is delivered.

**Acceptance criteria:**
- The setting is readable by `runner/code_context.py` to select the backend.
- The install flow presents the A/B/Both/Off choice and writes the corresponding config
  (host-MCP install for A, `code_context.backend` for B).
- Default is Off (no behavior change for existing installs).

---

## Story 6 — Host-agnostic proof on a non-MCP host

**Who:** Developer on a host without MCP support (e.g. antigravity).
**What:** A runner-mode task on that host still receives the 🧭 structural context via Approach B.
**Why:** Demonstrates the core advantage over Approach A — no host MCP support required.

**Acceptance criteria:**
- With Approach A unavailable (no host MCP) and backend `cli`, a runner task on the target host
  produces a prompt containing the 🧭 block.
- The run completes normally; removing the backend (`off`) cleanly drops the block with no error.
