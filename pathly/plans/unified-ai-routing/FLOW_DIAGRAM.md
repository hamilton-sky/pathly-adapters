# Flow Diagram — unified-ai-routing

> Auto-added by rigor escalator: multi-component design.

## Dispatch flow (any AI job)

```
caller ─ runJob(job, selection) ─▶ aiRouter
                                      │
                 selection.type ──────┤
                   'model'            'engine'
                      │                  │
                      ▼                  ▼
              modelManager.runModel   cliEngine: terminal.spawn(buildHeadlessArgv(id, prompt))
                      │                  │
        ┌─────────────┼──────────┐       └─ PTY exit ─▶ result text
        ▼             ▼          ▼
   Ollama HTTP   GGUF (main IPC)  Brightsky WS
        └─────────────┴──────────┴─▶ { text, cost_usd? }
```

## Summary trigger — client-initiated (drop / re-summarize)

```
ArtifactsView ─ pick target (AiTargetSelector) ─▶ aiRouter.runJob({kind:'summarize', text}, selection)
   └─ result ─▶ POST update comms_artifacts.summary ─▶ board refresh (SSE)
```

## Summary trigger — server-initiated (agent attaches artifact mid-run)

```
agent attaches artifact ─▶ server emits SUMMARY_REQUEST (runner SSE / board signal)
                                   │  (server runs NO inference, NO CLI subprocess)
                                   ▼
                       Studio client subscribed? ──no──▶ filename-only (best-effort, deferred)
                                   │ yes
                                   ▼
                       client: aiRouter.runJob(...) ─▶ POST comms_artifacts.summary back
```

## Reachability boundary
- Server can reach: Ollama HTTP only.
- Client-only transports: GGUF (Electron main), Brightsky (renderer WS).
- ∴ all summarization executes client-side via the Router; the server only *requests* it.
