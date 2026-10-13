# Chief agent — Spec

## Problem

The user wants one seat from which to run the whole of Pathly: "the user will only interact with
chief agent". That agent should read Pathly's state and configuration (agent settings, the board,
which agents are running, which features and tasks are planned and done) and get work done by
starting the configured agents (planner, builder, reviewer, tester, designer or any other), each
opened by Pathly's normal spawn path as a visible tab. Today that seat is the HQ chat panel backed
by `chat_agent.py`, a regex matcher with no model behind it. The previous chief plan (one headless
`claude -p --resume` turn per message behind a chat panel, woken by events; git `72292b35`) was
set aside in favour of an interactive CLI the user talks to directly.

Two things stand in the way. First, an LLM with write access to Pathly's HTTP API is only safe if
the server knows the caller is the chief and what it may do, and today three holes let any client
holding or reading a run token act as someone else: the raw `run_token` in the `TERMINAL_SPAWN`
payload is broadcast to `/events/runner` and `/events/runs` clients, `POST /db/query` accepts
`WITH ... INSERT` (enough to forge an author stamp or mint a token), and `POST /comms/edit`
rewrites a row's text under the original author's stamp. Second, an answer the chief relays to an
agent's question must be traceable to something the human really typed, and a decision the chief
makes must keep reaching worker prompts after someone acknowledges it.

## Goal and the bar

A **Chief** button in Studio replaces the HQ chat panel. It opens an interactive CLI tab: the user
picks the engine and a chief style in the shared prompt picker, Pathly pastes the style's prompt
(the user presses Enter), and the chief acts only through Pathly's HTTP API and a `pathly` command
set over it. The chief never writes code and never opens agent CLIs itself. The server knows the
chief by a run token with role `chief`, bound to the style's permission tier, handed to the CLI in
the environment as `PATHLY_RUN_TOKEN` (never in the prompt) and revoked when the tab closes.

The work lands in two rounds, following the user's decision for rounds. Round one, this
plan's tickets, builds the server core and proves the brief's bar. Round two builds the surfaces on
top of it: the `pathly` command set, the overview and inbox calls, the built-in preset texts,
Studio pasting without Enter, the Chief button replacing HQ (with `chat_agent.py` as the no-engine
fallback), the inbox badge, the stale-directive re-queue and billing the chief's own session. It is
outlined in `map.md` § Round two and planned as `pathly/features/chief-agent-round-two/` once round
one is built, because its tickets build on round-one code that does not exist yet. `map.md` §
Brief coverage maps every In-scope line of the brief to a round-one ticket or a round-two item.
The other option, planning round two now in this folder, is in `map.md` § Open questions.

**The bar.**

- `python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider` passes with
  a fake spawn host:
  - opening the chief mints a `chief` token for the chosen style and spawns an interactive tab
    with the style's prompt pasted and not sent;
  - with the Operator style, the chief's API calls create a goal and start a run that Pathly
    spawns through its normal spawn path;
  - a Status-style token is refused on a write;
  - an agent question stays pending until it is answered with a cited human message, relayed word
    for word, and an uncited or reworded answer is refused;
  - a binding decision reaches the next builder, reviewer and tester prompts after an
    acknowledgement, and no caller but the chief can retire it;
  - a run above the chief's cost ceiling and a call on another project's run are refused;
  - `pathly api` works from the chief's tab with the chief's token;
  - the raw run token no longer appears on `/events/runner` or `/events/runs`.
- `python -m pytest tests/ -q -p no:cacheprovider` passes in full.

## Stories

### Open a chief in the style I want

**As a** Pathly user, **I want** to open a chief tab with an engine and a style I choose, **so
that** one agent runs the system for me with exactly the powers I gave it.

- [ ] Opening mints a `chief` run token whose session records the tier resolved from the preset;
      the token reaches the CLI only through `PATHLY_RUN_TOKEN`.
- [ ] The style's prompt is pasted into the tab and not submitted.
- [ ] A second open for the same project returns the open session instead of a second chief.
- [ ] Closing the tab revokes the token; a server restart closes every chief left open.

### Styles are editable, permissions are not

**As a** user, **I want** to edit and save chief prompts, **so that** I can tune how the chief
works without being able to talk it into more power by editing its text.

