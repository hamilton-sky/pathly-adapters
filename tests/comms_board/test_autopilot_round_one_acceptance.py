"""Round one of the autopilot, proven end to end (chief-autopilot 09): the bar of the plan's map.md.

A claude chief in the Operator style, left alone with a goal, runs it safely. Everything runs the
real thing: the Flask app with its run-token guard and chief gate, the supervisor's spawn path, the
goal executors (``single`` through ``start_board_run`` and drain-dag, ``loop`` through the FSM's
``goal-loop`` flow, run in process), the board and the database. Only the machine around the server
is faked: ``AgentHost`` plays Studio's spawn host and each worker spawn's agent process, which makes
its calls with its own run token and reports its exit through ``/runner/terminal/result``; the
chief's claude is never started, so what the person types reaches the server through the chief
hook's own route. The story, in the ticket's order:

1. an Operator chief opens in ``dontAsk`` mode, unable to read ``~/.pathly`` or outside its project;
2. through its token it posts a goal and a task and starts the goal (``single``); the agent claims
   with drain-dag's literal body, asks its human, prints its token and exits unfinished;
3. the claim named the run, the run failed ``waiting_for_answer``, the task is ``blocked`` and no
   stored row holds the raw token;
4. ``GET /chief/notices`` lists the run with one question waiting;
5. the person answers in the tab, the chief relays it with its cite, the goal runs again and the
   agent finishes the task with the answer in its ready-task row;
6. a ``loop`` goal parks the same way and resumes under ``sched-<task>#2`` with the answer;
7. a body holding the hook secret is 400, a revoked token is 401, and a chief's ``team`` flow runs
   headless and lists as ``kind: flow``.

What this does not prove is a live claude: spike question 1 (does ``dontAsk`` deny what the
settings leave unsaid, in a real tab) is re-measured by the person on their machine.
"""

from __future__ import annotations

import json

from autopilot_acceptance_support import (
    ANSWER_HEADING,
    WAITING,
    agent_host,
    chief_post,
    drain_dag_asks,
    drain_dag_finishes,
    ended,
    git_project,
    invocations_of,
    loop_task_asks,
    rows_holding,
    run_detail,
    start_goal,
    task_row,
)
from chief_acceptance_support import (
    TOKEN_HEADER,
    _no_embedding_model,
    _no_watcher_outlives_its_test,
    client,
    db,
    open_chief,
    paste_prompt,
    project,
    type_in_tab,
    wait_for,
)

QUESTION = "Should the export write CSV or JSON?"
WORDS = "CSV, with the header row"


