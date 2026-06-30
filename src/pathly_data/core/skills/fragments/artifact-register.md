## Registering your output artifact

After you finish your stage work, register your primary output artifact. This runs **after**
you write your output file and **before** your completion report — so `AGENT_DONE` stays your
final act. This step never advances the pipeline: no `/complete_stage`, no `next-action`, no
FSM transition. The supervisor advances the flow once your artifact exists.

**1. Write your output file.** Write your stage's primary artifact to exactly `<out_path>`
(the runner injected this path — do not choose your own). This is the file the gate checks.

**2. Append one line to the artifact ledger.** Append a single JSON line to
`<feature_path>/ARTIFACTS.jsonl` (create the file if absent, append-only — never rewrite it):
```bash
python3 -c '
import json, os, sys, time
rec = {"role": "<agent>", "path": "<out_path>", "type": "md",
       "title": "<short title>", "summary": "<one-line gloss>", "ts": time.time()}
p = "<feature_path>/ARTIFACTS.jsonl"
with open(p, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec) + "\n")
'
```

**3. Advisory board POST (skip-if-down).** Mirror the artifact to the board so other agents
see it without opening the file. If the server is unreachable (connection refused / non-200),
skip silently — `ARTIFACTS.jsonl` and the file are the source of truth.
```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{"feature": "<feature>", "from": "<agent>", "type": "artifact", "board": "feature",
       "scope": "<feature>", "text": "<1-2 sentence description>",
       "artifact_path": "<out_path>", "artifact_type": "md"}'
```
