"""The chief core, proven end to end (chief-agent 13): the bar of the plan's map.md.

Everything here runs the real thing: the Flask app, the chief gate, the supervisor's spawn path
(``_run_stage_via_terminal``), the board and the prompt composer. Only the machine around the
server is faked: ``SpawnHost`` is a thread reading a queue registered in ``sse._spawn_clients``
(what an ``/events/spawn`` client gets), the part Studio plays, and the chief's claude is never
started, so what the person types in its tab reaches the server through the same route the
chief's hook posts to. One scenario per item of the bar, in the plan's order:

1. open a chief; 2. an operator acts through the API; 3. a status chief only reads; 4. an answer
to an agent cites a human message; 5. a standing order reaches the next builder, reviewer and
tester and only the chief retires it; 6. a run above the ceiling and a call on another project's
run are refused; 7. ``pathly api`` works from the chief's tab; 8. the raw run token stays off
``/events/runner`` and ``/events/runs``.

What this does not prove is a live claude: the chief's own claude is never started (spike 19 part B
is the planned hand run with a real claude). Until it has been run these stay unmeasured: that the
claude chief honours the restricted flags and its two switches, that its hook fires and records
what the person types, that `pathly api` works from inside the tab, that a cited answer reaches a
real waiting agent, that the run limit stops a third run, that the texts lead a real claude to
sensible first commands, and that closing the chief makes its token 401.
"""

from __future__ import annotations

import json
import queue
from urllib.parse import quote

from chief_acceptance_calls import (
    ABOVE,
    ALREADY,
    AS_CHIEF,
    BINDING_REFUSED,
    CITE_ONLY,
    FORMAT_FIRST,
    MAXED,
    NO_DEPS,
    NOT_CITED,
    NOT_IN_PROJECT,
    ONE,
    STAGES,
    WORDS,
    Subscribed,
    ask,
    board_row,
    busy,
    drained,
    in_place,
    opened_with_the_prompt_recorded,
    post_directive,
    post_goal,
    put_setting,
    root_line,
    run_pathly,
    session_state,
    standing_orders,
    start_single_run,
    worker_token,
    writes_of,
)
from chief_acceptance_support import (
    FRAGMENT_PATH,
    TOKEN_HEADER,
    _no_embedding_model,
    _no_watcher_outlives_its_test,
    client,
    db,
    later,
    open_chief,
    other_project,
    project,
    serving,
    session_row,
    spawn_host,
    type_in_tab,
    wait_for,
)

from pathly_orchestrator.http_server import chief_budget

# Numbers of the limits scenarios. The defaults are the module's own, so a changed default moves
# the numbers built from it and not only the assertions.
ONE_RUN = 1  # a run limit of one: the second start of a session is the one refused
CEILING = chief_budget.DEFAULT_CEILING_USD
ABOVE_THE_CEILING = CEILING * 100  # a cost the default ceiling refuses
BELOW_THE_CEILING = CEILING / 2  # a cost it allows
CEILING_THE_PERSON_SETS = ABOVE_THE_CEILING * 2  # lets the refused cost through
CEILING_THE_CHIEF_TRIES = ABOVE_THE_CEILING * 5  # never stored

STYLE = "You are the chief of this project and you run it for the user."
PROMPT = f"---\ntier: operator\nname: custom\n---\n{STYLE}\n"


# -- 1. open ---------------------------------------------------------------------------------


