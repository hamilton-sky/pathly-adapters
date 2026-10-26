# Spike: what does daycap's guard actually cover over Pathly spawns?

Type: task
Status: resolved
Blocked by: 21
Test first: no (spike; the finding is the deliverable)

daycap's `--guard` is a PreToolUse hook for interactive Claude Code / Codex
sessions: it reads the cached snapshot and can deny *tool calls inside a
session* (fail-open on stale/timeout; `src/bin/guard.js`, invariants 1-4).
The round-two draft `round-two-drafts/daycap-spend-report.md` (round-one
ticket 18 until 2026-10-14) wires daycap as a *reporting* source. This spike
stays in round one because it changes no code and blocks nothing. Before
anyone treats daycap
as an *enforcement* backstop for the fleet, this spike must answer one
question with a real run:

**Does the guard fire on Pathly's headless spawns?**

**Part A was not run.** On 2026-10-26 the person chose to run part B only and leave daycap
untouched. The Answer says part A is not measured and the guard question stays open; nobody may
treat daycap as a backstop for Pathly's spawns until a later spike measures it.

Pathly spawns `claude -p '{prompt}' --model ... --output-format json
--dangerously-skip-permissions` as a subprocess (see root `CLAUDE.md`,
Studio CLI spawn scheduler). Two sub-questions:

1. Does a headless `-p` session load the user's `settings.json` hooks at
   all (i.e. does the guard even get consulted)?
2. If it does, does `--dangerously-skip-permissions` bypass the PreToolUse
   decision (making the guard a no-op for exactly the spawns Pathly makes)?

One answer is already known: the guard does **not** run in the chief tab.
The chief starts with `--restricted` (or `--setting-sources` with
no sources), which ignores the user's `settings.json`, where daycap installs
its hook (spec.md § Decisions, "The chief's claude permissions"). Once
the chief can be opened, confirm it with the chief open and over
budget, and record it with the rest.

Procedure: install the daycap guard on the dev machine, set a tiny daily
budget, trigger it over budget, then run one headless spawn exactly as
`supervisor/terminal.py` builds it and observe whether the spawn or its
tool calls are denied. Record the exact CLI version — hook behavior is
version-sensitive. Also record what the over-budget spawn cost: a guard that
denies tool calls does not stop the model taking turns, so the spawn keeps
spending until it gives up.

## Outcome A: the guard fires on headless spawns

Then daycap is a fleet-wide brake and Pathly gets it for free. It is not a
kill switch: it denies tool calls, not tokens, so a denied spawn still spends
until it gives up (the cost recorded above says how much).