- [ ] Each preset names its base tier (`status`, `planner` or `operator`); a missing or unknown
      tier means Status (read-only).
- [ ] The action list for each tier is a server constant bound to the session, never read from
      prompt text.

### The server refuses what the style does not allow

**As a** user, **I want** a Status chief that cannot change anything, **so that** I can ask
questions without risk.

- [ ] A chief token on a write its tier lacks gets 403 with the allowed actions.
- [ ] A route the chief has no business calling (`/db/query`, prompt-file writes, `/chief/open`)
      gets 403 whatever the tier.
- [ ] A revoked chief token gets 401 and never falls back to anonymous.
- [ ] A Planner chief may post goals and tasks and call the decompose routes, but a call that
      passes `prompt_override` or `stage_overrides` is refused, and it never starts or controls a
      build run.

### Answers I gave, provably

**As a** user, **I want** every answer the chief relays to an agent to cite something I typed,
**so that** an agent never acts on an answer the chief made up.

- [ ] Every prompt the user submits in a claude chief tab is recorded by a hook.
- [ ] A chief-token answer must cite a recorded human message from the same session, typed after
      the question was asked, and must be that message's text; otherwise it is refused and the
      question stays pending.
- [ ] Each typed message can be cited once.
- [ ] The chief can close a human-addressed escalation only by citing a message typed after it.

### Standing orders

**As a** user, **I want** the chief's binding decisions to keep reaching the agents they target,
**so that** an acknowledgement does not silently drop a standing order.

- [ ] A binding decision for a role (or `*`) appears in that role's next prompts after it is
      acknowledged, until it is superseded or deleted.
- [ ] Only a chief token whose tier can `decide` may post one until the UI token exists; nothing
      else may. It cannot be edited in place.
- [ ] Only the chief can supersede it; nobody can delete it; a mirror file cannot plant one.
- [ ] It renders as a standing order that a newer ordinary decision does not outrank.

### Bounded and usable

**As a** user, **I want** the chief to stay inside my project and my budget, and to work from its
tab on day one, **so that** I can leave it running without surprises.

- [ ] A chief cannot act on a run or a board row of another project, even by id.
- [ ] A chief run above `chief.max_cost_usd_per_run`, or past `chief.max_runs_per_session`
      starts, is refused.
- [ ] `pathly api` reaches every route with the chief's token and refuses to run without it;
      the three styles have built-in texts.

## Scope

In (round one, this plan):

- The three token holes: `run_token` stripped from `/events/runner` and `/events/runs`;
  `POST /db/query` read-only; `POST /comms/edit` re-stamped to the editor.
- Chief tiers, preset-to-tier resolution, chief session tables, the open/close lifecycle,
  `/chief/open|close|session`.
- The chief gate (deny by default, tier-bound, project-bound) and `chief` as a project-board writer.
- Human-message capture for claude (UserPromptSubmit hook) and the cited-answer rule.
- Binding directives: the `binding` column, role-aware governance injection in its own
  standing-orders block, `POST /comms/directives`, edits refused on binding rows, supersede and
  delete refused to everyone but the chief, hydration storing `binding = 0`.
- Project binding for id-addressed calls; a cost and run ceiling per chief session.
- The `pathly api` command and built-in Status, Planner and Operator texts, so round one can be
  used from a tab opened with `POST /chief/open`.
- The acceptance test, living docs and CHANGELOG.