def test_open_pastes_the_style_and_the_fixed_rules_in_a_restricted_interactive_tab(
    client, spawn_host, project
):
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token

    chief = open_chief(client, spawn_host, project, "operator", prompt=PROMPT)

    assert set(chief.answer) == {"run_id", "tab_id", "tier", "engine"}
    assert (chief.answer["tier"], chief.answer["engine"]) == ("operator", "claude")
    tab = chief.tab
    assert (tab["interactive"], tab["submit"]) == (True, False)
    assert tab["cwd"] == str(project)
    assert tab["tab_id"] == tab["run_id"] == chief.run_id

    # What is pasted: the style without its front matter, the fixed rules, the root.
    fragment = FRAGMENT_PATH.read_text(encoding="utf-8").strip()
    prompt = tab["prompt"]
    assert prompt.startswith(f"{STYLE}\n\n{fragment}")
    assert prompt.splitlines()[-1] == root_line(chief)
    assert prompt.splitlines()[-1] == f"Your project root: {project}"
    assert "---" not in prompt.split(fragment, 1)[0]
    assert "tier:" not in prompt.split(fragment, 1)[0]
    # Nothing in it, and nothing in the argv, can be used to call the server.
    assert chief.token not in prompt
    assert chief.token not in " ".join(tab["argv"])

    # claude, restricted, with the session id the server chose and no MCP server.
    argv = tab["argv"]
    assert argv[:2] == ["claude", "--restricted"]
    assert argv[argv.index("--tools") + 1] == "Bash,Read,Glob,Grep"
    assert "--strict-mcp-config" in argv
    assert argv[argv.index("--session-id") + 1] == (
        session_row(chief.run_id)["cli_session_id"]
    )

    # The token is the chief's: the session's run id, the project board, role chief.
    live = resolve_run_token(db(), chief.token)
    assert live is not None
    assert (live["role"], live["run_id"]) == ("chief", chief.run_id)
    assert (live["board"], live["scope"], live["project_root"]) == (
        "project",
        str(project),
        str(project),
    )

    state = client.get("/chief/session", query_string={"project_root": str(project)})
    assert state.get_json()["open"] is True
    assert state.get_json()["run_id"] == chief.run_id
    assert state.get_json()["tier"] == "operator"
    again = client.post(
        "/chief/open",
        json={"project_root": str(project), "engine": "claude", "preset": "operator"},
    )
    assert again.status_code == 409
    assert again.get_json()["run_id"] == chief.run_id


def test_open_without_a_prompt_uses_the_built_in_style_of_the_preset(
    client, spawn_host, project
):
    from pathly_orchestrator.supervisor.chief_presets import BUILT_IN
    from pathly_orchestrator.supervisor.chief_tiers import strip_front_matter

    chief = open_chief(client, spawn_host, project, "status")

    assert chief.answer["tier"] == "status"
    style = strip_front_matter(BUILT_IN["status"]).strip()
    fragment = FRAGMENT_PATH.read_text(encoding="utf-8").strip()
    assert chief.tab["prompt"].startswith(f"{style}\n\n{fragment}")
    assert chief.tab["prompt"].splitlines()[-1] == root_line(chief)
    assert chief.token not in chief.tab["prompt"]


def test_a_preset_with_no_built_in_text_needs_a_prompt(client, spawn_host, project):
    resp = client.post(
        "/chief/open",
        json={"project_root": str(project), "engine": "claude", "preset": "custom"},
    )

    assert resp.status_code == 400
    assert "prompt is required" in resp.get_json()["error"]
    assert spawn_host.tabs == {}


# -- 2. an operator acts through the API -----------------------------------------------------


