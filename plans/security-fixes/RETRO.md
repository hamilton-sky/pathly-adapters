# Retrospective — security-fixes

## What went well?

- **Clean two-conversation split**: Separating code fixes (Conversation 1) from docs/config (Conversation 2) allowed focused scope — each conversation had a single, clear deliverable without scope creep.
- **Surgical, acceptance-criteria-driven specs**: The CONVERSATION_PROMPTS.md gave exact code locations and snippets, reducing ambiguity and rework during implementation.
- **Acceptance criteria caught edge cases**: Story 3b's explicit test case ("Content-Length: not-a-number causes return None") ensured error handling was not just present but correctly silent.

## What was surprising or required correction?

- **Story 2: Path-traversal guard scope**: The initial prompt noted that `target = dest / name` was only computed inside `if not dry_run`, requiring the implementer to move or duplicate assignment logic — this was not obvious from reading the acceptance criteria alone.
- **Story 6: SECURITY.md wording iteration**: The Risk / Mitigation / Recommendation format required careful phrasing across two reviewer cycles to avoid contradictions (e.g. "dropped and the server loop continues" vs. actual terminate-on-None behavior).
- **Story 3b over-specification**: Acceptance criteria required both "return None without raising" AND "server process terminates cleanly" — the second is a consequence of the first and muddied intent; redundant criteria added confusion during testing.
- **Story 6 over-specification**: Planner added "fix commit / version" requirement to SECURITY.md criteria that didn't match the existing doc style, requiring two story corrections during the test stage.

## What would we do differently next time?

- **Review acceptance criteria before writing conversation prompts**: A brief pass to spot criteria that are redundant or imply implementation detail before prompting the conversation.
- **Document expected rework**: If a feature is known to need architect or reviewer loops, call that out upfront so it's not treated as a surprise.
- **Pair security story criteria with explicit failure cases**: For security features, always include at least one explicit failure-mode test case in acceptance criteria — it prevents silent-mode assumptions.
- **Separate "how" from "what" in docs stories**: Story 6 mixed document structure ("Risk / Mitigation format") with content ("explain these two vectors"). Future docs stories should spec content as acceptance criteria and leave format to the conversation prompt.