In (round two, per the user's decision for rounds; outlined in `map.md` § Round two): the
friendly `pathly` commands on top of `pathly api`, `GET /chief/overview` and `GET /chief/inbox`,
richer preset texts and the `chief` Library category, Studio paste-without-Enter, the Chief button on the shared
`PromptActionConfig` picker replacing HQ (with `chat_agent.py` as the no-engine fallback), the
inbox badge, the stale-directive re-queue, billing the chief's own session, and round two's
acceptance and docs.

Not in scope:

- The chief writing code, running stages or spawning CLIs itself (it has no tool for it; the
  server spawns).
- Headless event-triggered chief turns, a chat thread store, a chat UI (set aside with the old plan).
- Episodic memory and scheduled consolidate/promote (a later plan).
- The rest of the read wall: wiring `read_policy` into read paths (RRP-4/5), the UI token
  (RRP-2b), warn/enforce rollout (`pathly/features/role-read-policy/map.md`).
- Multi-user.
- Human-message capture for codex (round one opens codex chiefs without it; see Open questions).

## Happy path

1. User clicks **Chief** (round two) → the launcher shows engine and style presets → user picks
   claude and "Operator", clicks Open → Studio posts `/chief/open`.
2. Server resolves the tier (`operator`), mints a `chief` token, writes the session's claude
   settings (hook + permissions), records the session and broadcasts `TERMINAL_SPAWN` with
   `interactive: true, submit: false` → Studio opens a "Chief · Operator" tab, exports
   `PATHLY_RUN_TOKEN`, pastes the prompt → the user sees the prompt waiting in the input.
3. User presses Enter → the hook records the submission (first one = `style_prompt`) → the chief
   reads the board and the open runs with `pathly api GET …` (round two adds `pathly inbox` and
   `pathly overview`).
4. User: "plan and build the export feature" → the chief posts a goal, decomposes it, starts a run
   (`POST /runs`) → the gate allows each call for `operator` → the server spawns the planner and
   builder tabs through `_run_stage_via_terminal` as usual.
5. The builder asks a question → it is held pending → the chief reads it from the inbox and asks
   the user → the user types "use CSV" (hook records it as human message 41) → the chief answers
   with `cite: 41` and the answer "use CSV" → the gate checks the citation, the words and that 41
   was not cited before, and records it → the builder continues.
6. User: "from now on, no new dependencies" → the chief posts a binding directive to `*` → every
   later builder, reviewer and tester prompt carries it, even after the decision is acknowledged.
7. User closes the tab → Studio reports the result → the session closes and the token is revoked.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| Open while a chief is already open for the project | 409 with the open `run_id` and `tab_id`, nothing minted | 07 |
| Open with `copilot` or `antigravity` | 400 naming the supported engines (`claude`, `codex`) | 06 |
| Open from a caller that sends a live run token (an agent) | 403 | 07 |
| Preset unknown, user file without `tier:`, or `tier: admin` | Status tier | 04 |
| User file `pathly/prompts/chief/operator.md` without front matter | Status (the file overrides the built-in name) | 04 |
| No spawn host starts the tab within 30 s | session closed, token revoked | 06 |
| Only `pathly-pty-host` is running (refuses interactive spawns) | its failed result closes the session | 06 |
| Server restarts with a chief open | at start every open session is closed and its token revoked | 07 |
| Chief sends its revoked token | 401 `chief session closed`, never anonymous | 08 |
| Chief token on an unlisted write (`/db/query`, `/skills/prompts`, `/chief/open`, `/comms/edit`) | 403 | 08 |
| Chief token reads `/events/*` or `/db/settings` | 403 (spawn tokens, stored secrets) | 08 |
| Chief token with another project's `project_root` | 403 | 08 |
| Chief token on a path no route matches | the gate passes, Flask answers 404, no view runs | 08 |
| Chief posts with `from: "builder"` | 403 | 08 |
| Planner chief sends `prompt_override` or `stage_overrides` to a decompose route | 403 naming `run` | 08 |
| A saved project write list that omits `chief` | the existing `/comms/post` 403 naming the allowed roles | 08 |
| Hook posts with a wrong secret or for a closed session | 403 / 404, nothing recorded | 09 |
| Server down when the hook runs | hook prints nothing and exits 0; the prompt goes through | 09 |
| Answer without `cite`, citing another session, the style prompt, or a message older than the question | 403, question stays pending | 10 |
| Codex chief (no hook) relays an answer | refused: no human messages exist for the session | 10 |
| Directive for `builder` | reaches builder prompts, not reviewer or tester | 11 |
| Project tier turned off for a role | binding directives from the project board are still injected | 11 |
| Directive superseded or deleted | leaves every prompt | 11 |
| `/comms/edit` on a binding row | 409 "supersede, don't edit" | 12 |
| `/comms/post` body with `binding: 1` | ignored; only `/comms/directives` sets it | 12 |
| Studio (no run token, server secret) posts to `/comms/directives` | 403 until the UI token exists | 12 |
| Answer citing a later human message with different words, or `option_id` from the chief | 403, question stays pending | 10 |
| Same human message cited for a second question | 403 "already cited" | 10 |
| Chief acknowledges a `to_agent: "human"` escalation | needs a cite typed after it; without one 403 (#63's gate stays closed) | 10 |
| Chief on `/comms/delete`, `/comms/hydrate`, `/comms/tasks/status`, `force_past_gate` | 403 | 08 |
| Chief pauses, aborts or answers a run of another project by id | 403 | 14 |
| Chief acknowledges or supersedes a row of another project by id | 403 | 14 |
| Chief `POST /runs` above `chief.max_cost_usd_per_run` (default 10) | 403 with the ceiling | 15 |
| Chief's 21st run start in one session (default limit 20) | 403 with the limit | 15 |
| Project-board run posts `supersedes` naming a directive | post stored, directive skipped with reason `binding` | 16 |
| `/comms/supersede` or `/comms/delete` on a directive without a chief token | 403 | 16 |
| `BOARD.json` row with `binding: 1`, or a row for another board | hydrated with `binding = 0` and `author_source = "legacy"`, or skipped | 16 |
| Newer ordinary decision on the same topic as a directive | listed below the standing-orders block; the directive still applies | 11 |
| `pathly api` with `PATHLY_RUN_TOKEN` unset (or filtered by codex) | exit 2 naming the variable, no request | 17 |
| `POST /chief/open` with a built-in preset and no `prompt` | the built-in text is pasted | 17 |
| `WITH x AS (...) INSERT ...` on `/db/query` | 400, nothing written | 02 |
| Studio renames a goal another role posted | stored text changes and the stamp becomes the editor's | 03 |

## Design

```
 Studio (Chief launcher, round two)
   │ POST /chief/open {engine, preset, prompt}
   ▼
 [chief blueprint] ─► [chief_session.open_chief]
                         │ tier = resolve_preset_tier(preset)
                         │ mint_run_token(role=chief)
                         │ chief_sessions row
                         │ settings.json (hook, permissions)
                         ▼
                      TERMINAL_SPAWN {interactive, submit:false}
                         │ /events/spawn only carries run_token
                         ▼
                      [spawn host tab] PATHLY_RUN_TOKEN in env
                         │                    │ UserPromptSubmit
                         │ pathly ... (HTTP)  ▼
                         │            POST /chief/human-messages
                         ▼                    │ hook secret
 [_log_request] ─► [chief_gate] ─► existing routes
        │ 401 revoked │ 403 tier/route/project
        ▼             ▼
      refused       refused
                         │ POST /runs, /comms/goals/*
                         ▼
                      supervisor ─► _run_stage_via_terminal
                         │ worker tabs, own tokens
                         ▼
 [retrieve_board_context(role)] ◄─ binding directives
```

The chief is a long-lived interactive spawn, so it does not go through
`_run_stage_via_terminal` (which blocks its caller and times out after 30 minutes). It reuses the
pieces that path is made of: `mint_run_token`, `create_run(run_id)` so the existing
`/runner/terminal/started` and `/runner/terminal/result` callbacks find it, and a watcher thread
that closes the session when the result arrives.

### Decisions

- **Where permissions come from** — options: A) a tier named by the preset and a server-side
  action table per tier; B) an action list stored with the preset file. Chosen: A. Why: prompt
  text and prompt files are user-editable (and writable by any worker agent with file access), so
  a list stored with them would let editing grant power; a tier word can only select one of three
  fixed lists, and the server shows it in the tab label.
