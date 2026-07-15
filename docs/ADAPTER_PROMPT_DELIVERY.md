# Adapter Prompt Delivery (Headless) — Channels, the Windows Command-Line Limit, and the Antigravity Constraint

> **One-line thesis:** a headless CLI engine can only receive a large composed prompt if the
> prompt can travel **off the command line** (stdin or a file). `claude` and `codex` can; the
> Antigravity CLI (`agy`) cannot — so on Windows it is a **small-prompt-only** engine until Google
> adds a stdio/file input channel upstream.

This is a reference spec for how Pathly hands a composed prompt to each CLI adapter in **runner
(headless) mode**, why one adapter is constrained where the others are not, how Pathly guards
against the resulting failure modes, and the upstream fix paths. It complements
[MULTI_TOOL_DESIGN.md](MULTI_TOOL_DESIGN.md) (adapter structure) and the spawn-scheduler section of
[../studio/CLAUDE.md](../studio/CLAUDE.md).

---

## 1. Background — how a composed prompt reaches a CLI

In runner mode Pathly composes the full prompt in Python (skill body + board context + task) and
Studio spawns the engine as a PTY (`node-pty`). The engine's `headless` argv template
(`adapters.yaml`) has a `{prompt}` slot, e.g.:

```
claude: ['claude', '-p', '{prompt}', '--model', '{model}', '--output-format', 'json', '--dangerously-skip-permissions']
codex:  ['codex', 'exec', '--json', '--sandbox', 'workspace-write', '--model', '{model}', '--', '{prompt}']
agy:    ['agy', '-p', '{prompt}']
```

A composed prompt is large — a skill body alone is ~17 KB, plus board context and the task text.
The question is whether `{prompt}` stays on the **command line** or is moved onto **stdin**.

### The hard limit

