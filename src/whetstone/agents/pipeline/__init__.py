"""Multi-model pipeline package — whetstone's one sanctioned divergence from
luxe's mono-only architecture (see src/whetstone/whetstone.sdd and
src/whetstone/agents/agents.sdd).

Currently houses the Track D planner/builder split. Swarm/micro/phased remain
forbidden; anything here must reuse the unchanged mono loop (loop.py:run_agent
via single.py:run_single) so tool-surface parity is structural, not re-derived.
"""

from whetstone.agents.pipeline.planner_builder import run_planner_builder

__all__ = ["run_planner_builder"]