- **Preset to tier** — options: A) the preset's front matter `tier:` decides, missing or unknown
  means Status; B) Studio sends the tier with the open request. Chosen: A. Resolution in
  `supervisor/chief_tiers.py::resolve_preset_tier(preset, project_root)`: a user prompt file
  `chief/<preset>` (project, else global, as `skills/prompt_files.read_prompt_file` merges them)
  decides by its front matter `tier:`; otherwise the built-in names `status`, `planner` and
  `operator` map to themselves; anything else is `status`. Front matter is stripped before the
  text is pasted and never read for anything else. Round two's "Save current as prompt" writes
  `tier: <tier of the selected preset>` into front matter when the body has none. Why: the tier
  stays a property of the saved preset, so the server alone decides it and every client that opens
  the preset gets the same tier; B would let any client claim `operator` for any text.
- **Tier table** — options: A) a Python constant; B) an editable `app_settings` table. Chosen: A.
  `status` = read; `planner` = read, post, plan; `operator` = read, post, plan, decide, run, stop,
  answer. Why: the brief's styles are data at the prompt level; editable permissions would need
  their own guard. B is listed as dropped so the user can ask for it.
- **What the Planner's `plan` covers** — options: A) posting goals and tasks and calling the three
  decompose routes (`/comms/goals/decompose`, `/comms/features/decompose`,
  `/comms/project/decompose`), which start plan-only planner or consultation agents, with any body
  that carries `prompt_override` or `stage_overrides` also needing `run`; B) posting goals and
  tasks only, so a Planner starts no agent at all. Chosen: A, the user's decision for the
  Planner style. Why: decomposing is how a goal becomes a plan in Pathly, and the overrides are the
  one way the caller's text reaches the spawned agents verbatim, so refusing them keeps the
  decomposers on their own skills. Build runs (`POST /runs`, goal start) and run control stay
  `run` and `stop`, which a Planner lacks.
