# Keep the hook secret out of the chief's reach

Type: task
Status: open
Blocked by: 01
Test first: yes

Spike S2. A chief's session folder `~/.pathly/chief/<run_id>/` (`supervisor/chief_session.py::_write_session_folder`)
holds `hook_secret`, the secret the `UserPromptSubmit` hook sends with each prompt it records as
typed by the person. A chief that reads it could post a forged "human" message and cite it as the
person's words. `claude_settings` denies `Read(~/.pathly/**)` only; the chief also has `Glob` and
`Grep` (`CLAUDE_TOOLS`), and `Bash(pathly *)` is allowed.

Close the three ways in that remain after ticket 01:

1. Deny `Grep(~/.pathly/**)` and `Glob(~/.pathly/**)` in `_CLAUDE_DENY`, next to the `Read` rule.
2. `pathly api` reads a body from standard input when the body argument is `-`
   (`chief_cli.py::_body_text`), so `pathly api POST /comms/post - < ~/.pathly/chief/<id>/hook_secret`
   could post the file if claude matches `Bash(pathly *)` on a command with a redirect. Add
   `Bash(pathly *<*)` and `Bash(pathly *$(*)` (command substitution) to the deny list. Deny rules
   win over allow rules in claude's settings.
3. The server: `POST /comms/post` and `POST /comms/answer` from a chief token refuse (400) a body
   whose text contains the session's hook secret. The server holds only the hash
   (`chief_sessions.hook_secret_hash`), so hash each 43-character URL-safe base64 run in the
   text (`secrets.token_urlsafe(32)`'s length) and compare; keep it in a new small module next to
   `http_server/chief_cite.py`. This is the guarantee; the deny rules are the first line.

Record in the Answer which of the three a real claude would hit first; it is not measured here.

## Not in this ticket

- Moving the secret out of the user's home or changing how the hook authenticates: round two if
  ticket 09's re-measure shows a way around these rules.
- Run tokens in stored text: ticket 03.

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_secret_reach.py tests/http_api/test_chief_secret_in_body.py -q -p no:cacheprovider`
  passes and covers: the settings deny `Read`, `Grep` and `Glob` on `~/.pathly/**` and the two
  redirect and substitution forms; a chief-token post or answer whose text
  holds the secret is 400 and stores nothing; a body without it is unaffected.
- All existing chief tests still pass.

```check
$ python -m pytest tests/runner_supervisor/test_chief_secret_reach.py tests/http_api/test_chief_secret_in_body.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api -q -p no:cacheprovider -k chief
exit 0
```

## Reference

- spike19-part-b-report.md § Surprises ("can likely read its own hook_secret")
- `src/pathly_orchestrator/runner/chief_argv.py`, `src/pathly_orchestrator/chief_cli.py`,
  `src/pathly_orchestrator/supervisor/chief_session.py`, `src/pathly_orchestrator/http_server/chief_cite.py`

## Answer
