"""Planner/builder pipeline — Track D (whetstone research fork).

A two-model pipeline that deliberately departs from luxe's mono-only loop:

  Pass 1 (PLAN):  a single constrained-decoding call against the planner model
                  (e.g. Gemma-3-27B-it) emits a JSON plan. No tools, no loop.
  Pass 2 (BUILD): the unchanged mono loop (single.py:run_single → loop.py:
                  run_agent) executes against the builder model (e.g.
                  Qwen3-Coder-Next-80B) with the FULL tool surface, with the
                  plan injected as advisory scaffolding via run_single's
                  `extra_task_context` (same insertion point as the .sdd block).

Design invariants (pinned in agents/agents.sdd):
  * No forked loop — the builder pass is run_single, unchanged.
  * Planner prompt is registry-bound (`prompts.get("planner")`), never inlined.
  * Fail CLOSED — an unparseable / failed plan yields no injected context, so
    the builder runs exactly as mono.
  * Memory lifecycle is explicit and sequential by default: the census math
    (planner ~16 GB + 80B builder ~64 GB ≈ 80 GB weights, leaving ~16 GB for
    2×KV under the 96 GB cap) makes co-residency marginal, so the planner is
    unloaded before the builder loads unless `coresident=True` is set for a
    smaller builder pairing.

The return value is the BUILDER's AgentResult, so every downstream consumer in
cli.py (events, citation lint, diff stat) works unchanged — the pipeline is a
drop-in for run_single at the maintain dispatch site.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from whetstone.agents.loop import AgentResult, OnToolEvent
from whetstone.agents.prompts import get as get_prompt
from whetstone.agents.single import _build_sdd_block, run_single
from whetstone.backend import Backend, BackendError
from whetstone.config import RoleConfig
from whetstone.tools.base import ToolCache, ToolDef, ToolFn

logger = logging.getLogger(__name__)

# JSON keys the planner is contracted to emit (see prompts._PLANNER_SYSTEM).
# A parsed plan missing every key is treated as a parse failure (fail closed).
PLAN_KEYS = ("approach", "files_to_inspect", "steps", "verification", "risks")


def _parse_plan(text: str) -> dict[str, Any] | None:
    """Parse the planner's JSON output. Returns the plan dict, or None when the
    output is not usable (fail-closed signal for the caller).

    Tolerates a stray markdown fence around the object (some quants wrap JSON in
    ```json fences despite the response_format constraint), but nothing else.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        # Strip a leading ```json / ``` fence and the trailing ``` if present.
        raw = raw.split("\n", 1)[-1] if "\n" in raw else ""
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]
        raw = raw.strip()
    try:
        plan = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(plan, dict):
        return None
    # Require at least one contracted key — otherwise it's not a plan we can use.
    if not any(k in plan for k in PLAN_KEYS):
        return None
    return plan


def _format_plan_block(plan: dict[str, Any]) -> str:
    """Render a parsed plan as an advisory builder-prompt block.

    Mirrors the CoT framing ("scaffolding, NOT the deliverable") so the builder
    does not treat the plan as a spec to echo. Returns a string with a leading
    "\\n\\n" so it appends cleanly after the .sdd block.
    """
    lines: list[str] = [
        "## Plan (advisory — from the planner model)",
        "A planner model proposed the following approach. Treat it as helpful "
        "scaffolding, NOT a specification: verify it against the actual repo, "
        "deviate when the code disagrees, and do only what the goal requires.",
        "",
    ]
    approach = plan.get("approach")
    if isinstance(approach, str) and approach.strip():
        lines.append(f"Approach: {approach.strip()}")
        lines.append("")

    def _bullets(title: str, key: str) -> None:
        items = plan.get(key)
        if isinstance(items, list) and items:
            lines.append(f"{title}:")
            for it in items:
                lines.append(f"- {str(it).strip()}")
            lines.append("")

    _bullets("Files to inspect", "files_to_inspect")
    _bullets("Suggested steps", "steps")
    _bullets("Verification", "verification")
    _bullets("Risks / edge cases", "risks")
    return "\n\n" + "\n".join(lines).rstrip()