- **The chief's spawn** — options: A) its own open path (`supervisor/chief_session.py`) that mints,
  registers the run and broadcasts `TERMINAL_SPAWN`, with a watcher thread; B) reuse
  `_run_stage_via_terminal`. Chosen: A. Why: B blocks the HTTP caller for the session's life and
  times out after 30 minutes.
- **One chief per project** — options: A) refuse a second open with 409 and the open tab; B) allow
  several. Chosen: A. Why: the human-message record and the inbox are per session, and the brief
  has one chief.
- **How the server enforces the tier** — options: A) one `before_request` gate keyed on the
  matched URL rule, deny by default for non-GET routes; B) checks inside each route. Chosen: A.
  Why: B edits a dozen routes (several at the 400-line ratchet) and a new route would be open to
  the chief by default.
- **Which reads the chief may make** — options: A) every GET except `/events/*` and
  `/db/settings`; B) an allow-list of GET routes. Chosen: A. Why: reading is what the chief is for
  and new GET routes are read-only by convention; `/events/spawn` carries spawn tokens and
  `/db/settings` can hold stored secrets.
- **Revoked chief tokens** — options: A) the gate looks the token up including revoked rows and
  answers 401 when it was a chief's; B) leave `caller_identity`'s fallback to anonymous. Chosen: A.
  Why: anonymous loopback callers can do everything, so B would turn a closed chief into an
  unrestricted one.
- **Recording human messages** — options: A) a claude UserPromptSubmit command hook in a
  per-session settings file, posting to `/chief/human-messages` with a per-session secret;
  B) the same hook authenticated by the chief's run token. Chosen: A. Why: the chief holds its
  token, so B would let it forge "human" messages. The first submission of a session is stored as
  `style_prompt` and cannot be cited.
- **Where the cited-answer rule lives** — options: A) in the chief gate for the `answer` action
  (`/runner/agent-answer`, `/comms/answer`); B) in each answer route. Chosen: A. Why: one rule for
  both routes, no edits to `api_control.py` or `messages_crud.py`. A cited message must be a
  `human` row of the same session; each use is recorded in `chief_citations`.
- **When the cited message must have been typed** — options: A) in the same chief session after
  the agent asked the question; B) any time in the same chief session. Chosen: A, the user's
  decision for cited answers. Why: a message typed before the question existed cannot have
  been an answer to it, so A keeps the chief from reusing an old remark. The cost: the user cannot
  answer ahead of time for the chief to relay later. B drops two timestamp comparisons in ticket 10.
- **Binding directives** — options: A) a new route `POST /comms/directives` that alone sets
  `binding = 1`; B) a `binding` field on `/comms/post`. Chosen: A. Why: `messages_write.py` sits at
  400 lines since #63 and B would need a second permission check inside it.
