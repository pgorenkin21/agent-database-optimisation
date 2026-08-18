"""Parallel agent coordination (Phase 2).

Exports are resolved lazily (PEP 562) so that importing a leaf submodule such as
``src.coord.replica_schedule`` does not eagerly pull in ``parallel`` (which
imports ``src.agent.loop``). That eager chain created a circular import
(agent.loop -> coord/__init__ -> parallel -> agent.loop) that broke importing
the agent loop as a first import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.coord.parallel import ParallelRunResult, run_parallel_agents
    from src.coord.policies import CoordinationPolicy, select_replica

__all__ = [
    "CoordinationPolicy",
    "ParallelRunResult",
    "run_parallel_agents",
    "select_replica",
]

_LAZY = {
    "ParallelRunResult": "src.coord.parallel",
    "run_parallel_agents": "src.coord.parallel",
    "CoordinationPolicy": "src.coord.policies",
    "select_replica": "src.coord.policies",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, name)
