"""Tests for production Cohort Scout context-efficiency eval."""

from __future__ import annotations

from mip_jupyter_dev.cohort_scout_eval import EVAL_CASES
from mip_jupyter_dev.cohort_scout_eval import expected_first_guide
from mip_jupyter_dev.cohort_scout_eval import measure_base_instructions
from mip_jupyter_dev.cohort_scout_eval import run_offline_eval
from mip_jupyter_dev.codex_bootstrap import BASE_INSTRUCTIONS_MAX_CHARS
from mip_jupyter_dev.codex_bootstrap import build_base_instructions


def test_eval_cases_cover_five_production_prompts() -> None:
    assert len(EVAL_CASES) == 5
    ids = {case.id for case in EVAL_CASES}
    assert ids == {"onboarding", "edit_cell", "novel_stroke", "off_topic", "env"}


def test_base_instructions_meet_production_budget() -> None:
    report = measure_base_instructions()
    assert report["ok"]
    assert report["chars"] <= BASE_INSTRUCTIONS_MAX_CHARS
    assert report["has_topic_routing"]
    assert report["skips_forced_index"]
    text = build_base_instructions()
    assert "00-agent-workspace" in text
    assert "--topic" in text


def test_expected_first_guide_commands() -> None:
    stroke = expected_first_guide(next(case for case in EVAL_CASES if case.id == "novel_stroke"))
    assert stroke["command"] == (
        "jupyter-mcp read-guide --page recipes/stroke-analysis --topic novel"
    )
    refuse = expected_first_guide(next(case for case in EVAL_CASES if case.id == "off_topic"))
    assert refuse["refuse"] is True


def test_offline_eval_passes() -> None:
    report = run_offline_eval()
    assert report["ok"]
    assert report["metadata"]["groups_default_empty"]
    assert report["topic_savings"]["saved_chars"] >= 0