def test_an_operator_posts_a_goal_and_starts_a_run_through_the_spawn_path(
    client, spawn_host, project
):
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token
    from pathly_orchestrator.supervisor import board_lock

    chief = open_chief(client, spawn_host, project, "operator", prompt=PROMPT)
    root = str(project)

    posted = post_goal(client, chief, root)

    assert posted.status_code == 200, posted.get_data(as_text=True)
    row = (
        db()
        .execute(
            "SELECT board, scope, type, from_agent, author_role, author_run_id,"
            " author_source FROM comms_messages WHERE id=?",
            (posted.get_json()["message_id"],),
        )
        .fetchone()
    )
    assert tuple(row) == (
        "project",
        root,
        "goal",
        "chief",
        "chief",
        chief.run_id,
        "token",
    )

    started = start_single_run(client, chief, root)

    assert started.status_code == 200, started.get_data(as_text=True)
    run_id = started.get_json()["run_id"]
    assert run_id != chief.run_id
    # The supervisor spawned it: a second TERMINAL_SPAWN reached the host, with a token of its
    # own whose role is the worker's, not the chief's.
    worker = spawn_host.worker(run_id)
    assert worker.payload["run_token"] != chief.token
    assert worker.payload["interactive"] is False
    assert worker.payload["cwd"] == root
    assert worker.live is not None
    assert (worker.live["run_id"], worker.live["role"]) == (run_id, "single-agent")
    assert worker.live["role"] != "chief"
    assert worker.live["project_root"] == root

    spawn_host.settle(run_id)
    assert resolve_run_token(db(), worker.payload["run_token"]) is None  # revoked
    assert resolve_run_token(db(), chief.token) is not None  # the chief's is not
    assert board_lock.holder("project", root) is None
    status = (
        db()
        .execute("SELECT status FROM run_history WHERE run_id=?", (run_id,))
        .fetchone()
    )
    assert status is not None and status["status"] == "done"
    counted = client.get("/chief/session", query_string={"project_root": root})
    assert counted.get_json()["runs_started"] == 1


# -- 3. a status chief only reads ------------------------------------------------------------


def test_a_status_chief_reads_the_board_and_is_refused_every_write(
    client, spawn_host, project
):
    root = str(project)
    operator = open_chief(client, spawn_host, project, "operator")
    closed = client.post("/chief/close", json={"project_root": root})
    assert closed.get_json() == {"closed": True}
    gone = client.get(
        "/comms", query_string={"feature": "demo"}, headers=operator.headers
    )
    assert gone.status_code == 401  # the closed chief's token is dead
    killed = wait_for(lambda: spawn_host.kills, "the host to be told to kill the tab")
    assert [(k["run_id"], k["tab_id"]) for k in killed] == [(operator.run_id,) * 2]
    status = open_chief(client, spawn_host, project, "status")
    assert status.answer["tier"] == "status"
    before = db().execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0]

    read = client.get(
        "/comms", query_string={"feature": "demo"}, headers=status.headers
    )

    assert read.status_code == 200, read.get_data(as_text=True)
    assert read.get_json() == []
    for path, body, action in writes_of(root):
        resp = client.post(path, json=body, headers=status.headers)
        assert resp.status_code == 403, (path, resp.get_data(as_text=True))
        assert resp.get_json() == {
            "error": f"a status chief may not {action}",
            "action": action,
            "tier": "status",
            "allowed": ["read"],
        }
    after = db().execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0]
    assert after == before
    assert spawn_host.workers == {}


def test_a_planner_chief_plans_but_neither_decides_nor_runs(
    client, spawn_host, project
):
    planner = open_chief(client, spawn_host, project, "planner")
    root = str(project)

    assert planner.answer["tier"] == "planner"
    assert post_goal(client, planner, root).status_code == 200
    for path, body, action in writes_of(root):
        if action in ("post", "plan"):
            continue
        resp = client.post(path, json=body, headers=planner.headers)
        assert resp.status_code == 403, (path, resp.get_data(as_text=True))
        assert resp.get_json()["error"] == f"a planner chief may not {action}"
        assert resp.get_json()["allowed"] == ["plan", "post", "read"]
    assert spawn_host.workers == {}


# -- 4. an answer to an agent cites a human message ------------------------------------------