def run_planner_builder(
    planner_backend: Backend,
    planner_role: RoleConfig,
    builder_backend: Backend,
    builder_role: RoleConfig,
    *,
    goal: str,
    task_type: str = "review",
    languages: frozenset[str] | None = None,
    extra_tool_defs: list[ToolDef] | None = None,
    extra_tool_fns: dict[str, ToolFn] | None = None,
    cache: ToolCache | None = None,
    on_tool_event: OnToolEvent | None = None,
    run_id: str | None = None,
    phase: str = "main",
    coresident: bool = False,
    on_planner_event: Callable[[dict[str, Any]], None] | None = None,
) -> AgentResult:
    """Run the planner/builder pipeline end-to-end and return the builder's
    AgentResult (a drop-in for run_single).

    `coresident=False` (default) unloads the planner model and thermal-guards
    the builder before Pass 2 — the safe default under the 96 GB cap with a
    large builder. Set `coresident=True` only for a pairing the memory census
    confirms fits both models + KV simultaneously.

    `on_planner_event`, when supplied, is called once with planner telemetry
    (parsed/steps/wall/tokens/model) so cli.py can append it to the run log.
    """
    plan: dict[str, Any] | None = None
    planner_text = ""
    timing = None
    try:
        variant = get_prompt("planner")
        sdd_block = _build_sdd_block()
        planner_task = (
            f"Task type: {task_type}\n"
            f"Goal: {goal}\n\n"
            f"{variant.task_prefix}"
            f"{sdd_block}"
        )
        resp = planner_backend.chat(
            messages=[
                {"role": "system", "content": variant.system},
                {"role": "user", "content": planner_task},
            ],
            temperature=planner_role.temperature,
            num_ctx=planner_role.num_ctx,
            max_tokens=planner_role.max_tokens_per_turn,
            # Constrained decoding: forces a JSON object and suppresses the
            # thinking-model CoT preamble (same path the reflect verifier uses).
            response_format={"type": "json_object"},
        )
        planner_text = resp.text
        timing = resp.timing
        plan = _parse_plan(planner_text)
    except BackendError as e:
        # Planner unreachable / retries exhausted — fail closed to mono.
        logger.warning("planner pass failed, falling back to mono builder: %s", e)
        plan = None

    if on_planner_event is not None:
        on_planner_event({
            "model": planner_backend.model,
            "parsed": plan is not None,
            "steps": len(plan.get("steps", [])) if isinstance(plan, dict) else 0,
            "planner_wall_s": getattr(timing, "total_s", 0.0) if timing else 0.0,
            "planner_prompt_tokens": getattr(timing, "prompt_tokens", 0) if timing else 0,
            "planner_completion_tokens": getattr(timing, "completion_tokens", 0) if timing else 0,
            "final_text_chars": len(planner_text or ""),
        })

    plan_block = _format_plan_block(plan) if plan is not None else None

    # --- Memory lifecycle: hand the GPU from planner to builder -------------
    # Default sequential handoff (census shows co-residency is marginal for a
    # large builder). Best-effort: unload failures don't abort the build.
    if not coresident and planner_backend.model != builder_backend.model:
        try:
            planner_backend.unload_model(planner_backend.model)
        except Exception as e:  # pragma: no cover - best effort
            logger.warning("planner unload skipped: %s", e)
        try:
            builder_backend.thermal_guard(builder_backend.model)
        except Exception as e:  # pragma: no cover - best effort
            logger.warning("builder thermal_guard skipped: %s", e)

    # --- Pass 2: unchanged mono builder loop with the plan injected ---------
    return run_single(
        builder_backend, builder_role,
        goal=goal,
        task_type=task_type,
        languages=languages,
        extra_tool_defs=extra_tool_defs,
        extra_tool_fns=extra_tool_fns,
        cache=cache,
        on_tool_event=on_tool_event,
        run_id=run_id,
        phase=phase,
        extra_task_context=plan_block,
    )
