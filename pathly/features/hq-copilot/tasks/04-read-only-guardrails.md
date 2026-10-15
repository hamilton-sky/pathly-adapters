# Enforce HQ's read-only guardrails

Type: task
Status: resolved
Blocked by: 01
Test first: yes

HQ must be safe by construction, not by the model's good mood. Two
guarantees, both tested without invoking a real model:

1. **The model gets no tools, ever.** Add an assertion (not a comment)
   at the HQ model-invocation site in `chat_agent.py`: the tool list /
   function-calling config passed to the local runtime must be empty.
   If a future change passes tools, HQ fails loudly at startup or call
   time — whichever the runtime allows — rather than silently gaining
   hands. Name the exact call site in the Answer.
2. **Action requests get the refusal redirect.** Codify ticket 01's
   refusal text as a constant (`HQ_READONLY_REDIRECT`) next to the
   system prompt. Add a lightweight server-side pre-check in
   `build_hq_prompt`'s caller: if the user message matches the action
   patterns ("start", "stop", "restart", "pause", "resume",
   "retry", "answer", "approve" + a run/goal/question noun — keep
   the pattern list in one place, easy to extend), HQ replies with the
   redirect *without consulting the model at all*. This is defense in
   depth: the system prompt says it, and the pre-check guarantees it
   even when the small model would have complied.

   Advisory questions ("should I stop the builder?") are NOT matched:
   they go to the model, which may discuss but not act.

## Not in this ticket

- The chief's acting surface: chief-agent tickets 04/08. HQ's redirect
  names the chief chat; it does not implement any chief behavior.
- Prompt-injection hardening beyond the delimiter + data-not-instructions
  rule: spec.md § Risks records it as accepted residual risk.

## Done when

- `python -m pytest tests/hq_copilot/test_guardrails.py -q -p no:cacheprovider` passes and covers: the invocation-site assertion fails if a non-empty tool list is passed (test by calling the guarded wrapper with a stub tool list); each action pattern ("stop the run", "restart the builder", "answer the question", "approve it") returns the redirect text with zero model invocations (assert via a counting stub); advisory phrasing ("should I stop the builder?") reaches the model stub.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/hq_copilot/test_guardrails.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Stories ("Safe by construction"), § Design (Decisions:
  "No tools for the model, ever")
- `src/pathly_orchestrator/chat_agent.py` (the HQ invocation site)

## Answer

Implemented 2026-10-14 in `chat_agent.py` (HQ section):

1. **No tools, ever.** `HQ_TOOL_SCHEMAS: tuple = ()` is the single
   source of truth; `_assert_no_hq_tools()` runs at the top of
   `build_hq_prompt` and raises `AssertionError` if the tuple is ever
   non-empty — fails loudly at call time, not silently. Named call
   site: `build_hq_prompt` (the HQ seam in `chat_agent.py`). Note: the
   real model invocation is Studio's `llm:chat` IPC (ticket 03
   finding) — ticket 06 must keep it tool-free for HQ; this assertion
   is the server-side tripwire.
2. **Refusal redirect.** `HQ_READONLY_REDIRECT` codifies ticket 01's
   text ("I can't start/stop/answer anything — that's the chief's
   job" + chief-chat pointer). `hq_refusal_redirect(msg)` matches
   verb (start|stop|restart|pause|resume|retry|answer|approve) +
   noun (run|goal|question|builder|planner|stage|build|it|this|that)
   with word boundaries (so "started" and "nonstop" don't match);
   `should I|should we` advisory phrasing is carved out and goes to
   the model. `prepare_hq_prompt(msg, board_id)` — build_hq_prompt's
   caller — returns the redirect with zero model contact for action
   requests, else the full prompt. Studio (ticket 06) must call
   `prepare_hq_prompt`, not `build_hq_prompt` directly.

Tests: `tests/hq_copilot/test_guardrails.py` (13 tests: assertion
fails loudly; 6 action phrasings redirect with zero stub calls;
5 non-action/advisory phrasings reach the model stub). Full hq_copilot
dir: 25 passed. `check_file_size.py` exits 0. Full regression
(`tests/comms_board tests/db tests/http_api tests/hq_copilot`): 913
passed, 2 skipped, 2026-10-14 (clean clone at the Mac's commit era,
venv on the assistant's machine).

### Review follow-up 2026-10-14 — imperatives only

The verb-anywhere + noun-anywhere match refused ordinary status questions
("why did the build stop?", "did the planner answer the question?",
"when will the run start?"). `hq_refusal_redirect` now matches a clause
that OPENS with an action verb (after optional politeness, "can you",
"let's", "I want you to") and names a target, checked per clause so "The
builder is stuck. Restart it." is still caught. Verb list gained
rerun/run/launch/abort/cancel/kill/reject/post/edit/delete. The guard now
lives in `hq_prompt.py`; `prepare_hq_turn` (what `POST /hq/prompt` calls)
replaces `prepare_hq_prompt`. Tests: 13 action + 11 non-action phrasings.