def test_an_agent_question_stays_pending_until_the_chief_cites_the_persons_words(
    client, spawn_host, project, ask
):
    chief = opened_with_the_prompt_recorded(client, spawn_host, project)
    before = type_in_tab(client, chief, "a remark made before the question")["id"]
    later()
    first, second = ask("topic-a", ONE), ask("topic-b", ONE)
    typed = type_in_tab(client, chief, WORDS)["id"]
    # A prompt a task notification delivered: recorded after the question, but never citable.
    relayed = type_in_tab(
        client, chief, "<task-notification>ok</task-notification>", True
    )

    def answer(topic, **body):
        return client.post(
            "/runner/agent-answer", json={"topic": topic, **body}, headers=chief.headers
        )

    for refused, error in (
        (answer("topic-a"), NOT_CITED),
        (answer("topic-a", cite=before), NOT_CITED),
        (answer("topic-a", cite=relayed["id"]), NOT_CITED),
        (answer("topic-a", cite=typed, answer="CSV"), CITE_ONLY),
    ):
        assert refused.status_code == 403, refused.get_data(as_text=True)
        assert refused.get_json()["error"] == error
        assert refused.get_json()["action"] == "answer"
        assert first.still_waiting()  # the question is still pending

    ok = answer("topic-a", cite=typed)

    assert ok.status_code == 200, ok.get_data(as_text=True)
    # Pathly relayed the person's own text, not anything the chief sent.
    assert first.answer() == WORDS
    reused = answer("topic-b", cite=typed)  # typed after both questions, but spent
    assert reused.status_code == 403
    assert reused.get_json()["error"] == ALREADY
    assert second.still_waiting()
    # The limit, stated: Pathly guarantees the words are the person's and were relayed once.
    # It does not guarantee the person meant them for this question; the chief chose that.
    # Had the person's message been meant for "topic-b", the chief could still have cited it
    # there instead.
    assert db().execute("SELECT COUNT(*) FROM chief_citations").fetchone()[0] == 1


def test_a_human_escalation_is_acknowledged_only_with_a_cite_recorded_after_it(
    client, spawn_host, project
):
    chief = opened_with_the_prompt_recorded(client, spawn_host, project)
    before = type_in_tab(client, chief, "a remark made before the escalation")["id"]
    later()
    posted = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "board": "feature",
            "scope": "demo",
            "from": "builder",
            "to": "human",
            "type": "escalation",
            "text": "May I drop the staging table?",
        },
    )
    assert posted.status_code == 200, posted.get_data(as_text=True)
    escalation = posted.get_json()["message_id"]
    later()

    def acknowledge(**body):
        body = {"message_id": escalation, "agent": "chief", **body}
        return client.post("/comms/acknowledge", json=body, headers=chief.headers)

    def acknowledged_by():
        row = db().execute(
            "SELECT acknowledged_by FROM comms_messages WHERE id=?", (escalation,)
        )
        return json.loads(row.fetchone()["acknowledged_by"] or "[]")

    for refused in (acknowledge(), acknowledge(cite=before)):
        assert refused.status_code == 403, refused.get_data(as_text=True)
        assert refused.get_json()["error"] == NOT_CITED
        assert refused.get_json()["action"] == "answer"
        assert acknowledged_by() == []
    after = type_in_tab(client, chief, "yes, drop it")["id"]
    # The name is stored on the row: a chief that signed as the person would make the board
    # read as if the person had closed the gate. Refused, and the message is not spent.
    signed = acknowledge(cite=after, agent="human")
    assert signed.status_code == 403, signed.get_data(as_text=True)
    assert signed.get_json()["error"] == AS_CHIEF
    assert acknowledged_by() == []

    ok = acknowledge(cite=after)

    assert ok.status_code == 200, ok.get_data(as_text=True)
    assert acknowledged_by() == ["chief"]
    again = acknowledge(cite=after)
    assert again.status_code == 403 and again.get_json()["error"] == ALREADY


# -- 5. a standing order reaches the next builder, reviewer and tester ------------------------


