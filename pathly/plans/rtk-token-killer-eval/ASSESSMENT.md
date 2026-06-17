# RTK (Rust Token Killer) — Integration Assessment for Pathly

**Status:** Evaluation · not approved for build
**Date:** 2026-06-16
**Author:** hamilton (with Claude Code)
**Repo under review:** [github.com/rtk-ai/rtk](https://github.com/rtk-ai/rtk) — Apache 2.0, single Rust binary, v0.28.x

---

## TL;DR / Verdict

**Do not bundle RTK into Pathly yet.** Run a one-off WSL2 trial against a real
feature run, read the `tokens_in` / `cost_usd` deltas from our own
`BILLING_UPDATE` events, and decide from numbers — not the vendor's "60–90%"
headline.

- **Native Windows (our primary env):** ❌ auto-rewrite hook does not fire → degraded mode.
- **WSL2 personal use:** 🟡 ~10-min trial, low risk, fast signal.
- **Bundle into `pathly-setup` for end-users:** ❌ not yet — needs a fidelity gate + per-OS binary distribution story first.

---

## What RTK is

A CLI proxy that intercepts common dev commands (`git`, test runners, linters,
`ls`/`cat`/`grep`, `docker`/`kubectl`, …) and **compresses their output before it
re-enters the model's context window**, claiming 60–90% token reduction. It wires
into agents via a **PreToolUse hook** that transparently rewrites
`git status` → `rtk git status`. Single Rust binary, zero runtime deps,
optional telemetry off by default.

Sibling projects in the same org (`rtk-ai/icm` memory, `rtk-ai/vox` STT/TTS) — not in scope here.

---

## How tokens are billed in Pathly (verified)

`src/pathly_hooks/stop_telemetry.py:109` records **both** sides — Pathly's cost
number is the full bill, not output-only:

```python
tokens_in  = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
tokens_out = output_tokens
cost_usd   = total_cost_usd or cost_usd or totalCostUsd or 0.0   # provider-reported total
```

`BILLING_UPDATE` stores `tokens_in`, `tokens_out`, `total_tokens`, `cost_usd`.

### Where RTK actually lands

In an agent loop, **input** = system prompt + Pathly's injected `-p` prompt +
history + **tool results (command output fed back)**. RTK only shrinks the last
slice:

| Slice of input | What it is | RTK compresses? | Price |
|---|---|---|---|
| Prompt share | Pathly role contracts + artifacts injected via `-p` | ❌ No | usually **cached** → cheap (cache_read) |
| Tool-result share | git/test/build/lint output read back into context | ✅ **Yes** (Bash only) | **uncached, full price** |
| Output share | model's generated text | ❌ No | full price |

**Takeaway:** RTK targets the *uncached, full-price* tool-result slice — the right
slice to cut. But it's narrow, and it only fires on the `Bash` tool.

---

## Fit analysis

### Alignment (why it's tempting)
- **Pathly burns tokens at scale.** Runner spawns a PTY-per-stage, each running
  `claude -p` (director → architect → builder → reviewer → tester …). We already
  track cost via `BILLING_UPDATE` patching `AGENT_DONE`.
- **Hook machinery already exists.** We ship a Stop hook (`stop_telemetry.py`);
  `pathly-setup claude --apply` already stitches hooks into `~/.claude`. Adding a
  PreToolUse hook is the same mechanism.
- **Adapter overlap.** RTK supports Claude Code, Codex, Copilot, Antigravity —
  the same four adapters Pathly installs to.

### Caveats (ordered by impact)
1. **🔴 Native Windows = degraded.** Auto-rewrite hook does not run on native
   Windows; falls back to "CLAUDE.md injection mode" requiring explicit `rtk`
   prefixes. Full benefit needs **WSL2** (same constraint we noted for Cursor).
2. **🟡 Bash-tool only.** `Read` / `Grep` / `Glob` (Claude Code built-ins) bypass
   RTK — and our agents use them heavily. Real-world savings < headline.
3. **🟡 Fidelity risk.** RTK compresses test/lint/git output that `reviewer` and
   `tester` reason over → REVIEW_FAILURES.md / TEST_FAILURES.md. Lossy compression
   could hide a failure detail. It has a "tee recovery" fallback (re-read full
   output) — must be validated before trusting in the runner path.
4. **🟢 Supply-chain/trust.** Apache 2.0, open source, telemetry opt-in/off by
   default, high adoption. A hook that rewrites *every* Bash command is a powerful
   interception point — vet the binary before bundling for end-users.

RTK should **not** touch our JSON IPC (`--output-format=json` stdout for
`session_id` / `cost_usd`, or `EVENTS.jsonl`) since those aren't Bash-tool calls —
**verify** this assumption during the trial.

---

## Recommendation (what / why / how)

**What:** Don't build. Run a WSL2 trial for personal dev sessions, then decide.

**Why:** RTK targets a genuinely full-price slice of the bill, but only Bash
output, and native Windows kills the auto-rewrite. Savings are real but narrow and
unproven on *our* workload — not worth a feature build on faith.

**How:** see the trial below. Decide on measured deltas.

### Parallel, higher-leverage move (independent of RTK)
Trim the injected `-p` prompts — dedupe artifacts, cache stable role text. That hits
a bigger slice than RTK can reach (the prompt share), and we control it entirely.

---

## Go / No-Go trial (WSL2)

1. In WSL2, install rtk; run `rtk init -g` against a **throwaway** Claude config
   (do not point it at the real `~/.claude` yet).
2. Pick one representative feature; run it end-to-end **twice**: once baseline
   (no RTK), once with RTK.
3. Compare `tokens_in` and `cost_usd` across the two runs' `BILLING_UPDATE`
   events (per-stage and total).
4. Spot-check: did any `reviewer` / `tester` stage lose a failure detail vs
   baseline? Did JSON IPC (`session_id`, `cost_usd`, `EVENTS.jsonl`) stay intact?

### Decision rule
- **≥ 20% `tokens_in` drop AND no fidelity regression** → open a real plan folder
  to integrate into `pathly-setup` (per-OS binary distribution + fidelity gate).
- **10–20%** → keep as an optional, documented power-user add-on; don't bundle.
- **< 10%, or any fidelity regression** → drop it.

---

## Open questions for integration (only if trial passes)
- Per-OS binary distribution inside the install flow (Rust binary, not pip/npm).
- `rtk init --agent <x>` wired into each adapter's `--apply` step.
- Fidelity gate so compression never eats a reviewer/tester failure detail.
- Graceful fallback when the binary is absent (never block the pipeline).

---

## Sources
- [rtk-ai/rtk](https://github.com/rtk-ai/rtk)
- [rtk-ai org](https://github.com/rtk-ai)
- Internal: `src/pathly_hooks/stop_telemetry.py`, CLAUDE.md (pipeline + telemetry sections)