def _notices(client, chief, root: str) -> list[dict]:
    resp = client.get(
        "/chief/notices", query_string={"project_root": root}, headers=chief.headers
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["notices"]


def _answer_with_cite(client, chief, question_id: str) -> None:
    """The person answers in the tab; the chief relays it with the message's cite."""
    cite = type_in_tab(client, chief, WORDS)["id"]
    resp = client.post(
        "/comms/answer",
        json={"question_id": question_id, "cite": cite},
        headers=chief.headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)


# -- 1. an Operator chief that cannot be talked past its settings ----------------------------------


def test_an_operator_chief_opens_in_dont_ask_mode_and_cannot_read_the_pathly_home(
    client, agent_host, project
):
    chief = open_chief(client, agent_host, project, "operator")

    argv = chief.tab["argv"]
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    settings_path = argv[argv.index("--settings") + 1]
    with open(settings_path, encoding="utf-8") as fh:
        permissions = json.load(fh)["permissions"]
    for tool in ("Read", "Grep", "Glob"):
        assert f"{tool}(~/.pathly/**)" in permissions["deny"], tool
    assert permissions["blockReadsOutsideWorkingDirectories"] is True
    assert permissions["allow"] == ["Bash(pathly *)"]


# -- 2 to 5. a single goal asks, parks, is answered and finishes -----------------------------------


def test_a_single_goal_parks_on_its_question_and_finishes_after_the_cited_answer(
    client, agent_host, project
):
    root = str(project)
    chief = open_chief(client, agent_host, project, "operator")
    paste_prompt(client, chief)
    goal = chief_post(client, chief, root, type="goal", text="Ship the CSV export")
    task = chief_post(
        client, chief, root, type="task", goal_id=goal, text="Write the exporter."
    )
    assert task_row(task)["task_status"] == "pending"

    # 2. The goal starts with the default executor; its agent asks and exits unfinished.
    asked: dict = {}
    agent_host.agent = drain_dag_asks(agent_host.client, root, goal, asked, QUESTION)
    first = start_goal(client, chief, root, goal)

    # 3. The claim named the run; the run failed waiting; the task waits; no token is stored.
    assert ended(first) == "error"
    assert asked["run_id"] == first
    assert asked["claim"]["claimed"] is True
    assert asked["claimed_by"] == first
    detail = run_detail(client, first)
    assert (detail["outcome"], detail["error"]) == ("failed", WAITING)
    row = task_row(task)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"] == f"{WAITING}:{asked['question']}"
    assert rows_holding(asked["token"]) == []
    # The token reached the store and was redacted there, not lost on the way.
    assert rows_holding("PATHLY_RUN_TOKEN: [run token]")

    # 4. The chief's notices list the run with its one question.
    notices = {n["run_id"]: n for n in _notices(client, chief, root)}
    assert notices[first]["status"] == "error"
    assert notices[first]["error"] == WAITING
    assert notices[first]["open_questions"] == 1

    # 5. The person answers; the chief relays it; the goal runs again and finishes.
    _answer_with_cite(client, chief, asked["question"])
    assert task_row(task)["task_status"] == "pending"
    finished: dict = {}
    agent_host.agent = drain_dag_finishes(agent_host.client, root, goal, finished)
    second = start_goal(client, chief, root, goal)

    assert ended(second) == "done"
    assert finished["task"]["id"] == task
    assert finished["task"]["answered_questions"] == [
        {"question": QUESTION, "answer": WORDS}
    ]
    assert task_row(task)["task_status"] == "done"
    assert run_detail(client, second)["outcome"] == "success"
    notices = {n["run_id"]: n for n in _notices(client, chief, root)}
    assert notices[second]["status"] == "done"
    assert notices[second]["open_questions"] == 0


# -- 6. a loop goal parks the same way and resumes with the answer ---------------------------------


def test_a_loop_goal_parks_on_its_question_and_resumes_with_the_answer(
    client, agent_host, project
):
    from pathly_orchestrator.db.queries.app_settings import set_setting

    root = str(project)
    git_project(project)
    set_setting(db(), "code_context.backend", "off")
    chief = open_chief(client, agent_host, project, "operator")
    paste_prompt(client, chief)
    goal = chief_post(
        client, chief, root, type="goal", text="Ship the parser", executor="loop"
    )
    task = chief_post(
        client, chief, root, type="task", goal_id=goal, text="Write the parser."
    )
    spawns: list = []
    agent_host.agent = loop_task_asks(agent_host.client, root, QUESTION, spawns)

    first = start_goal(client, chief, root, goal)

    assert ended(first) == "error"
    assert [s["run_id"] for s in spawns] == [f"sched-{task}#1"]
    status = client.get("/runner/status", query_string={"topic": spawns[0]["topic"]})
    assert status.status_code == 200, status.get_data(as_text=True)
    assert (status.get_json()["run_id"], status.get_json()["error_kind"]) == (
        first,
        WAITING,
    )
    row = task_row(task)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"].startswith(f"{WAITING}:")
    question = row["fail_reason"].split(":", 1)[1]

    _answer_with_cite(client, chief, question)
    assert task_row(task)["task_status"] == "pending"
    second = start_goal(client, chief, root, goal)

    assert ended(second) == "done"
    assert [s["run_id"] for s in spawns] == [f"sched-{task}#1", f"sched-{task}#2"]
    prompt = spawns[1]["prompt"]
    block = prompt[prompt.index(ANSWER_HEADING) :]
    assert QUESTION in block and WORDS in block
    assert task_row(task)["task_status"] == "done"
    for run_id in (f"sched-{task}#1", f"sched-{task}#2"):
        assert invocations_of(run_id) == 1, run_id


# -- 7. the guards hold, and a chief's flow runs headless ------------------------------------------


def test_a_secret_body_is_400_a_revoked_token_401_and_a_chief_flow_runs_headless(
    client, agent_host, project
):
    from pathly_orchestrator.db.queries.run_tokens import lookup_run_token
    from pathly_orchestrator.supervisor.chief_session import _chief_root

    root = str(project)
    chief = open_chief(client, agent_host, project, "operator")
    secret = (_chief_root() / chief.run_id / "hook_secret").read_text(encoding="utf-8")

    leaked = client.post(
        "/comms/post",
        json={
            "from": "chief",
            "type": "discovery",
            "text": f"the hook secret is {secret}",
            "board": "project",
            "scope": root,
            "feature": "project",
            "project_root": root,
        },
        headers=chief.headers,
    )
    assert leaked.status_code == 400, leaked.get_data(as_text=True)
    assert rows_holding(secret) == []

    # The stage's process stays alive until the chief stops the run.
    agent_host.hold = True
    flow = client.post(
        "/runs",
        json={"kind": "flow", "flow": "team", "scope": "demo", "project_root": root},
        headers=chief.headers,
    )
    assert flow.status_code == 200, flow.get_data(as_text=True)
    assert flow.get_json()["kind"] == "flow"
    run_id = flow.get_json()["run_id"]
    stage = wait_for(lambda: list(agent_host.spawns), "the flow's first spawn")[0]
    assert stage["interactive"] is False
    assert stage["topic"] == "demo"
    listed = client.get("/runs", query_string={"project_root": root})
    assert listed.status_code == 200, listed.get_data(as_text=True)
    assert {r["run_id"]: r["kind"] for r in listed.get_json()}[run_id] == "flow"

    stopped = client.post(
        f"/runs/{run_id}/stop", json={"project_root": root}, headers=chief.headers
    )
    assert stopped.status_code == 200, stopped.get_data(as_text=True)
    assert agent_host.workers[stage["run_id"]].live is not None  # live while it ran
    agent_host.finish(stage["run_id"])
    ended(run_id)
    row = lookup_run_token(db(), stage["run_token"])
    assert row is not None and row["revoked_at"] is not None  # revoked, not unknown
    revoked = client.get(
        "/comms",
        query_string={"feature": "demo"},
        headers={TOKEN_HEADER: stage["run_token"]},
    )
    assert revoked.status_code == 401, revoked.get_data(as_text=True)
    assert revoked.get_json()["error"] == "unknown run token"
