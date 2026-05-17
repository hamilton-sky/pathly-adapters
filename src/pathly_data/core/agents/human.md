# human

This is the canonical entry point for human feedback gates in Pathly FSMs.

When an FSM workflow encounters a blocking question that requires human input, decision-making,
or confirmation — feedback is routed to the `human` agent. This agent does not execute
automatically; instead, it blocks the workflow and surfaces a question to the user.

## Responsibility

You (the human operator) are responsible for:
- Reading the question or context provided in the feedback file
- Making a decision or providing required input
- Confirming the resolution to the FSM to continue

## Workflow

1. The FSM writes `HUMAN_QUESTIONS.md` to `<storage_path>/feedback/`
2. The orchestrator prints the question to the user and pauses
3. You review the question and provide a response
4. You confirm the response to the orchestrator
5. The orchestrator deletes `HUMAN_QUESTIONS.md` and continues

## When human routing is needed

Human feedback is triggered when:
- A builder or reviewer needs clarification on requirements
- A decision point requires domain knowledge that agents lack
- The system has reached a confidence threshold requiring approval
- An edge case or ambiguity cannot be resolved programmatically
