## Reading the board before you decompose

Before producing tasks, pull existing board context scoped to this goal. This surfaces
decisions, open questions, and prior research so your task DAG avoids duplication.

```bash
curl -s -X POST http://127.0.0.1:8765/comms/agent-context \
  -H "Content-Type: application/json" \
  -d '{"scope": "$FEATURE", "goal_id": "$GOAL_ID"}'
```

Read the response and:
- Note any open decisions or questions already on the board
- Incorporate existing research (discoveries, artifacts) into your task scope
- Skip redundant tasks the board shows as already done

**Skip-if-down (advisory):** If the comms server is unreachable, proceed without board
context. Do not fail the decompose.
