"""Round two of the autopilot, proven end to end (chief-autopilot-round-two 12): the plan's bar.

Agents answer agents, and only the person's questions reach the person. Everything runs the real
thing: the Flask app with its run-token guard, consult guard and chief gate, the consult router
(``POST /comms/post``'s ``after_request`` hook), ``consult_run`` and its read-only window, the
goal executors (``single`` through drain-dag, ``loop`` through the FSM's ``goal-loop`` flow, run
in process), the board and the database. Only the machine around the server is faked:
``AgentHost`` plays Studio's spawn host and each spawn's agent process (round one's), and
``autopilot_round_two_support.Agents`` picks the agent: a task's agent asks the architect with its
run token, a ``consult-`` spawn's agent writes its ``AGENT_DONE`` with the summary each test
chooses. The story, in the ticket's order:

1. a ``loop`` task asks the architect: one consult run answers, the router posts the answer, and
   the task runs again as ``sched-<task>#2`` in the same run with the answer, which succeeds;
2. a ``single`` run's drain-dag agent asks and leaves its task unfinished: one consult answers,
   the task is released with ``answered_questions``, and the next run finishes it;
3. an architect that answers ``ANSWER: USER <why>`` hands the question to the person: the task
   is parked and the chief's notices show the consult ``to_person``, one waiting for the person;
4. a fourth routed question of one task goes to the person with no consult spawn;
5. a consult that edits a source file is withheld: no answer, an escalation lists the file;
6. the parked loop run of step 3 reads ``failed``/``waiting_for_answer`` and ``GET /runs`` lists
   its consult as ``kind: consult``;
7. a planner run's decompose post of a task with no check block is 422 and stores nothing.

What this does not prove is a live claude or codex following ``planning/consult-answer``: the
person re-measures one consult on their machine (map Open questions).
"""

from __future__ import annotations

import pytest
from autopilot_acceptance_support import (
    ANSWER_HEADING,
    WAITING,
    agent_host,
    chief_post,
    drain_dag_finishes,
    ended,
    git_project,
    run_detail,
    start_goal,
    task_row,
)
from autopilot_round_two_support import (
    CONSULT_PREFIX,
    Agents,
    consult_says,
    consults_ended,
    drain_dag_asks_role,
    invocations,
    loop_task_asks_role,
    message,
    planner_posts,
    replies,
    route_ended,
    route_of,
    task_waits_on,
)
from chief_acceptance_support import (
    _no_embedding_model,
    _no_watcher_outlives_its_test,
    client,
    db,
    open_chief,
    paste_prompt,
    project,
    wait_for,
)

QUESTION = "Should the parser stream the rows or read the whole file?"
ADVICE = "Stream the rows: the files reach a gigabyte."
WHY_USER = "the file sizes are the person's call"
CHECK = "```check\n$ python -m pytest tests/test_parser.py -q\nexit 0\n```"


@pytest.fixture(autouse=True)
def _consults_end(agent_host):
    """Every consult thread ends inside its test, while the spawn host still listens."""
    yield
    consults_ended()


def _loop_goal(client, chief, project, text: str) -> tuple[str, str]:
    """A ``loop`` goal of one task in a git project (the loop's proof gates and the consult's
    read-only window read its diff)."""
    from pathly_orchestrator.db.queries.app_settings import set_setting

    root = str(project)
    src = project / "src"
    src.mkdir(exist_ok=True)
    (src / "parser.py").write_text("ROWS = []\n", encoding="utf-8")
    git_project(project)
    set_setting(db(), "code_context.backend", "off")
    goal = chief_post(client, chief, root, type="goal", text=text, executor="loop")
    task = chief_post(
        client, chief, root, type="task", goal_id=goal, text="Write the parser."
    )
    return goal, task


