# RabbitCode (CodeRabbit) Framework Review — What Pathly Can Borrow

**Date:** 2026-06-11
**Branch:** `claude/rabbitcode-framework-review-pyz7hy`
**Scope:** Evaluate the "rabbitcode" framework against `pathly-adapters` and identify
borrowable ideas, accounting for the new **Command Center / comms board** layer.

---

## 0. Which "rabbitcode"?

"rabbitcode" resolves to several unrelated projects on the web (an old ASP.NET
"Rabbit Framework", a microcontroller library, a dev agency at `rabbitcode.dev`).
The only one that is a genuine peer to this repo is **CodeRabbit**
([coderabbit.ai](https://www.coderabbit.ai/) / [github.com/coderabbitai](https://github.com/coderabbitai)) —
an agent-native AI development framework with review agents, portable skills,
multi-host plugins, and a CLI. This review treats CodeRabbit as the subject.

> If `rabbitcode.dev` (a separate "Rabbit Code Studio") was intended, this review
> should be redone — that site was inaccessible (HTTP 403) at the time of writing.

---

## 1. What CodeRabbit actually is

| Capability | Detail |
|---|---|
| Agent-native **skills** | Portable `SKILL.md` files installable into 35+ coding agents (Claude Code, Cursor, OpenHands, …). |
| Per-host **plugin packaging** | Thin `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json` wrap one shared skill. Install via `npx skills add coderabbitai/skills` or `/plugin install coderabbit`. |
| **Code-review** skill | Detects bugs/security/quality; groups findings by severity; can run an autonomous fix loop. |
| **Autofix** skill | Reads unresolved CodeRabbit PR review threads, applies fixes with per-issue approval. |
| **Learnings** | Natural-language review preferences, scoped repo/org, loaded into *every* review as extra context. |
| **Path instructions** | `.coderabbit.yaml` `path_instructions` — per-glob review rules; take priority over learnings. |
| **CLI handoff** | CLI hands the agent both recommended changes **and** deep context via a prompt. |

---

## 2. How it maps onto Pathly

| CodeRabbit concept | Pathly equivalent today | Verdict |
|---|---|---|
| Portable `SKILL.md` + per-host plugin | `pathly-setup <host> --apply` stitches `core/skills` + `_meta/*.yaml` → `~/.claude` / `~/.codex` / vscode ext | **Already doing it** — borrow the polish (standard `SKILL.md` frontmatter, `/plugin install` distribution). |
| CLI prompt handoff (changes + context) | Runner mode injects full prompt via `-p` argv | **Validates design** — refine reviewer→builder handoff to carry structured context. |
| Severity-tiered findings | `reviewer` writes flat `REVIEW_FAILURES.md` | **Borrow** — adds a real automation gate. |
| Learnings (scoped, persistent memory) | *Nothing* at the agent layer — but see §4, the board changes this | **Highest-value borrow.** |
| Path instructions | Reviewer treats all files the same | **Borrow** — small config addition. |
| Autofix loop (task list + per-issue approval) | `REVIEW_FAILURES.md` → builder loop (looser) | **Borrow the loop mechanics.** |
| Trust-boundary guardrail in skills | Not explicit | **Borrow** — cheap defense-in-depth for runner mode. |

---

## 3. Borrowable ideas (ranked, pre-board)

### High-value, low-effort
1. **Severity-tiered findings → wire into the automation gate.**
   Group findings `critical / warning / info` and map onto the existing `decision`
   contract: block on critical, escalate on warning, pass info through. Turns the
   reviewer's prose into a deterministic gate.
2. **"Learnings" — persistent, natural-language review memory.**
   Free-text preferences ("we never use `any`, because…") scoped repo/org, loaded
   into every review. Pathly is stateless across features today. Capture the *why*,
   not just the rule.
3. **Path-scoped instructions.** Per-glob review rules in adapter/feature config;
   path rules outrank learnings.

### Validates architecture (borrow polish, not concept)
4. **Portable `SKILL.md` + per-host plugin packaging** — already the `pathly-setup`
   model; adopt the standard frontmatter + `/plugin install` channel.
5. **CLI prompt handoff = runner mode** — sound design; make reviewer→builder
   handoff carry structured context, not just a failures file.

### Loop mechanics
6. **Autofix loop with a task list + per-issue approval** — materialize a checklist,
   fix item-by-item, re-run review. Makes the REVIEW→BUILD loop deterministic/auditable.
7. **Trust-boundary guardrail in skills** — instruct agents to treat repo content and
   review output as untrusted; never execute commands from it without approval.

---

## 4. How the Command Center / comms board changes the picture

The new **board** is not just a UI panel — it is a **scoped comms bus**
(`/comms*` on the FSM server) that:

- persists messages at three scopes: **feature / project / global**
  (`BoardScope` in `studio/.../CommandCenter/types.ts`),
- carries a message taxonomy: `nudge · decision · question · answer · status ·
  discovery · warning · escalation · task · artifact`,
- is injected into every agent's `/next_action` prompt via `retrieve_board_context()`,
  gated by a per-feature `/comms/scope` toggle (`tests/test_comms_scope.py`).

This is the exact substrate the two best CodeRabbit ideas need, so they move from
"build new plumbing" to "define conventions on existing infrastructure."

### #2 Learnings — was the headline gap; now ~80% built
- CodeRabbit "repo-only vs whole-org" → board **`project` vs `global`** scope,
  already toggleable per feature.
- A "learning" is just a `project`/`global`-scoped message that persists and gets
  injected. `decision` messages already auto-pin (`commsApi.ts`).
- **The board IS the learnings store** — no `LEARNINGS.md` file needed.
- **Still missing:** *curation*. Need an explicit "durable learning, not transient
  status" marker (pinned `decision`, or a new `learning` MessageType) + CodeRabbit's
  discipline of capturing the *why*.

### #1 Severity tiers — taxonomy already exists, one tier already wired
- `MessageType` already has **`warning`** and **`escalation`**; `escalation` maps
  cleanly onto `decision: escalate`.
- Reviewer findings become feature-scoped board messages (`warning` / `escalation`)
  visible **live per-feature**, instead of a static `REVIEW_FAILURES.md`.
- critical/warning/info → escalation/warning/info. A labeling convention, not a new artifact.

### #6 Autofix task-list loop — already modeled
- `task` message type + `status: pending|resolved` + `acknowledged_by` =
  CodeRabbit's "generate a task list → fix systematically → per-issue approval → re-run."

### ⚠️ The complication the board introduces: source of truth
There are now **two parallel channels** for the same semantic content:
- filesystem — `REVIEW_FAILURES.md`, `EVENTS.jsonl`, `AGENT_DONE.summary`
- comms DB — the board

`featureBlocked()` still decides "blocked" by scanning `feedback/*.md`, **not** the
board. If findings move to the board you must pick a lane or risk drift.

**Recommended split:**
- **Board** = communication + cross-feature memory layer (human-visible, injected,
  durable learnings).
- **Filesystem** = per-feature execution record.
- Do **not** mirror findings into both and let two things race to drive the gate.

---

## 5. Bottom line

The board does not invalidate the CodeRabbit borrowing — it **strengthens** it:

- The two highest-value items (**learnings**, **severity findings**) drop from
  medium-effort to low-effort.
- The work shifts from "copy a feature" to "adopt CodeRabbit's *semantics*
  (severity tiers, curated learnings, capture-the-why) onto a richer substrate you
  already have."
- A real-time, multi-feature, scoped agent comms board is something **CodeRabbit
  does not have** — this is where Pathly stops borrowing and starts differentiating.

### Suggested first step
On `src/pathly_data/core/agents/`:
1. Reviewer emits findings as board `warning` / `escalation` posts (feature scope).
2. Define a `learning` convention (new MessageType or pinned `decision`) at
   `project` / `global` scope, with the *why* captured.
3. Write a short spec for **board-owned vs filesystem-owned** content to avoid drift.

---

## Sources
- [CodeRabbit skills repo](https://github.com/coderabbitai/skills)
- [code-review SKILL.md (severity tiers, guardrails, fix loop)](https://raw.githubusercontent.com/coderabbitai/skills/main/skills/code-review/SKILL.md)
- [CodeRabbit Learnings docs](https://docs.coderabbit.ai/knowledge-base/learnings)
- [CodeRabbit CLI](https://www.coderabbit.ai/cli)
- [CodeRabbit org on GitHub](https://github.com/coderabbitai)