- **Who may post a directive** — options: A) only a live chief token whose tier has `decide`,
  until the UI token (RRP-2b) exists; B) that, or a caller that sends no run token and the matching
  server secret (what Studio sends today). Chosen: A, the user's decision for directives.
  Why: the server cannot tell Studio from a local agent until the UI token exists, and B gives the
  strongest write on the board to any local process that reads the server secret file, which
  agents do (`fsm_http_client._load_secret`). The brief's "(or the UI)" path waits for RRP-2b.
- **Directive reach** — options: A) inject binding decisions targeted at the prompt's role or
  `*`, from the enabled boards plus always the project board; B) only from enabled boards like
  other governance. Chosen: A. Why: a standing order must not be muted by a context-budget tier
  toggle.
- **`/db/query` read-only** — options: A) `PRAGMA query_only = ON` on the request thread's
  connection for the one statement, reset in `finally`; B) a separate `mode=ro` connection.
  Chosen: A. Why: the connection is thread-local and already has sqlite-vec loaded; a fresh one
  would break SELECTs over vector tables. `sqlite3` runs one statement per `execute`, so the user
  cannot flip the pragma back (`map.md` § Decisions so far: SQLite and Python `sqlite3` docs,
  measured on 3.11, 3.12 and 3.13).
- **`/comms/edit` provenance** — options: A) re-stamp the row to the editor; B) refuse edits by
  anyone but the author. Chosen: A. Why: Studio's goal rename (`services/messages.ts`) edits rows
  other roles posted; B breaks it.
- **SSE token hole** — options: A) send the `run_token` only on `/events/spawn` and strip it from
  the `/events/runner` and `/events/runs` copies; B) hand the token to hosts another way. Chosen:
  A. Why: the two hosts read it only from `/events/spawn` (role-read-policy ticket 10 finding);
  closing `/events/spawn` itself needs the UI token (RRP-2b).
- **Engines** — options: A) claude fully, codex in a read-only sandbox without human-message
  capture, others refused; B) claude only. Chosen: A. Why: the brief lets the user pick the
  engine; codex passes `PATHLY_RUN_TOKEN` to its commands by default, `--sandbox read-only` keeps it
  from editing files and makes it ask before each command, and the cited-answer rule fails closed
  when no human message exists.
- **The chief's claude permissions** — options: A) the session settings file allows
  `Bash(pathly *)` and denies `Edit`, `Write`, `NotebookEdit`, `Agent`, `CronCreate`, `Workflow`,
  `Read(~/.pathly/**)`, `Bash(curl *)` and `Bash(wget *)`, with no permission-bypass flag, and the
  chief starts with `--strict-mcp-config` and an empty MCP config; B) the same as CLI flags.
  Chosen: A. Why: one file holds the hook and the rules; every other command asks the human. Deny
  wins over allow rules in the user's own settings, so the chief cannot drop its token through
  curl or wget, and no user or project MCP server (Serena's edit tools, the `pathly-fsm` MCP)
  reaches it.

- **What a citation proves** — options: A) the answer must be the cited message's text, verbatim,
  each message citable once, no `option_id` from the chief; B) the cited message only has to exist
  and come after the question. Chosen: A (revised after the independent review of 2026-10-13).
  Why: under B a chief can cite the user's "ok" and relay any answer it likes, and reuse one
  citation for every question. The cost: the user's words reach the agent as typed, and the user
  types once per question.
- **Human escalations** — options: A) a chief with `answer` may acknowledge a `to_agent: "human"`
  escalation with a cite typed after it, through a flag the gate sets for
  `refuse_agent_on_human_gate`; B) leave #63's refusal for every run token. Chosen: A. Why: under
  B the chief cannot close the main way agents ask the human, and the user talks only to the
  chief. Delete and `force_past_gate` stay refused.
- **Who retires a directive** — options: A) only a chief token (supersede); nobody deletes one;
  hydration stores `binding = 0`; B) keep #63's paths open to any project-board run and to
  token-less callers. Chosen: A. Why: under B "only the chief posts a standing order" means
  nothing, because any other caller can retire it the next minute.
- **How directives render** — options: A) their own standing-orders block before the ranked
  decisions; B) inside #63's tier-then-newest list. Chosen: A. Why: B tells the agent the newest
  decision wins, so any later note outranks a standing order.
