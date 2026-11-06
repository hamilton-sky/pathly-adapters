# Settle how the chief's folder-trust screen is handled and how far the hook secret reaches

Type: settle
Status: resolved
Blocked by: —
Test first: no
Level: 1

Two choices about opening a chief change what the person gets, so the person decides them
(build guide: "If the decision is truly the user's, ask"). Ticket 14 builds question 1's answer.
Tickets 15 and 18 build question 2's answer. Resolved by the brief's Decided line (below).

**Question 1, the trust screen (spike 19 part B, proposed item 4, "S4").** On the first open of
a folder claude had never trusted, claude showed its folder-trust screen, the pasted first prompt
and the person's Enter went to that screen, and the chief started with no instructions. Studio's
injector (`studio/src/main/ipc/terminal/promptInjector.ts`, `attachStartupHandling`) already
answers a trust screen with Enter for every interactive tab, but only when `TRUST_PROMPT_RE`
matches, and otherwise pastes blind after 5 seconds; the pattern does not match claude's current
wording ("Is this a project you created or one you trust?", "Yes, I trust this folder"), which
fits the lost paste (wording source: map Decisions so far, GitHub issue
anthropics/claude-code#40002).

- **A (recommended): Studio answers the screen, as it does today, and never pastes blind into a
  chief tab.** The pattern learns the current wording; a chief tab pastes only after claude's ready
  prompt, never on the 5-second fallback. The person sees no trust screen for a chief. Why: it is
  what Studio already does for every interactive tab, and a chief runs `--restricted` (project
  settings ignored) with `--strict-mcp-config` (no project MCP servers), so trusting the folder
  gives it nothing a trusted chief would not have.
- **B: the person answers the screen.** For a chief tab Studio never answers a trust screen; it
  waits for the person's answer and pastes after claude's ready prompt follows. The person answers
  once per never-trusted folder.
- **C: the server pre-accepts the folder** by writing
  `projects["<repo root>"].hasTrustDialogAccepted = true` into the person's `~/.claude.json`
  before opening (docs: https://code.claude.com/docs/en/permissions, "Project allow rules and
  workspace trust"). Not recommended: Pathly would write the person's claude config,
  a file every running claude rewrites, so a concurrent write can lose either side's change.

**Question 2, the hook secret's reach.** No way exists on one user account, without OS isolation
(a second uid, a container, a sandbox), to keep a secret from another process of the same user:
on Linux a same-uid process may read `/proc/<pid>/environ` of another, which Yama's ptrace scope
does not restrict (map Decisions so far). So round two plans the strongest measurable
mitigation (tickets 15 and 18): no file holds the secret; the server keeps it in memory until Studio's main process claims it
once and puts it only in the chief claude's environment. What the person chooses is what a second
claim does:

- **A (recommended): a second claim closes the chief.** A process that races Studio for the claim
  leaves a closed chief (the person opens it again), never an open chief whose secret another
  process holds.
- **B: a second claim is refused and the chief stays open.** The person is never interrupted, but
  a process that claimed first holds a working secret for an open chief.

Either way the plan says plainly, in `src/pathly_orchestrator/CLAUDE.md` and the launcher's text,
that while the chief runs a same-user process can still read the chief's environment, and that a
**codex chief** has no hook and no secret, while its `--sandbox read-only` still reads the whole
file system (other processes' `/proc/<pid>/environ`, and so headless agents' live
`PATHLY_RUN_TOKEN`s): Pathly cannot promise it stays inside its project. Isolating headless agents
under another uid or a sandbox would give real secrecy; it is platform work for a later round, not
this one.

## Not in this ticket

- Building either answer: tickets 14 (trust screen), 15 and 18 (hook secret).

## Done when

- The Answer names the choice for question 1 (A, B or C) and for question 2 (A or B), and who
  chose them.

## Reference

- `pathly/features/chief-agent/spike19-part-b-report.md` § Surprises, § Proposed tickets, read-only
- map.md § Decisions so far (the outside facts and their sources)

## Answer

Decided in the brief (`Decided (recommended answers, approved by the person 2026-11-06)`), recorded
by the planner on 2026-11-06:

- **Question 1 = A**: Studio answers a chief tab's folder-trust screen, as it does for every
  interactive tab, and never pastes blind into a chief tab: the first prompt is pasted only after
  claude's ready prompt. B (the person answers) and C (the server writes `~/.claude.json`) are not
  built.
- **Question 2 = A**: a second claim of the hook secret closes the chief (`close_chief(run_id,
  "hook secret claimed twice")`); B (refuse and keep it open) is not built.
- Chosen by: the user, through the brief's Decided line (the recommended answers, pending their
  tap). If the tap differs, this ticket reopens and tickets 14, 15 and 18 are planned again.
