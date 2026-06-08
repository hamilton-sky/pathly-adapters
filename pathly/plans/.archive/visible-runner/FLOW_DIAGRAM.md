# visible-runner — Flow Diagram

## Inter-process interaction (SSE relay + callback)

```
 User                Studio renderer          Electron main          Python supervisor
  │                     │                          │                       │
  │ click Start          │                          │                       │
  │─────────────────────►│  POST /runner/start      │                       │
  │                     │─────────────────────────────────────────────────►│
  │                     │                          │              start_run()
  │                     │                          │              _loop() ──►(thread)
  │                     │                          │                       │
  │                     │◄── SSE: RUNNER_STATUS ──────────────────────────│
  │                     │    {status: "running"}    │              next_action()
  │                     │                          │              _run_stage_via_terminal()
  │                     │◄── SSE: TERMINAL_SPAWN ──────────────────────────│
  │                     │    {tab_id, label, argv}  │                       │
  │                     │                          │              wait started_event
  │  tab opens in UI    │                          │                       │
  │◄────────────────────│  addTab("runner-abc")    │                       │
  │                     │  terminal.spawn(tab_id)──►│                       │
  │                     │                          │  spawn PTY(claude)    │
  │                     │  terminal.write(prompt)──►│                       │
  │                     │                          │  write prompt → PTY   │
  │                     │  POST /terminal/started──────────────────────────►│
  │                     │                          │              event fires
  │                     │                          │              wait result_event
  │                     │          ┌───────────────┤               │
  │  output streams     │          │  PTY running  │               │
  │◄────────────────────│◄─ data ──┤  (xterm live) │               │
  │                     │          │               │               │
  │                     │          └───── exit ────┤               │
  │                     │                          │               │
  │                     │                          │  write DONE ─►xterm (ANSI banner)
  │ "─── DONE ───"      │                          │               │
  │◄────────────────────│◄─ terminal:data ─────────│               │
  │                     │                          │               │
  │                     │  POST /terminal/result ──────────────────►│
  │                     │  {stdout_tail, exit_code} │  parse_result(adapter, stdout_tail)
  │                     │  no JSON parsing here     │  → {cost_usd, session_id}
  │                     │                          │  result_event fires
  │                     │                          │  _loop: complete_stage()
  │                     │◄── SSE: STAGE_CHANGE ───────────────────│
  │  RunnerLogCard       │    {stage: "PLAN"}       │               │
  │  updates            │─ recordStageStart() ─────┤               │
  │                     │                          │               │
  │    (next stage repeats from TERMINAL_SPAWN)    │               │
```

## Abort flow

```
 User                Studio renderer          Electron main          Python supervisor
  │                     │                          │                       │
  │ click Abort          │                          │                       │
  │─────────────────────►│  POST /runner/abort      │                       │
  │                     │─────────────────────────────────────────────────►│
  │                     │                          │              _abort_flag = True
  │                     │                          │              broadcast TERMINAL_SIGNAL
  │                     │◄── SSE: TERMINAL_SIGNAL ─────────────────────────│
  │                     │    {signal: "term"}       │                       │
  │                     │  terminal.kill(tab_id) ──►│                       │
  │                     │                          │  SIGTERM → PTY        │
  │                     │                          │  PTY exits code≠0     │
  │                     │                          │  write "aborted" ────►xterm
  │  "── aborted ──"    │◄─ terminal:data ─────────│                       │
  │◄────────────────────│                          │                       │
  │                     │  POST /terminal/result ──────────────────────────►│
  │                     │    {exit_code: 1}         │                       │
  │                     │                          │              result_event fires
  │                     │                          │              _abort_flag → stop loop
  │                     │◄── SSE: RUNNER_STATUS ───────────────────────────│
  │                     │    {status: "aborted"}    │                       │
```

## Headless fallback (Studio not connected)

```
 Python supervisor                        (no Studio)
       │
  _run_stage_via_terminal()
       │
  broadcast TERMINAL_SPAWN ──────────────► (nobody listening)
       │
  wait started_event[run_id] timeout=5s
       │
  [TIMEOUT]
       │
  broadcast RUNNER_WARNING {reason: "terminal_spawn_timeout"}
       │
  invoke_agent()  ──────────────────────► subprocess.Popen(argv)
       │                                     │
       │ ◄── stdout JSON ───────────────────
       │
  _loop continues normally
```

## DECISION_MENU flow

```
 Python supervisor          Studio renderer
       │                          │
  DECISION_MENU SSE ─────────────►│
                                  │
                                  │  setLogCardExpanded(true)
                                  │  toast("Runner is waiting...")
                                  │  [orange buttons active]
                                  │
                     user clicks Advance / Retry
                                  │
                    POST /runner/advance ────────────────────► supervisor
                                                               resumes _loop
```

## RunnerLogCard state machine

```
  stageLog.length === 0
       │
  [card not rendered]
       │
  recordStageStart() called
       │
  [card renders, sticky, collapsed]
  "0 stages done — STORM"
       │
  stage completes (recordStageEnd)
       │
  "1 stage done — PLAN"   ← updates in place
       │
  DECISION_MENU SSE
       │
  auto-expand
       │
  user dismisses / new stage starts
       │
  collapse
       │
  RUNNER_STATUS {status: done/idle}
       │
  [card un-stickies, becomes static record]
```
