"""The office FX stream is only worth having if something emits on it.

`office.fx` was specced and plumbed end to end (emit helper -> snapshot ring ->
dashboard watcher -> renderer) with only two live emitters, so `speak`, `done`,
`error` and `retry` rendered nothing. These lock in the hooks that feed them.
See docs/design/office-fx-transient-effects.md.
"""

from types import SimpleNamespace

import pytest


@pytest.fixture
def office(monkeypatch):
    """A quiet office: no snapshot writes, no leftover agents."""
    from tools import delegate_tool

    monkeypatch.setattr(delegate_tool, "_write_office_snapshot", lambda: None)
    delegate_tool._active_subagents.clear()
    delegate_tool._main_activities.clear()
    yield delegate_tool
    delegate_tool._active_subagents.clear()
    delegate_tool._main_activities.clear()


def _kinds(record):
    return [entry["kind"] for entry in record.get("fx", [])]


def _of_kind(record, kind):
    return [entry for entry in record.get("fx", []) if entry["kind"] == kind]


def test_delegation_makes_the_parent_speak_the_instruction(office):
    """The hand-off ticket flies; the bubble says what is written on it."""
    parent = {"subagent_id": "sa-parent", "parent_id": None, "kind": "subagent"}
    office._active_subagents["sa-parent"] = parent

    office._register_subagent(
        {
            "subagent_id": "sa-child",
            "parent_id": "sa-parent",
            "kind": "subagent",
            "goal": "Research the client site",
        }
    )

    assert _kinds(parent) == ["handoff", "speak"]
    assert _of_kind(parent, "handoff")[0]["target"] == "sa-child"
    assert _of_kind(parent, "speak")[0]["data"]["text"] == "Research the client site"


def test_delegation_without_a_goal_emits_no_empty_bubble(office):
    parent = {"subagent_id": "sa-parent", "parent_id": None, "kind": "subagent"}
    office._active_subagents["sa-parent"] = parent

    office._register_subagent(
        {"subagent_id": "sa-child", "parent_id": "sa-parent", "goal": "   "}
    )

    assert _kinds(parent) == ["handoff"]


def test_long_goals_are_clipped_to_one_bubble_line(office):
    parent = {"subagent_id": "sa-parent", "parent_id": None, "kind": "subagent"}
    office._active_subagents["sa-parent"] = parent

    office._register_subagent(
        {
            "subagent_id": "sa-child",
            "parent_id": "sa-parent",
            "goal": "Research the client website and\nthen draft three scripts",
        }
    )

    text = _of_kind(parent, "speak")[0]["data"]["text"]
    assert len(text) == office._FX_SPEAK_CHARS
    assert text.endswith("…")
    assert "\n" not in text


def test_completed_delegation_lands_a_check_on_the_parent(office):
    """The child is gone from the very next snapshot, so its ✓ rides the parent."""
    parent = {"subagent_id": "sa-parent", "parent_id": None, "kind": "subagent"}
    office._active_subagents["sa-parent"] = parent
    office._active_subagents["sa-child"] = {
        "subagent_id": "sa-child",
        "parent_id": "sa-parent",
    }

    office._unregister_subagent("sa-child", ok=True, summary="Drafted 3 scripts")

    assert "sa-child" not in office._active_subagents
    assert _kinds(parent) == ["done", "speak"]
    assert _of_kind(parent, "done")[0]["target"] == "sa-child"
    assert _of_kind(parent, "speak")[0]["data"]["text"] == "Drafted 3 scripts"


def test_failed_delegation_lands_an_error_not_a_check(office):
    parent = {"subagent_id": "sa-parent", "parent_id": None, "kind": "subagent"}
    office._active_subagents["sa-parent"] = parent
    office._active_subagents["sa-child"] = {
        "subagent_id": "sa-child",
        "parent_id": "sa-parent",
    }

    office._unregister_subagent("sa-child", ok=False, summary="rate limited")

    assert _of_kind(parent, "error")[0]["target"] == "sa-child"
    assert _of_kind(parent, "done") == []


def test_unregistering_a_root_agent_is_a_no_op(office):
    """No parent to receive the FX, and no crash for the caller."""
    office._active_subagents["sa-root"] = {"subagent_id": "sa-root", "parent_id": None}

    office._unregister_subagent("sa-root", ok=True, summary="done")

    assert "sa-root" not in office._active_subagents


def test_backoff_parks_the_agent_and_flashes_a_retry(office):
    """`waiting` alone only says "is waiting"; the FX says "just got throttled"."""
    agent = SimpleNamespace(model="model-a")
    office.mark_main_turn_start(agent, "some task")
    record = office._main_activities[id(agent)]

    office.note_waiting_activity(agent)

    assert record["status"] == "waiting"
    assert _kinds(record) == ["retry"]