On Windows, `CreateProcess` caps the entire command line at **32,767 characters** (the
`UNICODE_STRING` limit). Worse, if the launcher resolves to a `.cmd`/`.bat` shim, the effective
cap drops to **8,192 characters** (cmd.exe's own limit), and cmd's batch parser additionally
**truncates any argument at the first newline**. So a multi-KB, multi-line prompt passed as an
argv element is not merely risky on Windows — it is structurally impossible past the cap.

The escape hatch is to keep the prompt **off the command line**: pipe it via **stdin**. Studio does
exactly this in `resolveRunnerShell` (`studio/src/main/ipc/terminal.ts`): on Windows it writes a
UTF-8 BOM `.ps1` temp script (the `-EncodedCommand` base64 path has the same ~32 KB limit) and, for
engines that can read stdin, pipes the prompt in as a here-string instead of placing it on the
command line.

---

## 2. Adapter capability matrix

| Adapter | Prompt input channels | Big-prompt (headless) path | Windows gotcha |
|---|---|---|---|
| **claude** | `-p` arg **or stdin** | `$prompt \| claude -p` — `-p` reads stdin when its value is omitted (10 MB cap, v2.1.128) | none once piped |
| **codex** | arg, **`codex exec -`** (stdin = prompt), or arg+stdin (stdin appended as context) | pipe prompt to `exec -` | `codex exec` **hangs** if stdin is a non-TTY pipe with no writer ([openai/codex#20919](https://github.com/openai/codex/issues/20919)) → close stdin with `< NUL` / `$null \|` |
| **agy** | **`-p`/`--print` arg only** (also `-i/--prompt-interactive`) | **none — no stdin / `--prompt-file` / `@file` channel** | 32 KB command-line wall + non-TTY stdout drop + `.cmd` newline-shred |

Verified against: [Claude Code headless docs](https://code.claude.com/docs/en/headless),
[Codex non-interactive docs](https://developers.openai.com/codex/noninteractive), and the
[agy v1.0.16 command cheat sheet](https://toolsbase.dev/en/reference/antigravity-cli-commands)
(July 2, 2026, cross-checked against official docs + GitHub releases).

> **Correction of a common myth:** some web summaries claim `agy` supports `--prompt-file`. It does
> **not** (v1.0.16). The only prompt flags are `-p/--print` and `-i/--prompt-interactive`. Do not
> build on a `--prompt-file` that doesn't exist.

---

## 3. The three *distinct* agy failure modes

These are separate problems that get conflated; each needs its own reasoning.

1. **Command-line length overflow — the big-prompt killer.** The prompt can only be an argument, so a
   composed prompt exceeds the 32,767-char (`.exe`) / 8,192-char (`.cmd`) command-line limit and the
   process fails to launch ("command line is too long"). **Unfixable client-side** — a temp-script
   wrapper does not help, because whatever line finally runs `agy -p <prompt>` still hands the huge
   argument to `CreateProcess`.

2. **Non-TTY stdout drop — the "succeeded but did nothing" trap.** `agy --print` detects whether
   stdout is a real terminal and, when it is not (pipe / subprocess / redirect), emits **no output
   while still exiting 0** (upstream issue #76). The fix is a **pseudo-TTY**: `script -qec` on Linux,
   or **node-pty/ConPTY on Windows** — which Studio already uses, so this mode is covered for the
   small editor actions.

3. **`.cmd` shim newline-shred — Windows-specific.** When the launcher resolves to `agy.cmd` (a
   cmd.exe batch shim) instead of `agy.exe`, cmd's batch parser truncates a multi-line argument at
   the first newline; the escaped remainder makes cmd print "The system cannot find the path
   specified" while still exiting 0 — a silent false success.

> The July 2026 diagram-run failure hit **#2 + #3 together**: the resolver fell back to `agy.cmd`
> (during an agy self-update rename window, since `agy.exe` is preferred), the multi-line prompt was
> shredded, and Studio recorded a 1.5-second success with no output.

---

## 4. How Pathly handles it today

| Guardrail | Where | Effect |
|---|---|---|
| **stdin piping for claude/codex** | `resolveRunnerShell` (terminal.ts) | large prompts bypass the command-line limit entirely |
| **`$null` stdin for codex** | `resolveRunnerShell` | prevents the non-TTY `codex exec` hang (#20919) |
| **prefer `agy.exe` over `agy.cmd`** | `resolveEnginePath` (terminal.ts) | avoids the batch-shim shred whenever the native binary exists |
| **batch-shim guard** | `resolveRunnerShell` (terminal.ts) | a `.cmd`/`.bat` launcher + a multi-line arg → pipe (claude/codex) or **throw** (agy), instead of a silent exit-0 |
| **node-pty / ConPTY spawn** | terminal.ts PTY spawn | pseudo-TTY, so agy's non-TTY stdout drop does not bite small editor actions |
| **agy disabled for per-task/board/team** | task Run picker + adapter routing | large composed prompts never route to agy |
| **dash-safety** | `_dash_safe_prompt` (adapters.py), `dashSafePrompt` (cliEngine.ts), `_strip_leading_frontmatter` (compose.py) | a prompt never starts with `-`/`---` (would be parsed as a bad option) |

**Net posture:** `agy` is a **small-prompt-only** engine on Windows — fine for the editor
micro-actions (Split / Analyze / comments / diagrams) that fit under ~8 KB and spawn through
node-pty, disabled for anything that carries a full composed prompt.

---

## 5. Fix paths (upstream — the real solutions)

Both live on [`google-antigravity/antigravity-cli`](https://github.com/google-antigravity/antigravity-cli).

### 5a. ACP stdio mode — strategic

[Issue #31](https://github.com/google-antigravity/antigravity-cli/issues/31) (open) requests an
`--acp` flag running `agy` as a JSON-RPC-2.0-over-stdio agent server (`initialize` / `session/new` /
`session/prompt` / streaming). The prompt would arrive as a `session/prompt` message over **stdin**,
so the command-line limit vanishes — and structured stdout also resolves the non-TTY drop. This is
the standard that claude/codex/Zed/Cursor orchestration is converging on. Bigger lift for Google →
slower to land. Pathly's move: a supporting comment with the concrete Windows use case.

### 5b. `--prompt-file` / stdin — tactical

No such issue exists yet. A narrow request: `agy -p --prompt-file <path>` or `cat prompt.md | agy -p -`
(dash = read prompt from stdin), matching `claude -p` (stdin) and `codex exec -` (stdin). Tiny
surface area, trivial to implement, does not touch the TUI — **far more likely to ship soon** than
full ACP, and it is the one that realistically unblocks Pathly on Windows. (It does not fix the
non-TTY stdout drop, but node-pty already covers that for us.)

**Recommendation:** pursue both — they are complementary and hedge on whichever Google ships first.
Whichever lands, Pathly re-enables agy for headless composed prompts by piping the prompt via the
new channel in `resolveRunnerShell` (same shape as the claude/codex stdin path).

---

## 6. References

- [Antigravity CLI — headless / non-TTY stdout problem](https://antigravitylab.net/en/articles/integrations/antigravity-cli-agy-headless-non-tty-stdout-ci)
- [agy v1.0.16 command cheat sheet](https://toolsbase.dev/en/reference/antigravity-cli-commands)
- [Antigravity CLI docs](https://antigravity.google/docs/cli-using)
- [ACP feature request — antigravity-cli#31](https://github.com/google-antigravity/antigravity-cli/issues/31)
- [Claude Code headless docs](https://code.claude.com/docs/en/headless)
- [Codex non-interactive docs](https://developers.openai.com/codex/noninteractive) · [codex exec stdin non-TTY hang #20919](https://github.com/openai/codex/issues/20919)
- [Windows command-line length limit — Raymond Chen, "The Old New Thing"](https://devblogs.microsoft.com/oldnewthing/20031210-00/?p=41553)