def test_an_acknowledged_standing_order_reaches_the_next_builder_reviewer_and_tester(
    client, spawn_host, project
):
    chief = open_chief(client, spawn_host, project, "operator")
    root = str(project)
    everyone = post_directive(client, chief, root, NO_DEPS)
    post_directive(client, chief, root, FORMAT_FIRST, to_agent="builder")

    acknowledged = client.post(
        "/comms/acknowledge",
        json={"message_id": everyone, "agent": "chief"},
        headers=chief.headers,
    )

    assert acknowledged.status_code == 200, acknowledged.get_data(as_text=True)
    row = board_row(everyone)
    assert (row["status"], row["binding"]) == ("active", 1)  # no longer "pending"
    assert (row["author_role"], row["author_run_id"]) == ("chief", chief.run_id)
    orders = standing_orders(project)
    for stage in STAGES:
        assert NO_DEPS in orders[stage], stage
    assert FORMAT_FIRST in orders["BUILDING"]
    assert FORMAT_FIRST not in orders["REVIEWING"] + orders["TESTING"]


def test_no_one_but_the_chief_retires_a_standing_order(client, spawn_host, project):
    chief = open_chief(client, spawn_host, project, "operator")
    root = str(project)
    order = post_directive(client, chief, root, NO_DEPS)
    planner = worker_token("planner", root)

    # An agent of the project board posts a decision that names the order in `supersedes`.
    over = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "board": "project",
            "scope": root,
            "from": "planner",
            "type": "decision",
            "text": "Use whatever dependencies you like.",
            "supersedes": [order],
        },
        headers={TOKEN_HEADER: planner},
    )
    assert over.status_code == 200, over.get_data(as_text=True)
    newer = over.get_json()["message_id"]  # the post itself is stored
    assert over.get_json()["superseded"] == []
    assert over.get_json()["supersede_skipped"] == [{"id": order, "reason": "binding"}]
    # A caller with no token supersedes it directly.
    direct = client.post("/comms/supersede", json={"old_id": order, "new_id": newer})
    assert direct.status_code == 403
    assert direct.get_json() == {"error": BINDING_REFUSED}
    # Nobody deletes it, the chief included (the gate lists no delete for a chief).
    for headers in ({}, {TOKEN_HEADER: planner}, chief.headers):
        gone = client.post(
            "/comms/delete", json={"message_id": order, "force": True}, headers=headers
        )
        assert gone.status_code == 403, gone.get_data(as_text=True)
    assert in_place(order)
    assert NO_DEPS in standing_orders(project)["BUILDING"]

    # The chief supersedes it with a new order, and the next prompts carry the new one.
    replacement = post_directive(client, chief, root, FORMAT_FIRST)
    retired = client.post(
        "/comms/supersede",
        json={"old_id": order, "new_id": replacement},
        headers=chief.headers,
    )

    assert retired.status_code == 200, retired.get_data(as_text=True)
    assert board_row(order)["superseded_by"] == replacement
    for stage, text in standing_orders(project).items():
        assert FORMAT_FIRST in text and NO_DEPS not in text, stage


# -- 6. limits: the cost ceiling, the run limit and another project's run --------------------


