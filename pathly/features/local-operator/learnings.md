# Learnings: local-worker-adapter

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.
- [02] To run an action exactly as a human click would, dispatch to the existing route in-process (`current_app.test_client().open(...)`): loopback + no Origin passes the secret middleware, and the route's own refusals/broadcasts come for free.
- [02] node-llama-cpp 3.22 function params: every object property is required (`required` is ignored); an optional arg is a bare `enum` that includes `null` (or `type: ["string","null"]`).
- [06] Test basenames must be unique across `tests/*/` — `test_acceptance.py` already exists in hq_copilot, so the operator bar lives in `test_operator_acceptance.py`.
- [06] The function handler's reply sets the answer's voice: Qwen3 echoes it. Word it to the user ("you"), not about "the user".
- [06] Headless real-model check without Electron: import node-llama-cpp from `studio/node_modules` by file URL in a scratch .mjs, build the turn in Python over a read-only sqlite connection (`file:…?mode=ro`, patch `db.connection.get_db`).
- [06] Deep mode + function calls: Qwen3 can end the answer with a bare `</think>` as plain text — strip think tags from answer chunks in main; thought segments carry the real reasoning.
- [06] "I restarted Studio" may not mean the main process restarted: on macOS closing the window keeps the app (and its server) alive; check process start times before testing main/server changes.