- Living doc: one paragraph in `src/pathly_orchestrator/CLAUDE.md`
  ("daycap is the machine-wide backstop; the chief's per-session ceilings are the
  Pathly-aware inner layer").
- Optional hardening (only if cheap): the supervisor reads the daycap
  snapshot before spawning and skips the spawn when over budget — fail open
  on stale/missing, so a daycap outage never wedges the fleet.
- The chief's text (the `chief-connect` fragment) may say
  "daycap can block agents' tool calls machine-wide when the daily budget is
  gone"

## Outcome B: the guard does not fire on headless spawns

Then the boundary is explicit and must be written down, not assumed:

- daycap covers the human's own **interactive** sessions. It does **not**
  cover Pathly's headless fleet, and it does not cover the chief tab, which
  loads no user settings. Putting the guard in the chief's own
  settings file would be a round-two decision.
- Headless enforcement stays Pathly-side: the chief's per-session ceilings
  (spec.md § Decisions, "Limits")
  plus the per-goal `cost_cap.py`. If a machine-wide daily stop for the
  fleet is wanted, it needs a Pathly-side daily accumulator (new ticket —
  do not bolt it onto this one).
- Record the boundary in the living doc and in `learnings.md` (one line,
  tagged with this ticket number), so nobody re-derives it in six months.

Either way, this ticket changes no enforcement code. Its deliverable is the
measured answer plus the doc line. Do not build Outcome A's optional
hardening inside this ticket.

## Part B: does a real chief session work the way the code says?

Added 2026-10-22 at the person's request (they chose to extend this spike). Every chief test uses a
fake spawn host. Nothing has yet run a real `claude` against what the chief depends on, and no other
ticket plans it. This part is one short live session in the same sitting as part A. Its deliverable is
a measured yes or no per question, not code.

Setup: the Pathly server runs from master with tickets 20 and 21 merged, `claude` is installed and
signed in, and a scratch project folder has a git repo and one feature folder. Open an operator
chief with Studio's Chief button (commit 3d9533e1) or by calling `POST /chief/open`. Pathly pastes
the style and the fixed rules into the new tab and the person presses Enter. Record the exact claude
CLI version. The person ran this on 2026-10-26 on their own machine with their own Claude Code,
which wrote the observations to `pathly/features/chief-agent/spike19-part-b-report.md` (commit
7fc5e73b). The builder of this ticket writes the Answer from that report and adds nothing it did not
observe.

Answer each question yes or no, with the command and what it printed:

1. Restricted start. Ask the chief to run `ls`, `git status`, `curl http://127.0.0.1:8765/health`
   and `python3 -c "print(1)"`. Only `pathly *` runs without asking; curl and wget are denied; any
   other command asks.
2. Switches. With `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` and `CLAUDE_CODE_DISABLE_CRON=1` in the
   chief's settings (ticket 20, B1), a background command and a `.claude/scheduled_tasks.json` entry
   produce no prompt in the tab.
3. Hook. A message the person types in the tab is recorded by the `UserPromptSubmit` hook as a
   `human` row with a message number the chief can cite (read it in the database or by the route the
   docs name).
4. `pathly api`. Inside the tab the chief reads `GET /chief/session?project_root=<root>` and posts
   with `POST /comms/post`; the posted row carries the chief's stamp.
5. Cited answers end to end. Get a headless agent to ask the person a question (the way
   `src/pathly_orchestrator/CLAUDE.md` "Cited answers" describes). The person types the answer in the
   chief tab. The chief answers with `cite`; the agent receives the person's exact words. An answer
   without a cite is refused (403) and does not reach the agent.
6. Limits. Set `chief.max_runs_per_session` to 2 and ask the chief for three runs. The third is
   refused, no run starts, and the chief tells the person.
7. The texts. The built-in operator style plus the fixed rules lead a real claude to sensible first
   commands: read the session, `GET /comms` with board, scope and feature, no curl. Record anything it
   gets wrong.
8. Close. `POST /chief/close` ends the tab and the chief's token stops working (a `pathly api` call
   from a shell that still holds it answers 401).

Every "no" is recorded in the Answer under `For later tickets` as a proposed ticket. Do not fix a
finding inside this ticket.