def test_a_start_above_the_cost_ceiling_is_refused_and_the_chief_cannot_raise_it(
    client, spawn_host, project, busy
):
    chief = open_chief(client, spawn_host, project, "operator")
    root = str(project)
    busy("demo")  # a flow start on "demo" gets past the gate and is then a route 409

    def start(cost):
        body = {"kind": "flow", "scope": "demo", "flow": "team", "project_root": root}
        return client.post(
            "/runs", json={**body, "max_cost_usd": cost}, headers=chief.headers
        )

    over = start(ABOVE_THE_CEILING)

    assert over.status_code == 403, over.get_data(as_text=True)
    assert over.get_json()["error"] == ABOVE
    assert over.get_json()["ceiling"] == chief_budget.DEFAULT_CEILING_USD
    # The chief cannot change its own ceiling: the settings are not its to write. It sends a value
    # that is not the stored one, so the ceiling it reads back shows nothing was written.
    own = client.put(
        f"/db/settings/{chief_budget.CEILING_KEY}",
        json={"value": CEILING_THE_CHIEF_TRIES},
        headers=chief.headers,
    )
    assert own.status_code == 403 and "allowed" in own.get_json()
    state = session_state(client, root)
    assert state["max_cost_usd_per_run"] == chief_budget.DEFAULT_CEILING_USD
    # The ceiling is the reason: a lower cost passes the gate (the route's 409 is "busy"), and
    # so does the refused cost once the person raised the ceiling.
    assert start(BELOW_THE_CEILING).status_code == 409
    raised = put_setting(client, chief_budget.CEILING_KEY, CEILING_THE_PERSON_SETS)
    assert raised.status_code == 200, raised.get_data(as_text=True)
    assert session_state(client, root)["max_cost_usd_per_run"] == (
        CEILING_THE_PERSON_SETS
    )
    assert start(ABOVE_THE_CEILING).status_code == 409
    assert (
        session_state(client, root)["runs_started"] == 0
    )  # a refused start costs no slot
    assert spawn_host.workers == {}


def test_a_session_cannot_start_more_runs_than_its_limit(client, spawn_host, project):
    chief = open_chief(client, spawn_host, project, "operator")
    root = str(project)
    assert put_setting(client, chief_budget.LIMIT_KEY, ONE_RUN).status_code == 200
    first = start_single_run(client, chief, root)
    assert first.status_code == 200, first.get_data(as_text=True)
    spawn_host.settle(first.get_json()["run_id"])

    second = start_single_run(client, chief, root)

    assert second.status_code == 403, second.get_data(as_text=True)
    assert second.get_json()["error"] == MAXED
    assert second.get_json()["limit"] == ONE_RUN
    assert len(spawn_host.workers) == 1  # nothing was spawned for the second
    state = session_state(client, root)
    assert (state["runs_started"], state["max_runs_per_session"]) == (ONE_RUN, ONE_RUN)


def test_a_chief_cannot_control_a_run_of_another_project(
    client, spawn_host, project, other_project
):
    from pathly_orchestrator.supervisor import board_lock

    chief = open_chief(client, spawn_host, project, "operator")
    root, elsewhere = str(project), str(other_project)
    spawn_host.hold = True  # both runs stay alive until the test lets them go
    # The person starts a run in the other project: no run token, no chief.
    theirs = client.post(
        "/runs",
        json={
            "kind": "single",
            "board": "project",
            "scope": elsewhere,
            "project_root": elsewhere,
        },
    )
    assert theirs.status_code == 200, theirs.get_data(as_text=True)
    other_run = theirs.get_json()["run_id"]
    spawn_host.worker(other_run)

    for verb in ("stop", "abort", "pause"):
        resp = client.post(
            f"/runs/{other_run}/{verb}",
            json={"project_root": root},
            headers=chief.headers,
        )
        assert resp.status_code == 403, (verb, resp.get_data(as_text=True))
        assert resp.get_json()["error"] == NOT_IN_PROJECT
    assert board_lock.holder("project", elsewhere) == other_run  # still running
    assert spawn_host.kills == []

    # The same call on a run of the chief's own project is allowed.
    own = start_single_run(client, chief, root)
    assert own.status_code == 200, own.get_data(as_text=True)
    own_run = own.get_json()["run_id"]
    spawn_host.worker(own_run)
    stopped = client.post(
        f"/runs/{own_run}/stop", json={"project_root": root}, headers=chief.headers
    )
    assert stopped.status_code == 200, stopped.get_data(as_text=True)
    assert stopped.get_json()["stopped"] is True
    spawn_host.settle(own_run)
    assert [k["run_id"] for k in spawn_host.kills] == [own_run]
    assert board_lock.holder("project", elsewhere) == other_run
    spawn_host.finish(other_run)
    spawn_host.settle(other_run)


