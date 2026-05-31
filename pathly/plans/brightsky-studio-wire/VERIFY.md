RESULT: PASS

## Verification

- `npm run typecheck` in `studio` passed.
- `python -m pytest -c %TEMP%\pytest-minimal-pathly.ini tests/test_chat_agent.py` passed with `2 passed`.

## Notes

- The current working tree already contains the Brightsky/Pathly Studio wiring for context forwarding, thinking metadata, tool bridging, and reconnect behavior.
