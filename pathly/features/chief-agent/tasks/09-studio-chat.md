# Make the Studio chat talk to the chief, and delegate POST /chat to it when enabled

Type: task
Status: open
Blocked by: 04
Test first: yes

The human's front door (SPEC.md § B G1, story US-1).

- Studio: add `studio/src/renderer/src/components/HQ/ChiefThread/` (one component folder, CSS
  module, `tokens.css` only) and `studio/src/renderer/src/store/chiefApi.ts`
  (`postChiefMessage`, `getChiefThread` through the existing `apiFetch`). It renders the thread,
  sends messages, and appends `CHIEF_MESSAGE` / `CHIEF_REPLY` SSE events live. Board ids in a
  reply (`goal`, `task`, run ids) render as links to the existing board views. `useHQ.tsx` is 874
  lines and may only shrink: mount the new component from the HQ panel with at most a call site,
  no new logic in `useHQ.tsx`.
- Server: `POST /chat` (`chat_agent.py`) forwards to `POST /chief/message` when `chief.enabled`
  is true and returns `{delegated: "chief", id}`; when false, the regex path answers as today.
- Docs in the same commit: `studio/CLAUDE.md` (the chief thread), `README.md` and
  `docs/WHAT_IS_PATHLY.md` (the chief as the front door, led by the headless-board framing).

## Not in this ticket

- A chief settings screen: `chief.enabled` and the caps are set through `PUT /db/settings` for now.

## Done when

- `studio/node_modules/.bin/vitest run --root studio src/renderer/src/components/HQ/ChiefThread`
  passes (renders a thread, sends a message, appends an SSE reply, links a goal id).
- `python -m pytest tests/http_api/test_chat_agent.py -q` passes, including new cases: enabled →
  delegated to the chief and a thread row exists; disabled → regex answer unchanged.
- `useHQ.tsx` is not longer than 874 lines; both Studio typechecks exit 0.

```check
$ studio/node_modules/.bin/vitest run --root studio src/renderer/src/components/HQ/ChiefThread
exit 0
$ python -m pytest tests/http_api/test_chat_agent.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "print('useHQ ok:', sum(1 for _ in open('studio/src/renderer/src/components/HQ/useHQ.tsx',encoding='utf-8')) <= 874)"
prints useHQ ok: True
```

## Reference

- `studio/CLAUDE.md` (components, CSS modules, IPC pattern); `components/HQ/`
- `studio/src/renderer/src/lib/config.ts` (`apiFetch`); `chat_agent.py`, `blueprints/ops/chat.py`
- Ticket 04's Answer

## Answer
