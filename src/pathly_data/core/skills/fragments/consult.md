---

---
## Consult a peer — get advice from another role

You are not alone in the pipeline. When you are blocked on something another ROLE owns — the
"what / why" (po), the stories or acceptance criteria (planner), the design / contracts (architect),
the UX (designer), the test strategy (tester), or a second opinion on the diff (reviewer) — you may
**consult** that role instead of guessing. A consult is advice only; it never silently advances the
pipeline or edits another role's artifacts.

**To consult, post a board question addressed to the role** so the human sees the exchange and the
answer threads onto the board:

```
POST http://127.0.0.1:8765/comms/post
{ "feature": "<feature>", "board": "<board>", "scope": "<feature>", "from": "<your role>",
  "to": "<role>", "type": "question", "text": "<ONE bounded question — and the assumption you will proceed on>" }
```
Send `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` on that call.

Who owns what:

| Ask… | for |
|---|---|
| po | scope, intent, success criteria — "is this the right thing to build?" |
| planner | story breakdown, acceptance criteria, ordering, rigor |
| architect | design, layers, contracts, migrations, rollback |
| designer | UX, component shape, visual + interaction states |
| tester | verification strategy, coverage, the gaps you can't see |
| reviewer | likely violations, diff quality, contract risk (advisory) |

Rules:
- Ask exactly ONE bounded question, and state the fallback assumption you will proceed on. **Never
  block** waiting for a reply — the answer comes back asynchronously.
- A question to a role is answered by a consult run of that role that Pathly starts itself,
  usually within minutes. What happens next depends on how you are running:
  - **A loop task** (`execute-task`): Pathly holds your task when you end and runs it again with
    the answer, so finish this attempt on your fallback assumption.
  - **`drain-dag`**: when the answer decides how to build the task, post the question, leave that
    task unfinished (do not complete or fail it) and go on with the other ready tasks; Pathly
    parks it until the answer comes, and its next run reads the answer. Otherwise complete it on
    your fallback.
  - **A team stage**: the answer is advice on the board. If you need the specialist to CHANGE an
    artifact (not just advise), write the matching `feedback/<TYPE>.md` instead — see the Feedback
    protocol — and the FSM routes them to resolve it before the pipeline advances.
- Do not answer another agent's question yourself, even one addressed to your role: a consult run
  does.
