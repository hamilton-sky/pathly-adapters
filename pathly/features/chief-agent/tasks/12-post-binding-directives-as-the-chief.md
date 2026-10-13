# Let the chief post a binding directive, and never edit one in place

Type: task
Status: open
Blocked by: 03, 08, 11
Test first: yes

Add `POST /comms/directives` in a new `blueprints/comms/directives.py` (added to
`blueprints/comms/__init__.py::all_blueprints`), the only write path that sets `binding = 1`.

- Body `{project_root, to_agent, text}`. `to_agent` is `*` or a role name (`^[a-z][a-z0-9_-]{0,39}$`),
  `text` a non-empty string of at most 8 KiB; 400 otherwise.
- Caller: only a live run with role `chief` per `caller_identity(request)`. The chief gate has
  already checked that the session's tier has `decide` and that `project_root` is the session's
  project. Everything else is 403: no token, a builder or any other role's token, and a token-less
  request that carries the server secret (what Studio sends today). This is the brief's pending
  default: the "(or the UI)" path waits for the UI token (RRP-2b), because until then the server
  cannot tell Studio from any local process that reads the server secret file. If the user replaces
  the default, the other option is in map.md § Open questions ("Directives from the UI").
- Write: `db/queries/comms_directives.py::post_directive(conn, scope, to_agent, text, **author)`
  calls `post_message(board="project", scope=scope, from_agent="chief", to_agent=to_agent,
  type="decision", text=text, **author)` and then sets `binding = 1` on that row under
  `_get_write_lock`. `scope` is the project board scope
  (`fsm_compose.resolve_board_scope("project", project_root, "")`), `author` is
  `stamp(caller_identity(request))`. Return 201 `{id}` and broadcast the same `COMMS_UPDATE` that
  `comms_post` sends for a new row, through `sse._broadcast_comms`.
- A directive is replaced with the existing `/comms/supersede`, which the gate maps to `decide`.

Refuse in-place edits: `/comms/edit` on a row with `binding = 1` returns 409
`{"error": "binding directives are superseded, not edited"}` and changes nothing.
`messages_crud.py` is at 382 lines before ticket 03; keep it at or under 400 (put the check in the
db layer, for example a `"binding"` result from `update_message_text`, if the route would grow
too much).

`/comms/post` keeps ignoring a `binding` field in its body; add a test that proves it.

Living docs: `src/pathly_orchestrator/CLAUDE.md` lists `POST /comms/directives` under "Comms
board endpoints" (chief token only) and the edit refusal; the root `CLAUDE.md` comms domain line
names `directives`.

## Not in this ticket

- A path for Studio to post a binding directive: waits for the UI token (RRP-2b), a later plan.
- The `pathly decide --binding` command: round two (map.md § Round two).

## Done when

- `python -m pytest tests/comms_board/test_comms_directives_route.py -q -p no:cacheprovider`
  passes and covers: an operator chief token posts a directive (201) and the row has `binding = 1`,
  `type = "decision"`, `from_agent = "chief"`, `author_role = "chief"`, `author_source = "token"`;
  a planner chief token is 403 (gate); a builder token, a request with no token and no secret, and
  a request with no token and the right `X-Pathly-Secret` are all 403 and store nothing; a bad
  `to_agent` is 400; `/comms/edit` on the directive is 409 and the text is unchanged;
  `/comms/post` with `binding: 1` stores 0; `/comms/supersede` by the operator removes the old
  directive from `get_binding_decisions`.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/comms_board/test_comms_directives_route.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- spec.md § Decisions ("Binding directives", "Who may post a directive"), § Interfaces
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_write.py::comms_post` (broadcast
  shape; read-only)
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py::comms_edit`,
  `comms_supersede`
- `tests/http_api/test_http_server.py` (how tests set `middleware._api_secret`)

## Answer