# -- 7. pathly api works from the chief's tab ------------------------------------------------


def test_pathly_api_reads_the_session_with_the_chiefs_token(
    client, spawn_host, project, tmp_path
):
    chief = open_chief(client, spawn_host, project, "operator")
    root = str(project)
    target = "/chief/session?project_root=" + quote(root, safe="/")
    goal = {"from": "chief", "type": "goal", "text": "From the tab", "board": "project"}
    goal.update(scope=root, feature="project", project_root=root)
    new_limit = json.dumps({"value": chief_budget.DEFAULT_RUN_LIMIT + 5})

    with serving() as port:

        def run(*args):
            return run_pathly(list(args), chief.token, port, tmp_path)

        session = run("GET", target)
        posted = run("POST", "/comms/post", json.dumps(goal))
        refused = run("PUT", f"/db/settings/{chief_budget.LIMIT_KEY}", new_limit)

    assert session.returncode == 0, session.stderr
    state = json.loads(session.stdout)
    assert (state["open"], state["tier"], state["run_id"]) == (
        True,
        "operator",
        chief.run_id,
    )
    assert state["runs_started"] == 0
    # The command sent the token: the board stamps the post as this chief's.
    assert posted.returncode == 0, posted.stderr
    stamp = board_row(json.loads(posted.stdout)["message_id"])
    assert (stamp["author_role"], stamp["author_run_id"]) == ("chief", chief.run_id)
    assert stamp["author_source"] == "token"
    # A call the gate refuses exits 1 and prints the gate's own answer.
    assert refused.returncode == 1
    assert json.loads(refused.stdout)["error"] == "the chief may not call this route"
    assert (
        session_state(client, root)["max_runs_per_session"]
        == chief_budget.DEFAULT_RUN_LIMIT
    )
    for done in (session, posted, refused):
        assert chief.token not in done.stdout + done.stderr


# -- 8. the raw token stays off /events/runner and /events/runs ------------------------------


def test_the_raw_run_token_is_on_the_spawn_stream_and_on_no_other(
    client, spawn_host, project, monkeypatch
):
    from pathly_orchestrator.http_server import sse

    on_topics, on_runs = queue.Queue(), queue.Queue()
    # A client listening on every topic and on every run: the ids do not exist yet.
    monkeypatch.setattr(sse, "_runner_clients", Subscribed(on_topics))
    monkeypatch.setattr(sse, "_run_clients", Subscribed(on_runs))
    chief = open_chief(client, spawn_host, project, "operator")
    root = str(project)
    started = start_single_run(client, chief, root)
    assert started.status_code == 200, started.get_data(as_text=True)
    run_id = started.get_json()["run_id"]
    worker = spawn_host.worker(run_id)
    spawn_host.settle(run_id)

    # /events/spawn (the host's queue) carried both tokens: the stream needs no credentials
    # until the UI token exists, so a client subscribed in time reads them.
    assert spawn_host.tabs[chief.run_id]["run_token"] == chief.token
    assert worker.payload["run_token"] and worker.live is not None
    full = {chief.run_id: spawn_host.tab(chief.run_id), run_id: worker.payload}
    for stream, raws in (
        ("/events/runner", drained(on_topics)),
        ("/events/runs", drained(on_runs)),
    ):
        spawns = [p for p in map(json.loads, raws) if p.get("type") == "TERMINAL_SPAWN"]
        assert {p["run_id"] for p in spawns} == {chief.run_id, run_id}, stream
        for spawn in spawns:
            assert "run_token" not in spawn, stream
            # Otherwise the same event: only the credential is missing.
            expected = {
                k: v for k, v in full[spawn["run_id"]].items() if k != "run_token"
            }
            assert spawn == expected, stream
        assert {p["topic"] for p in spawns} == {f"chief:{chief.run_id}", root}
        text = "".join(raws)
        assert (
            chief.token not in text and worker.payload["run_token"] not in text
        ), stream