def _notices(client, chief, root: str) -> dict[str, dict]:
    resp = client.get(
        "/chief/notices", query_string={"project_root": root}, headers=chief.headers
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return {n["run_id"]: n for n in resp.get_json()["notices"]}


def _asked(spawns: list[dict]) -> str:
    """The question the first task spawn posted (the only one to the architect)."""
    rows = db().execute(
        "SELECT id FROM comms_messages WHERE type='question' AND author_run_id=?",
        (spawns[0]["run_id"],),
    )
    found = [r["id"] for r in rows.fetchall()]
    assert len(found) == 1, found
    return found[0]


# -- 1. a loop task's question is answered by one consult, and the task runs again -----------------


def test_a_loop_tasks_question_is_answered_by_a_consult_and_the_task_runs_again(
    client, agent_host, project
):
    root = str(project)
    chief = open_chief(client, agent_host, project, "operator")
    paste_prompt(client, chief)
    goal, task = _loop_goal(client, chief, project, "Ship the parser")
    tasks: list[dict] = []
    agents = Agents(
        loop_task_asks_role(agent_host.client, root, QUESTION, tasks),
        consult_says(agent_host.client, f"ANSWER: {ADVICE}"),
    )
    agent_host.agent = agents

    run = start_goal(client, chief, root, goal)

    assert ended(run) == "done"
    question = _asked(tasks)
    assert [s["run_id"] for s in tasks] == [f"sched-{task}#1", f"sched-{task}#2"]
    # Exactly one consult run answered it, billed once as its own category.
    assert len(agents.consults) == 1
    consult = agents.consults[0]
    assert consult["run_id"].startswith(CONSULT_PREFIX)
    assert consult["category"] == "consult"
    route = route_ended(question)
    assert (route["status"], route["consult_run_id"]) == ("answered", consult["run_id"])
    # The router posted the answer, from the architect, as a reply to the question.
    answers = replies(question, "answer")
    assert len(answers) == 1
    assert (answers[0]["from_agent"], answers[0]["text"]) == ("architect", ADVICE)
    assert answers[0]["author_run_id"] == consult["run_id"]
    # The task ran again in the same run, with the question and its answer in its prompt.
    prompt = tasks[1]["prompt"]
    block = prompt[prompt.index(ANSWER_HEADING) :]
    assert QUESTION in block and ADVICE in block
    assert task_row(task)["task_status"] == "done"
    assert run_detail(client, run)["error"] is None
    assert invocations(consult["run_id"]) == [
        {"agent_role": "architect", "category": "consult"}
    ]


# -- 2. a single run's unfinished task gets its answer and the next run finishes it ---------------


def test_a_single_runs_question_is_answered_and_the_next_run_finishes_the_task(
    client, agent_host, project
):
    root = str(project)
    chief = open_chief(client, agent_host, project, "operator")
    paste_prompt(client, chief)
    goal = chief_post(client, chief, root, type="goal", text="Ship the parser")
    task = chief_post(
        client, chief, root, type="task", goal_id=goal, text="Write the parser."
    )
    asked: dict = {}
    agents = Agents(
        drain_dag_asks_role(agent_host.client, root, goal, asked, [QUESTION]),
        consult_says(agent_host.client, f"ANSWER: {ADVICE}"),
    )
    agent_host.agent = agents

    first = start_goal(client, chief, root, goal)

    assert ended(first) == "error"
    assert asked["run_id"] == first
    question = asked["questions"][0]
    route = route_ended(question)
    assert len(agents.consults) == 1
    assert (route["status"], route["consult_run_id"]) == (
        "answered",
        agents.consults[0]["run_id"],
    )
    assert [a["from_agent"] for a in replies(question, "answer")] == ["architect"]
    # The answer reached the task: ready again, whether it came before or after the run settled.
    assert run_detail(client, first)["error"] in ("answer_ready", WAITING)
    wait_for(lambda: task_row(task)["task_status"] == "pending", "the task's release")

    finished: dict = {}
    agent_host.agent = drain_dag_finishes(agent_host.client, root, goal, finished)
    second = start_goal(client, chief, root, goal)

    assert ended(second) == "done"
    assert finished["task"]["id"] == task
    assert finished["task"]["answered_questions"] == [
        {"question": QUESTION, "answer": ADVICE}
    ]
    assert task_row(task)["task_status"] == "done"
    assert run_detail(client, second)["outcome"] == "success"


# -- 3 and 6. an architect hands the question to the person; the run waits for the person ---------


def test_an_answer_user_hands_the_question_to_the_person_and_parks_the_loop_run(
    client, agent_host, project
):
    root = str(project)
    chief = open_chief(client, agent_host, project, "operator")
    paste_prompt(client, chief)
    goal, task = _loop_goal(client, chief, project, "Ship the parser")
    tasks: list[dict] = []
    agents = Agents(
        loop_task_asks_role(agent_host.client, root, QUESTION, tasks),
        consult_says(agent_host.client, f"ANSWER: USER {WHY_USER}"),
    )
    agent_host.agent = agents

    run = start_goal(client, chief, root, goal)

    # 3. The question is the person's now; the task is parked on it; no answer was posted.
    assert ended(run) == "error"
    question = _asked(tasks)
    assert [s["run_id"] for s in tasks] == [f"sched-{task}#1"]
    assert len(agents.consults) == 1
    consult = agents.consults[0]["run_id"]
    route = route_ended(question)
    assert (route["status"], route["consult_run_id"]) == ("to_person", consult)
    assert message(question)["to_agent"] == "human"
    assert replies(question, "answer") == []
    assert any(WHY_USER in r["text"] for r in replies(question, "status"))
    assert task_waits_on(task) == question
    notice = _notices(client, chief, root)[run]
    assert notice["waiting_for_person"] == 1
    assert [(c["consult_run_id"], c["status"]) for c in notice["consults"]] == [
        (consult, "to_person")
    ]

    # 6. The run reads failed, waiting for the answer; the consult lists as its own kind.
    detail = run_detail(client, run)
    assert (detail["outcome"], detail["error"]) == ("failed", WAITING)
    listed = client.get("/runs", query_string={"project_root": root})
    assert listed.status_code == 200, listed.get_data(as_text=True)
    kinds = {r["run_id"]: r["kind"] for r in listed.get_json()}
    assert kinds[consult] == "consult"
    assert kinds[run] == "loop"


# -- 4. a task's fourth routed question goes to the person, with no consult -----------------------


def test_a_tasks_fourth_role_question_goes_to_the_person_with_no_consult(
    client, agent_host, project
):
    root = str(project)
    chief = open_chief(client, agent_host, project, "operator")
    paste_prompt(client, chief)
    goal = chief_post(client, chief, root, type="goal", text="Ship the parser")
    task = chief_post(
        client, chief, root, type="task", goal_id=goal, text="Write the parser."
    )
    asked: dict = {}
    texts = [f"{QUESTION} (part {n})" for n in range(1, 5)]
    agents = Agents(
        drain_dag_asks_role(agent_host.client, root, goal, asked, texts),
        consult_says(agent_host.client, f"ANSWER: {ADVICE}"),
    )
    agent_host.agent = agents

    run = start_goal(client, chief, root, goal)

    assert ended(run) == "error"
    *routed, fourth = asked["questions"]
    for question in routed:
        assert route_ended(question)["status"] == "answered", question
    consults_ended()
    assert len(agents.consults) == 3
    assert {route_of(q)["consult_run_id"] for q in routed} == {
        c["run_id"] for c in agents.consults
    }
    assert not any(fourth in c["prompt"] for c in agents.consults)
    route = route_of(fourth)
    assert (route["status"], route["consult_run_id"]) == ("to_person", None)
    assert "limit (3)" in route["reason"]
    assert message(fourth)["to_agent"] == "human"
    assert replies(fourth, "answer") == []
    # The three answers are in, and the task still waits: on the person's question.
    row = task_row(task)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"].startswith(f"{WAITING}:") and fourth in row["fail_reason"]
    assert run_detail(client, run)["error"] == WAITING


# -- 5. a consult that edits a source file is withheld ---------------------------------------------


def test_a_consult_that_edits_a_source_file_is_withheld_and_the_task_waits_for_the_person(
    client, agent_host, project
):
    root = str(project)
    chief = open_chief(client, agent_host, project, "operator")
    paste_prompt(client, chief)
    goal, task = _loop_goal(client, chief, project, "Ship the parser")
    tasks: list[dict] = []
    agents = Agents(
        loop_task_asks_role(agent_host.client, root, QUESTION, tasks),
        consult_says(
            agent_host.client, f"ANSWER: {ADVICE}", edit=project / "src" / "parser.py"
        ),
    )
    agent_host.agent = agents

    run = start_goal(client, chief, root, goal)

    assert ended(run) == "error"
    question = _asked(tasks)
    assert len(agents.consults) == 1
    route = route_ended(question)
    assert route["status"] == "withheld"
    assert "src/parser.py" in route["reason"]
    assert replies(question, "answer") == []
    escalations = replies(question, "escalation")
    assert len(escalations) == 1
    assert escalations[0]["to_agent"] == "human"
    assert "src/parser.py" in escalations[0]["text"]
    assert message(question)["to_agent"] == "human"
    assert [s["run_id"] for s in tasks] == [f"sched-{task}#1"]
    assert task_waits_on(task) == question
    assert run_detail(client, run)["error"] == WAITING


# -- 7. a planner cannot post a task with no check ------------------------------------------------


def test_a_planner_runs_task_with_no_check_is_422_and_stores_nothing(
    client, agent_host, project
):
    root = str(project)
    chief = open_chief(client, agent_host, project, "operator")
    paste_prompt(client, chief)
    goal = chief_post(client, chief, root, type="goal", text="Ship the parser")
    unchecked = "Write the parser, with no check."
    checked = f"Write the parser tests.\n\n{CHECK}"
    seen: dict = {}
    agent_host.agent = Agents(
        planner_posts(agent_host.client, root, goal, [unchecked, checked], seen),
        consult_says(agent_host.client, "ANSWER: none expected"),
    )

    resp = client.post(
        "/comms/goals/decompose",
        json={"goal_id": goal, "mode": "planner", "project_root": root},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    wait_for(lambda: seen.get("posts"), "the planner's posts")
    ended(seen["run_id"])

    (refused, refused_body), (stored, stored_body) = seen["posts"]
    assert refused == 422, refused_body
    assert refused_body["task"] == unchecked
    assert stored == 200, stored_body
    tasks = db().execute(
        "SELECT text FROM comms_messages WHERE type='task' AND goal_id=?", (goal,)
    )
    assert [r["text"] for r in tasks.fetchall()] == [checked]