- **Limits** — options: A) per-session ceilings in the gate (`chief.max_cost_usd_per_run` 10,
  `chief.max_runs_per_session` 20, set by the user in app settings); B) none in round one.
  Chosen: A. Why: an injected or confused chief can start runs in a loop while the user is away.
- **Usable in round one** — options: A) a generic `pathly api` command and three short built-in
  texts now, the friendly commands in round two; B) everything in round two. Chosen: A. Why:
  under B round one ends with a chief that has no allowed way to call the API (curl is denied
  and every other command asks).

## Interfaces

- `POST /chief/open` `{project_root, engine: "claude"|"codex", model?, preset, prompt?}`
  (`prompt` may be left out for a built-in preset) →
  201 `{run_id, tab_id, tier, engine}`; 409 `{error, run_id, tab_id}`; 400 bad input or engine;
  403 caller sent a live run token.
- `POST /chief/close` `{project_root}` → 200 `{closed: true|false}`.
- `GET /chief/session?project_root=` → `{open, run_id, tab_id, tier, engine, opened_at,
  runs_started, max_runs_per_session, max_cost_usd_per_run}`.
- `pathly api <METHOD> <path> [<json> | -]` → prints the body; exit 0 on 2xx, 1 otherwise, 2 on
  usage or a missing `PATHLY_RUN_TOKEN`. `pathly help`.
- Answers from a chief token carry `cite: <human message id>`, and `answer` equals that message's
  text; `/comms/acknowledge` on a human escalation carries `cite`.
- `POST /chief/human-messages` `{run_id, hook_secret, text}` → 201 `{id, kind}`; 403 bad secret;
  404 no open session; 400 bad text (empty, not a string, over 64 KiB).
- `POST /comms/directives` `{project_root, to_agent: "*"|<role>, text}` → 201 `{id}`, posted on
  the project board; 400 bad `to_agent` or text; 403 for anything but a live chief token whose
  tier has `decide`.
- Chief gate refusals: 401 `{"error": "chief session closed"}`; 403 `{"error", "action", "tier",
  "allowed"}`; 403 `{"error": "cite a human message from this chief session"}` for answers.
- `TERMINAL_SPAWN` for a chief: `{type, topic: "chief:<run_id>", run_id, run_token, tab_id,
  label: "Chief · <Tier>", adapter, argv, cwd, prompt, interactive: true, submit: false,
  category: "single"}`. `run_token` is present only on the `/events/spawn` copy of any spawn.
- Hook: `<python> -m pathly_hooks.chief_prompt --run-id <id> --secret-file <path> --port <port>`;
  reads the UserPromptSubmit JSON on stdin; for a `human` message prints `Pathly recorded this as
  human message <id>; cite it with cite=<id> when you relay an answer.` and always exits 0.
- Tables: `chief_sessions(run_id PK, project_root, preset, tier, engine, tab_id,
  hook_secret_hash, settings_dir, opened_at, closed_at, close_reason)`,
  `chief_human_messages(id PK, run_id, project_root, kind, text, ts)`,
  `chief_citations(id PK, run_id, message_id UNIQUE, route, target, ts)`;
  `chief_sessions.runs_started INTEGER NOT NULL DEFAULT 0`;
  `comms_messages.binding INTEGER NOT NULL DEFAULT 0`.
- `retrieve_board_context(..., role="")` gains `role`; `board_context_for` and
  `fsm_compose.build_prompt` pass it.

## Migration and compatibility

- All schema changes are additive and idempotent; existing rows get `binding = 0`.
- `/events/runner` and `/events/runs` consumers no longer see `run_token`; no consumer reads it
  there.
- `/db/query`: statements that wrote through `WITH ... INSERT|UPDATE|DELETE` now fail with 400.
- `/comms/edit`: the edited row's `author_*` becomes the editor's (`none` for Studio until RRP-2b).
- Studio receives `submit: false` before it honours it (round two); until then nothing opens a
  chief except a direct `POST /chief/open`.
- `/comms/supersede` and `/comms/delete` on a binding row, and `supersedes` naming one, are
  refused for every caller but the chief (no binding rows exist before this plan).
