"""Phase 2 agent-level eval — runs the full agent against EvalSet JSON.

Two test functions:

* ``test_evalset_schema_valid`` — parses every ``*.evalset.json`` to confirm
  the file is a valid ADK ``EvalSet``. Runs by default; no LLM, no agent.
* ``test_agent_eval`` — actually invokes the agent end-to-end via
  ``AgentEvaluator.evaluate_eval_set`` and scores against ``test_config.json``.
  Skipped unless ``PAVE_REAL_LLM=1`` is set, because each run consumes LLM
  tokens and is non-deterministic.

Add new cases by dropping a ``<name>.evalset.json`` into ``eval_sets/``.
Authoring tip: run ``adk web .`` and use the eval UI to record a session,
then save it to this directory.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).parent
_EVAL_SETS_DIR = _EVAL_DIR / "eval_sets"
_CONFIG_PATH = _EVAL_DIR / "test_config.json"


def _eval_set_files() -> list[Path]:
    if not _EVAL_SETS_DIR.exists():
        return []
    return sorted(_EVAL_SETS_DIR.glob("*.evalset.json"))


def _case_id(p: Path) -> str:
    return p.stem.replace(".evalset", "")


@pytest.mark.parametrize(
    "eval_set_file",
    _eval_set_files(),
    ids=[_case_id(p) for p in _eval_set_files()],
)
def test_evalset_schema_valid(eval_set_file: Path) -> None:
    """Each *.evalset.json parses into ADK's EvalSet without ValidationError."""
    from google.adk.evaluation.local_eval_sets_manager import load_eval_set_from_file

    eval_set = load_eval_set_from_file(str(eval_set_file), eval_set_file.stem)
    assert eval_set.eval_cases, f"{eval_set_file.name} has no eval_cases"
    for case in eval_set.eval_cases:
        # Each case must have exactly one of conversation / conversation_scenario
        assert (case.conversation is None) != (case.conversation_scenario is None), (
            f"{case.eval_id}: must specify exactly one of conversation/conversation_scenario"
        )


@pytest.mark.skipif(
    os.getenv("PAVE_REAL_LLM") != "1",
    reason="Set PAVE_REAL_LLM=1 to run agent evals (each test consumes LLM tokens).",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "eval_set_file",
    _eval_set_files(),
    ids=[_case_id(p) for p in _eval_set_files()],
)
async def test_agent_eval(eval_set_file: Path) -> None:
    """Run the agent against the EvalSet and assert metrics meet thresholds."""
    from google.adk.evaluation.agent_evaluator import AgentEvaluator
    from google.adk.evaluation.eval_config import get_evaluation_criteria_or_default
    from google.adk.evaluation.local_eval_sets_manager import load_eval_set_from_file

    eval_set = load_eval_set_from_file(str(eval_set_file), eval_set_file.stem)
    eval_config = get_evaluation_criteria_or_default(str(_CONFIG_PATH))

    await AgentEvaluator.evaluate_eval_set(
        agent_module="pave_agent.agent",
        eval_set=eval_set,
        eval_config=eval_config,
        print_detailed_results=True,
    )
