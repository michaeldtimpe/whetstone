"""Track D planner/builder pipeline — unit + fail-closed smoke tests.

Runs without a live oMLX: the planner Backend.chat is faked and the builder
run_single is monkeypatched to capture the injected plan context. Covers the
malformed-JSON failure mode the pipeline must fail CLOSED on (pre-promote gate).
"""

from __future__ import annotations

import pytest

from whetstone.agents.loop import AgentResult
from whetstone.agents.pipeline import planner_builder as pb
from whetstone.backend import ChatResponse, GenerationTiming
from whetstone.config import RoleConfig


# --- _parse_plan -----------------------------------------------------------

_VALID = (
    '{"approach": "fix the bug", "files_to_inspect": ["a.py"], '
    '"steps": ["edit a.py"], "verification": ["run tests"], "risks": []}'
)


def test_parse_plan_accepts_valid_object():
    plan = pb._parse_plan(_VALID)
    assert plan is not None
    assert plan["approach"] == "fix the bug"
    assert plan["steps"] == ["edit a.py"]


def test_parse_plan_tolerates_markdown_fence():
    plan = pb._parse_plan("```json\n" + _VALID + "\n```")
    assert plan is not None and plan["files_to_inspect"] == ["a.py"]


@pytest.mark.parametrize("bad", [
    "",
    "   ",
    "not json at all",
    "{broken json",
    "[1, 2, 3]",            # valid JSON but not an object
    '"a string"',           # valid JSON, not an object
    '{"unrelated": "key"}',  # object but no PLAN_KEYS -> not a usable plan
])
def test_parse_plan_fails_closed_on_unusable(bad):
    assert pb._parse_plan(bad) is None


# --- _format_plan_block ----------------------------------------------------

def test_format_plan_block_is_advisory_and_additive():
    block = pb._format_plan_block(pb._parse_plan(_VALID))
    assert block.startswith("\n\n")              # appends cleanly after sdd block
    assert "advisory" in block.lower()
    assert "scaffolding" in block.lower() and "NOT a specification" in block
    assert "fix the bug" in block                # approach surfaced
    assert "- edit a.py" in block                # steps rendered as bullets


# --- run_planner_builder end-to-end (faked backends) -----------------------

class _FakeBackend:
    def __init__(self, model, text):
        self.model = model
        self._text = text
        self.unloaded = False
        self.thermal_guarded = False

    def chat(self, **kwargs):
        # Assert the planner uses constrained decoding (json_object).
        assert kwargs.get("response_format") == {"type": "json_object"}
        return ChatResponse(text=self._text,
                            timing=GenerationTiming(prompt_tokens=10,
                                                    completion_tokens=20,
                                                    total_s=1.5))

    def unload_model(self, model_id):
        self.unloaded = True
        return True

    def thermal_guard(self, model_id, **kwargs):
        self.thermal_guarded = True
        return True


def _patch_builder(monkeypatch):
    """Replace run_single with a capture stub; returns the captured-kwargs dict."""
    captured = {}

    def fake_run_single(backend, role, **kwargs):
        captured["backend_model"] = backend.model
        captured["extra_task_context"] = kwargs.get("extra_task_context")
        return AgentResult(final_text="built", steps=1)

    monkeypatch.setattr(pb, "run_single", fake_run_single)
    return captured


def _roles():
    return RoleConfig(model_key="planner"), RoleConfig(model_key="builder")


def test_valid_plan_is_injected_and_planner_unloaded(monkeypatch):
    captured = _patch_builder(monkeypatch)
    planner_role, builder_role = _roles()
    planner = _FakeBackend("gemma-planner", _VALID)
    builder = _FakeBackend("qwen-builder", "")
    events = []

    res = pb.run_planner_builder(
        planner, planner_role, builder, builder_role,
        goal="fix it", task_type="bugfix",
        on_planner_event=events.append,
    )
    assert res.final_text == "built"
    # Plan injected into the builder pass.
    assert captured["backend_model"] == "qwen-builder"
    assert captured["extra_task_context"] is not None
    assert "fix the bug" in captured["extra_task_context"]
    # Sequential handoff fired (distinct models, coresident=False default).
    assert planner.unloaded and builder.thermal_guarded
    # Planner telemetry surfaced.
    assert events and events[0]["parsed"] is True and events[0]["steps"] == 1


def test_malformed_plan_fails_closed_to_mono(monkeypatch):
    captured = _patch_builder(monkeypatch)
    planner_role, builder_role = _roles()
    planner = _FakeBackend("gemma-planner", "{ this is not valid json")
    builder = _FakeBackend("qwen-builder", "")
    events = []

    res = pb.run_planner_builder(
        planner, planner_role, builder, builder_role,
        goal="fix it", task_type="bugfix",
        on_planner_event=events.append,
    )
    assert res.final_text == "built"
    # Fail CLOSED: no plan injected -> builder runs exactly as mono.
    assert captured["extra_task_context"] is None
    assert events and events[0]["parsed"] is False


def test_coresident_skips_unload(monkeypatch):
    _patch_builder(monkeypatch)
    planner_role, builder_role = _roles()
    planner = _FakeBackend("gemma-planner", _VALID)
    builder = _FakeBackend("qwen-builder", "")

    pb.run_planner_builder(
        planner, planner_role, builder, builder_role,
        goal="fix it", task_type="bugfix", coresident=True,
    )
    # Co-resident pairing keeps both loaded (no handoff).
    assert not planner.unloaded and not builder.thermal_guarded