Part B adds to Done when: the Answer has a yes or no with evidence for each of questions 1 to 8 and
the CLI version; the known-limit sentence in the `(chief-agent)` entry of `CHANGELOG.md` ("no
automated test opens a real claude" and the sentence naming this spike) says what was measured and
what stays unmeasured; `learnings.md` gains one line, tagged with this ticket number, for each
surprising finding.

## Not in this ticket

- Changing the guard, the spawn argv, or any ceiling.
- The reporting integration: `round-two-drafts/daycap-spend-report.md`
  (independent of this outcome).

## Done when

- The `## Answer` section says part A was not run (the person's choice, 2026-10-26), so whether
  the guard fires on headless spawns is not measured, no outcome (A/B) holds and no daycap doc
  line is added.
- Part B's Done when (above) holds; the report's proposed tickets are listed under
  `For later tickets` in the Answer, security first.

## Reference

- spec.md § Decisions: "The chief's claude permissions" (restricted start), "Limits"
  (session ceilings),
  `round-two-drafts/daycap-spend-report.md` (daycap reporting)
- daycap `src/bin/guard.js` (invariants 1-4, fail-open design),
  `src/bin/daycap.ts` (`install --guard`)
- `src/pathly_orchestrator/supervisor/terminal.py` (spawn construction),
  `src/pathly_orchestrator/adapters.py` (`_dash_safe_prompt`, headless argv)

## Answer

Work started at `9a9200bac9b2dfd8cf6f9843ae5551153d7be158`. This Answer is written from
`pathly/features/chief-agent/spike19-part-b-report.md` (commit 7fc5e73b), the person's own record
of one live session on their machine. The builder ran no claude, no server and no daycap, and
adds nothing the report does not say.

### Part A: not run

The person chose on 2026-10-26 to run part B only and leave daycap untouched. Whether daycap's
guard fires on Pathly's headless `claude -p ... --dangerously-skip-permissions` spawns is **not
measured**: neither sub-question (does a `-p` session load the user's hooks; does
`--dangerously-skip-permissions` bypass the PreToolUse decision) has an answer, no CLI version was
recorded for it and no over-budget spawn cost exists. Neither Outcome A nor Outcome B holds, so no
daycap line goes into `src/pathly_orchestrator/CLAUDE.md`, no `chief-connect` text changes, and
no Outcome-B learnings line is written. Nobody may treat daycap as a backstop for Pathly's spawns
until a later spike measures it. The "guard does not run in the chief tab" confirmation was not
done either (it needs daycap installed).

### Part B: a real claude in the chief tab

Environment (from the report): 2026-10-26, 10:35 to 12:15 IST; **claude `2.1.310 (Claude
Code)`** (the docs' switch measurements were on 2.1.304); macOS 27.0 (26A428); server from the
repo's `.venv` at commit `3d9533e1` (master = origin/master, nothing merged); a throwaway scratch
repo with one commit and `pathly/features/demo/`. Chief opened with Studio's Chief button, engine
`claude`, style Operator; the measured session is the second open, `chief-5f8cb4507e60` (the first
lost its prompt, see Surprises). The argv was `claude --restricted --tools Bash,Read,Glob,Grep
--settings <session>/settings.json --mcp-config <session>/mcp.json --strict-mcp-config
--session-id …`, and the tab showed "auto mode on (shift+tab to cycle)" both times.

1. **Restricted start: NO.** The person asked for each command in turn. `ls`: "Listed 1
   directory", empty; the chief then ran `pwd; ls -la`, "Allowed by auto mode classifier", which
   printed nothing either. `git status`: "Allowed by auto mode classifier", printed the untracked
   `pathly/`. `curl http://127.0.0.1:8765/health`: "Permission to use Bash with command curl -sS
   http://127.0.0.1:8765/health has been denied." `python3 -c "print(1)"`: "Allowed by auto mode
   classifier", printed `1`. Only curl behaved as the docs say; no command asked the person.
   claude 2.1.310 started in auto mode, the argv passes no `--permission-mode`, and `--restricted`
   does not stop auto mode. `wget` was not tried.
2. **Switches: YES, with no positive control.** The session's `settings.json` `env` holds
   `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS: "1"` and `CLAUDE_CODE_DISABLE_CRON: "1"`. Asked to run
   `sleep 5` with `run_in_background: true`, the chief said its Bash tool "has no
   run_in_background option. It only accepts command, description, timeout and
   dangerouslyDisableSandbox", and ran nothing. A one-shot entry written to
   `<scratch>/.claude/scheduled_tasks.json` at 10:58:47, due 11:00:00 (shape taken from the
   2.1.310 binary's parser), had not fired at 11:03: nothing in the tab, file unchanged,
   `chief_human_messages` held only the style prompt and typed rows. No chief without
   `CLAUDE_CODE_DISABLE_CRON` was tried, so this shows nothing fired, not that the switch alone
   stopped it.
3. **Hook: YES.** Typed `hello, reply OK`; read-only `~/.pathly/pathly.db` gained
   `(12, 'chief-5f8cb4507e60', '~/pathly-spike19-scratch', 'human', 'hello, reply OK', <ts>)`.
   The line "Pathly recorded this as human message <id>" is not shown in the tab (claude adds
   hook stdout to the model's context), but the chief got it: it wrote unprompted "I didn't cite
   your message (#7)", and row 7 was that request. The style prompt is row 6, kind
   `style_prompt`, stored starting with `<pasted_content id=…>`.
4. **`pathly api`: YES, after one help step.** The chief ran `pathly api GET
   '/chief/session?project_root=<root>'` (200), then posted twice with a guessed author field
   (`from_agent`, then `agent`); both 403 `{"error":"a chief posts as 'chief'"}`, and it stopped
   and asked. Told to run `pathly help` and retry, it posted `pathly api POST /comms/post
   '{"from": "chief", "type": "note", "text": "live check note", "board": "project", "scope":
   "<root>", "feature": "project"}'` → `{"message_id": "326e4aa6-…", "ok": true}`. `GET /comms`
   with board, scope and feature returns it with `from_agent: chief`, `author_role: chief`,
   `author_run_id: chief-5f8cb4507e60`, `author_source: token`.
5. **Cited answers end to end: NOT MEASURED.** The refusal half is YES; the agent half is not
   measured. The chief posted goal `58309c0f-…` and a task telling the agent to use
   AskUserQuestion, and started it (`POST /runs` kind `goal` → run `8cf8ec4b-…`, kind `single`).
   The headless agent (claude-sonnet-4-6, 150 s, 22 turns, 0.549 USD) never called
   AskUserQuestion (`"permission_denials":[]`, no such call in the transcript); it posted board
   question `07712a9f-…` "Which colour do you prefer: red or blue?", read the board a few times
   (including the `BOARD.json` mirror on disk), and exited; the run ended `done` with a synthetic
   `AGENT_DONE` `outcome: "success"` while the task stayed `in_progress` and no `colour.txt` was
   written. So no run waited and `/runner/agent-answer` had nothing to answer, which matches the
   code: only `supervisor/orchestrator.py` reads `ask_user_question` and calls
   `_await_agent_question`, and a `single` goal run goes through `board_run`. Through the board:
   the person typed `blue` (row 18, `human`); the chief ran `pathly api POST /comms/answer
   '{"question_id": "07712a9f-…", "cite": 18}'` → `{"answer_id": "66ca0525-…", "ok": true}`; the
   answer row's text is exactly `blue`, `reply_to` the question, the question is `answered`, and
   `chief_citations` holds message 18 → `/comms/answer` → `07712a9f-…`. Without a cite: `POST
   /comms/answer` with `"answer": "purple"` → `pathly: HTTP 403`
   `{"action":"answer", …, "error":"send cite only: Pathly relays the cited message's
   text","tier":"operator"}`; no `purple` row, no citation spent. Not measured: an agent
   receiving "blue".
6. **Limits: YES.** `runs_started` was already 1 (the goal run), so the observer (the
   person's own Claude Code, which wrote the report) set `chief.max_runs_per_session` to 3, not 2 (`PUT /db/settings/chief.max_runs_per_session
   {"value": "3"}`; the session then reported 3), which leaves the same two more runs the ticket
   asks for. Three typed requests for `POST /runs` kind `flow` `explore` with `max_cost_usd: 0.5`:
   N=1 `ok: true` run `411c20b2-…` and N=2 `ok: true` run `b088fca1-…` (each stopped within a
   second by a watcher, 0.0 USD; `runs_started` then 3); N=3 `pathly: HTTP 403`
   `{"action":"run", …, "error":"this chief session has started its maximum number of
   runs","limit":3,"tier":"operator"}`, and `GET /runs` still listed 3 runs. The chief told the
   person and did not retry. The setting row was deleted afterwards (no route deletes a setting);
   the session reported 20 again.
7. **The texts: YES for the first move, with misreadings later.** First move after the Operator
   text, all through `pathly api` and no curl: `GET /chief/session`, `GET /comms/goals`, `GET
   /comms` for pending `question` and then `escalation` (each with board, scope and feature),
   `GET /runs`, then a short correct summary. Got wrong: guessed the `POST /comms/post` author
   field (the Operator text shows no post body; the 403 does not name the field; `pathly help`
   shows `"from": "chief"` but was run only when told); said a goal run was "capped at $10" (a
   goal run takes no `max_cost_usd`); said "out of 20" after the limit became 3 because it never
   re-read the session, and then wrongly guessed the endpoint and the enforcer disagree; after
   the curl deny it offered `! curl …` or allowing curl in the permission settings, a route
   around the deny; answered the colour question as soon as `blue` was typed (it had offered to,
   so defensible, but no explicit order was given). Also: `pathly help` lists post types as "a
   message, goal or task", yet `note` was accepted.
8. **Close: YES (401 measured).** The chief's `PATHLY_RUN_TOKEN` was read from its environment
   into a private file (never printed); `pathly api GET '/chief/session?project_root=<root>'` with
   it exited 0. The person clicked Close chief in Studio: `GET /chief/session` gave
   `{"open":false}`, the tab and process were gone, the session row had `close_reason: closed
   from Studio`, the token row had `revoked_at` set, and `~/.pathly/chief/` was empty. The same
   call then answered `pathly: HTTP 401` `{"error":"chief session closed"}`, exit 1. The token
   file was deleted.

Spend: 0.549 USD in Pathly runs (the goal run 0.5488, the two explore runs 0.0 each). The chief
tab's own claude usage is not billed by Pathly and was not measured.

Surprises (all from the report): the first open of a never-trusted folder lost its prompt to
claude's folder-trust dialog (that session closed `tab closed`; cause not checked); auto mode plus
Bash means the chief can likely read its own `hook_secret` (`Read(~/.pathly/**)` denies only the
Read tool; not tried); the chief's Bash schema offers `dangerouslyDisableSandbox`; `ls` and `ls
-la` printed nothing in the tab while `git status` listed files (cause unknown); the goal-run
agent's first command was `echo "PATHLY_RUN_TOKEN: $PATHLY_RUN_TOKEN"`, putting its run token into
its own transcript (no core file tells it to); the relayed answer is stored `from_agent: human`,
`author_source: none`, and only `chief_citations` shows a chief relayed it; an explore flow run
from `POST /runs` opened an interactive claude tab that stopped at the "Bypass Permissions mode …
No, exit / Yes, I accept" dialog; `GET /runs` lists flow runs as `kind: single`; the chief cannot
learn a run finished unless the person writes to it (by design, but the person expected to be
told).

### Built

- `CHANGELOG.md`: in the `(chief-agent)` entry, the known-limit sentence that said no test opens
  a real claude and named spike 19 as the planned check now says what part B measured on claude
  2.1.310, that the restricted flags do not hold as written (auto mode), and what stays
  unmeasured (a cited answer reaching a waiting agent, the switches without a positive control,
  daycap's guard on headless spawns). Nothing else in the entry changed.
- This ticket's Status and Answer; one line appended to `map.md`; ten lines appended to
  `learnings.md` (six in the first build, four more in the rebuild).

### Proof

- Part A bullet: the "Part A: not run" section above states it was not run (the person's choice,
  2026-10-26), that the guard question is not measured, that neither outcome holds and that no
  daycap doc line is added. `git diff --stat 9a9200ba` shows no change to
  `src/pathly_orchestrator/CLAUDE.md` or any fragment.
- Part B, eight answers and the CLI version: questions 1 to 8 above each carry YES, NO or NOT
  MEASURED with the command and what it printed, taken from the report; claude `2.1.310 (Claude
  Code)`.
- CHANGELOG: `git diff 9a9200ba -- CHANGELOG.md` shows only the sentence beginning "Every test
  fakes the spawn host" replaced (lines 83 to 97 now).
- learnings: ten `(19)` lines appended (`git diff 9a9200ba -- pathly/features/chief-agent/learnings.md`
  shows ten added lines, all starting `- (19)`, and no line removed or changed), one per surprising
  finding: auto mode, the trust dialog, the agent echoing its token, a goal run's question never
  waiting, the hook line not visible in the tab, the explore run's interactive bypass dialog (with
  `GET /runs` listing it as `kind: single`), the chief's Bash offering `dangerouslyDisableSandbox`,
  `ls` printing nothing in the tab, the agent reading the `BOARD.json` mirror from disk, and a
  relayed answer stored as `from_agent: human`, `author_source: none`. The report's last surprise
  (the chief cannot learn a run finished unless the person writes to it) is by design and is
  proposed ticket 13 below, so it has no learnings line.
- Proposed tickets: listed below, security first.

### Decisions

- Question 5 is answered NOT MEASURED as the report does, not NO: the refusal half held, and the
  delivery half never had a waiting agent to receive the answer.
- Question 6 is YES although the limit was set to 3, not 2: the session had already started one
  run, so 3 left exactly the two allowed runs and a refused third, which is what the question
  tests.
- The CHANGELOG still says `wget` was not tried, since the report's command list has no wget.

### Shortcuts taken

None. No claude was run by the builder; every claim above is the report's.

### Review fixes

Rebuild after round 1 (previous build `fd7f7d59`; this rebuild started at `966dc031`).

- **learnings.md missed four surprising findings (spec review, NOT MET).** Agreed. Appended four
  `(19)` lines, each taken from the report's "Surprises" section (and, for the agent's board
  reads, its question 5): the chief's Bash offers `dangerouslyDisableSandbox`; `ls` and `ls -la`
  printed nothing in the tab while `git status` listed files (cause unknown); the goal-run agent
  read the `pathly/project/BOARD.json` mirror from disk; a relayed answer is stored
  `from_agent: human`, `author_source: none` and only `chief_citations` shows the chief relayed it.
  No existing line was edited.
- **The Proof line said six lines.** Corrected to ten, with the full list; Built corrected too.
- **Optional: who set the limit in question 6.** Changed: the observer (the person's own Claude
  Code, which wrote the report and says "I set it to 3") set it, not the person.

### For later tickets

Every NO, NOT MEASURED and surprise from the report, as proposed tickets (security first). None
is fixed here.

1. **Security.** Start the chief with an explicit `--permission-mode` so auto mode cannot approve
   non-`pathly` commands (`dontAsk` denies anything not allowed ahead of time; claude 2.1.310's
   `--help` also lists `manual` if the person should be asked), then re-measure question 1.
2. **Security.** Make the chief's secret files unreadable to its Bash too, or measure that they
   are: with the hook secret and the `--session-id` a forged `human` message could be cited as
   the person's words.
3. **Security.** Stop agents echoing `PATHLY_RUN_TOKEN`, or redact it from their output and
   transcripts.
4. Open the chief only in a folder claude already trusts, or clear the trust dialog before the
   paste, so the first prompt is never lost.
5. Route a goal-run agent's question to a waiting run (or resume the task when a board question
   is answered), then re-measure question 5's delivery half.
6. Do not let a `single`-executor run end `done` / `success` while its claimed task is still
   `in_progress`.
7. Stamp an answer the chief relays as chief-relayed on the board row, not `author_source: none`.
8. Name the field in the 403 `a chief posts as 'chief'` (`"from": "chief"`), and show a full
   `POST /comms/post` body in the Operator text.
9. Make the Operator text say a goal run has no per-run cost cap, and that the chief re-reads the
   session before quoting its limits.
10. Make the texts forbid suggesting the person bypass a deny (`! curl`, changing permissions).
11. Make explore (and every flow) runs started by `POST /runs` headless, without the interactive
    bypass dialog.
12. Make `GET /runs` report a flow run's kind as `flow`.
13. Tell the person when a run the chief started finishes (the report's "Plan discussed" parts 1
    and 2; a notice injected into the tab must be stored as `relayed`, never citable).
14. Round two: a bounded autopilot (the report's part 3), after 1, 5, 6 and 13.
15. Run a positive control for the cron switch (a chief without `CLAUDE_CODE_DISABLE_CRON`) on
    2.1.310.
16. Find out why `ls` prints nothing in the chief tab.
17. Part A, still open: a spike that installs daycap's guard and measures it against a headless
    spawn, before anyone treats daycap as a backstop.

Also: the docstring of `tests/comms_board/test_chief_acceptance.py` (lines 16 to 21) still says
spike 19 part B "is the planned hand run" and lists the same items as unmeasured. This ticket's
Done when names only the CHANGELOG sentence, so it was left; whoever next touches that file
should bring it in line with the CHANGELOG. The CHANGELOG's earlier sentence that the cron switch
was "measured on claude 2.1.304 only" is still true and was left.

## Review findings (round 1, spec review)

SPEC
- Answer says part A was not run (the person's choice, 2026-10-26), the guard question is not measured, no outcome (A/B) holds and no daycap doc line is added: MET. The "Part A: not run" section says all of this; `git diff --stat 9a9200ba..fd7f7d59 -- src/` prints nothing.
- Part B: a yes or no with evidence for questions 1 to 8, plus the CLI version: MET. 1 NO, 2 YES (no positive control), 3 YES, 4 YES, 5 NOT MEASURED, 6 YES, 7 YES with misreadings, 8 YES (401); CLI `2.1.310 (Claude Code)`. One small attribution change: the report's observer says "I set it to 3" (the limit), the Answer says "the person set".
- Part B: the CHANGELOG known-limit sentence says what was measured and what stays unmeasured: MET (lines 84-97 the only change; every claim is in the report).
- Part B: learnings.md gains one `(19)` line per surprising finding: NOT MET. Six `(19)` lines were added (learnings.md lines 100-105). The report's "Surprises" section has findings with no line:
  - the chief's Bash schema offers `dangerouslyDisableSandbox`;
  - a relayed answer is stored `from_agent: human`, `author_source: none`, and only `chief_citations` shows the chief relayed it;
  - the goal-run agent read the `BOARD.json` mirror from disk to look for answers;
  - `ls` and `ls -la` printed nothing in the tab while `git status` listed files.
  The Answer's Proof still says "six `(19)` lines appended, one per surprising finding".
- Part B: the report's proposed tickets are listed under `For later tickets`, security first: MET (all 16 in order, 3 security first, plus "Part A, still open").
- Scope: OK (CHANGELOG.md, learnings.md, map.md, the ticket).
- Test first: n/a (`Test first: no`).

To fix: add a `(19)` line to learnings.md for each of the four findings above, or write in the Answer why each one is not a surprising finding, and correct the Proof line. Optional: change the Q6 wording so the observer, not the person, set the limit.

REVIEW: FAIL
