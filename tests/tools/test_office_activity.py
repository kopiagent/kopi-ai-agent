import json
import os
import time
from types import SimpleNamespace


def test_main_office_activity_is_isolated_per_agent(monkeypatch):
    from tools import delegate_tool

    monkeypatch.setattr(delegate_tool, "_write_office_snapshot", lambda: None)
    delegate_tool._main_activities.clear()
    first = SimpleNamespace(model="model-a")
    second = SimpleNamespace(model="model-b")

    delegate_tool.mark_main_turn_start(first, "first task")
    delegate_tool.mark_main_turn_start(second, "second task")

    records = list(delegate_tool._main_activities.values())
    assert len(records) == 2
    assert len({record["subagent_id"] for record in records}) == 2
    assert {record["kind"] for record in records} == {"main"}

    delegate_tool.mark_main_turn_end(first)
    assert list(delegate_tool._main_activities.values())[0]["goal"] == "second task"
    delegate_tool.mark_main_turn_end(second)


def test_office_turn_wrapper_cleans_up_on_return_and_error(monkeypatch):
    from agent.conversation_loop import _track_office_turn
    from tools import delegate_tool

    events = []
    monkeypatch.setattr(
        delegate_tool,
        "mark_main_turn_start",
        lambda agent, goal="": events.append(("start", agent, goal)),
    )
    monkeypatch.setattr(
        delegate_tool,
        "mark_main_turn_end",
        lambda agent: events.append(("end", agent)),
    )
    agent = object()

    @_track_office_turn
    def succeeds(agent, user_message, *args, **kwargs):
        return "ok"

    @_track_office_turn
    def fails(agent, user_message, *args, **kwargs):
        raise RuntimeError("boom")

    assert succeeds(agent, "raw", persist_user_message="clean") == "ok"
    try:
        fails(agent, "raw")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")

    assert events == [
        ("start", agent, "clean"),
        ("end", agent),
        ("start", agent, "raw"),
        ("end", agent),
    ]

    events.clear()
    assert succeeds(agent, "raw", None, None, None, None, "positional") == "ok"
    assert events == [("start", agent, "positional"), ("end", agent)]


def test_top_level_subagent_is_not_treated_as_stale_main(tmp_path, monkeypatch):
    from kopi_cli import web_server

    office_dir = tmp_path / "office"
    office_dir.mkdir()
    snapshot = {
        "pid": os.getpid(),
        "ts": time.time(),
        "agents": [
            {
                "subagent_id": "sa-top-level",
                "parent_id": None,
                "depth": 0,
                "kind": "subagent",
                "status": "running",
            }
        ],
    }
    (office_dir / f"subagents-{os.getpid()}.json").write_text(
        json.dumps(snapshot), encoding="utf-8"
    )
    monkeypatch.setattr(web_server, "get_kopi_home", lambda: tmp_path)

    agents = web_server._read_office_agents()

    assert [agent["subagent_id"] for agent in agents] == ["sa-top-level"]