- Hydration stores `binding = 0`, skips rows for another board and labels every hydrated stamp
  `legacy`, so a fresh clone loses standing orders and the chief posts them again.
- Otherwise no change for callers that send no chief token.

## Risks

- A chief that drops its token is anonymous, and anonymous loopback callers can still do
  everything until RRP-2b. Mitigation: the claude chief pre-allows only `Bash(pathly *)`, so any
  other command asks the human; the `pathly` CLI (round two) refuses to run without the token.
- UserPromptSubmit also fires on scheduled tasks, background subagents reporting back and
  messages from other sessions (docs: hooks), so a cross-session message from a worker's claude
  session would be recorded as human. Mitigation: `Agent`, `CronCreate` and `Workflow` are denied
  in the chief settings; the cross-session case stays an open question in map.md.
- The hook secret file is readable by the user's processes. Mitigation: mode 0600, a `Read` deny
  rule for `~/.pathly/**`, deleted when the session closes.
- The chief session is not billed in round one: Studio sets `PATHLY_GATE_BILLED` for runner tabs
  and the result callback has no `RunnerState` for the chief's topic. Following the user's
decision for cost, round two gets a ticket that bills it (`map.md` § Round two).
- A user-set codex `shell_environment_policy.ignore_default_excludes = false` strips
  `PATHLY_RUN_TOKEN` from codex's commands (docs: codex config). Mitigation: the `pathly` CLI
  (round two) reports the missing variable by name.

- A chief that cites an unrelated later message word for word still passes ticket 10; the rule
  binds the words, not the intent. Mitigation: the user sees every relayed answer on the board;
  the acceptance test documents the limit.
- Prompt injection: board text, artifacts and agent output reach the chief, and an Operator
  chief can start runs. Mitigation: the built-in texts tell it to take orders only from the user
  in the tab (ticket 17), and the ceilings in ticket 15 bound the damage.
- Studio today auto-submits every pasted prompt and ignores `submit: false`
  (`studio/src/main/ipc/terminal/promptInjector.ts`), so a chief opened before round two starts at
  once with its style prompt; the hook still stores that first submission as `style_prompt`.
  A chief tab also takes one of Studio's 5 interactive slots.
- Any local process can post `/runner/terminal/result` for the chief's run id and close the
  session. That only ends the chief early (fail closed).

## UI

Built in round two; shown here so both rounds share one picture. The launcher is the shared
`PromptActionConfig` (engine from `CliSelect`, styles from `useMergedPresets`, "Save current as
prompt" from `PresetAddRow`), hosted by the Chief button; no new picker (the brief's `Decided:`
line).

### Topbar — Chief button with two items waiting

```
┌──────────────────────────────────────────────┐
│ Pathly   my-app ▾        [ Chief (2) ] [ ⚙ ] │
└──────────────────────────────────────────────┘
```

### Chief launcher — open, Operator selected

```
┌────────────────────────────────────────────┐
│  Chief                                     │
├────────────────────────────────────────────┤
│  Engine   [ claude              ▾ ]        │
│  Style    [ Operator            ▾ ]        │
│           Status · Planner · ✓ Operator    │
│  Tier: Operator — starts and stops runs,   │
│  answers agents, posts decisions           │
│  ┌──────────────────────────────────────┐  │
│  │ You are the Pathly chief. Use only   │  │
│  │ the `pathly` commands. Start with    │  │
│  │ `pathly inbox` and `pathly overview`.│  │
│  └──────────────────────────────────────┘  │
│  [ Save current as prompt ]                │
│  2 waiting: 1 agent question, 1 decision   │
│                     [ Reset ] [ Open ]     │
└────────────────────────────────────────────┘
```

### Chief launcher — a chief is already open

```
┌────────────────────────────────────────────┐
│  Chief · Operator is open (claude)         │
│               [ Show tab ] [ Close chief ] │
└────────────────────────────────────────────┘
```

### Chief launcher — no CLI engine found

```
┌────────────────────────────────────────────┐
│  No CLI engine found (claude, codex).      │
│  Using the HQ assistant instead.           │
│                              [ Open HQ ]   │
└────────────────────────────────────────────┘
```
