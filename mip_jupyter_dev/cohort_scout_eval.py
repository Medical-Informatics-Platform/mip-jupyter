"""Production Cohort Scout context-efficiency checks (no live chat required)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request
from urllib.request import urlopen

from .codex_bootstrap import BASE_INSTRUCTIONS_MAX_CHARS
from .codex_bootstrap import DEFAULT_CODEX_MODEL
from .codex_bootstrap import ENV_CODEX_MODEL
from .codex_bootstrap import build_base_instructions
from . import jupyter_mcp_tools as tools


@dataclass(frozen=True)
class EvalCase:
    """Canned production prompt with expected first guide page."""

    id: str
    prompt: str
    expected_page: str | None
    topic: str | None = None
    refuse: bool = False


# Keep aligned with docs/jupyter-ai-codex.md golden prompts.
EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="onboarding",
        prompt="@Cohort Scout summarize what a new MIP user should do first",
        expected_page="01-onboarding",
    ),
    EvalCase(
        id="edit_cell",
        prompt=(
            "@Cohort Scout create a new scratch notebook named mcp_probe.ipynb "
            "with one markdown cell that says MCP OK"
        ),
        expected_page="04-jupyter-mcp",
        topic="payload",
    ),
    EvalCase(
        id="novel_stroke",
        prompt=(
            "@Cohort Scout run a novel statistical stroke analysis with significance on SSR"
        ),
        expected_page="recipes/stroke-analysis",
        topic="novel",
    ),
    EvalCase(
        id="off_topic",
        prompt="@Cohort Scout write a chocolate cake recipe",
        expected_page="00-agent-workspace",
        topic="scope",
        refuse=True,
    ),
    EvalCase(
        id="env",
        prompt="@Cohort Scout explain how mip.Client.from_env() gets configuration",
        expected_page="05-env-and-backend",
        topic="from_env",
    ),
)


class _EvalVar:
    def __init__(self, code: str, label: str) -> None:
        self.code = code
        self.label = label

    def summary(self) -> dict[str, Any]:
        return {"code": self.code, "label": self.label, "type": "integer"}


class _EvalVariables:
    def search(self, query: str) -> list[_EvalVar]:
        return [_EvalVar("nihss", f"NIHSS {query}")]


class _EvalDataModel:
    variables = _EvalVariables()

    def summary(self) -> dict[str, Any]:
        return {"code": "stroke", "version": "3.7", "n_variables": 1, "n_datasets": 1}

    def list_datasets(self) -> list[dict[str, Any]]:
        return [{"code": "SSR", "label": "SSR"}]

    def list_groups(self) -> list[dict[str, Any]]:
        return [{"code": "clinical", "label": "Clinical"}]

    def list_variables(self) -> list[dict[str, Any]]:
        return [{"code": "nihss", "label": "NIHSS", "type": "integer"}]


class _EvalCatalog:
    def summaries(self) -> list[dict[str, Any]]:
        return [{"code": "stroke", "version": "3.7", "label": "Stroke"}]

    def data_model(self, code: str, version: str | None = None) -> _EvalDataModel:
        return _EvalDataModel()


class _EvalAlgo:
    def __init__(self, name: str, kind: str) -> None:
        self.name = name
        self.kind = kind

    def summary(self) -> dict[str, Any]:
        return {"name": self.name, "label": self.name, "type": self.kind}


class _EvalAlgorithms:
    def list(self) -> list[_EvalAlgo]:
        return [_EvalAlgo("describe", "statistics"), _EvalAlgo("logistic_regression", "model")]


class EvalClient:
    """Minimal fake MIP client for offline metadata size checks."""

    def catalog(self) -> _EvalCatalog:
        return _EvalCatalog()

    def algorithms(self) -> _EvalAlgorithms:
        return _EvalAlgorithms()


def measure_base_instructions() -> dict[str, Any]:
    text = build_base_instructions()
    return {
        "chars": len(text),
        "budget": BASE_INSTRUCTIONS_MAX_CHARS,
        "ok": len(text) <= BASE_INSTRUCTIONS_MAX_CHARS,
        "has_topic_routing": "--topic" in text,
        "skips_forced_index": "skip AGENTS" in text,
        "has_shell_bridge": "jupyter-mcp" in text or "jupyter_mcp_cli" in text,
    }


def expected_first_guide(case: EvalCase) -> dict[str, Any]:
    """Document the expected first read-guide call for a canned prompt."""

    if case.refuse:
        return {
            "case": case.id,
            "prompt": case.prompt,
            "refuse": True,
            "expected_page": case.expected_page,
            "topic": case.topic,
            "notes": "Refuse briefly; optional 00 --topic scope; no MIP metadata tools.",
        }
    command = None
    if case.expected_page:
        command = f"jupyter-mcp read-guide --page {case.expected_page}"
        if case.topic:
            command += f" --topic {case.topic}"
    return {
        "case": case.id,
        "prompt": case.prompt,
        "refuse": False,
        "expected_page": case.expected_page,
        "topic": case.topic,
        "command": command,
    }


def measure_topic_savings(page: str, topic: str) -> dict[str, Any]:
    """Compare full-page vs topic-scoped guide bytes (uses repo agent docs)."""

    repo = Path(__file__).resolve().parents[1]
    env = {
        "MIP_AGENT_DOCS": str(repo),
        "MIP_JUPYTER_ROOT": str(repo / "workspace"),
    }
    previous = {key: os.environ.get(key) for key in env}
    try:
        os.environ.update(env)
        full = asyncio.run(tools.agent_read_guide(page=page, topic=None))
        scoped = asyncio.run(tools.agent_read_guide(page=page, topic=topic))
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    full_len = len(full.get("content") or "")
    scoped_len = len(scoped.get("content") or "")
    return {
        "page": page,
        "topic": topic,
        "full_chars": full_len,
        "topic_chars": scoped_len,
        "saved_chars": max(0, full_len - scoped_len),
        "ok": scoped_len < full_len or full_len == 0,
    }


def measure_metadata_payloads(client: Any | None = None) -> dict[str, Any]:
    """Measure default MIP metadata JSON sizes against a fake client."""

    active = client or EvalClient()
    with patch("mip.Client.from_env", return_value=active):
        catalog = asyncio.run(tools.mip_catalog_summary())
        model = asyncio.run(tools.mip_data_model_summary("stroke", version="3.7"))
        algorithms = asyncio.run(tools.mip_algorithm_summary())

    sizes = {
        "catalog": len(json.dumps(catalog, ensure_ascii=False)),
        "data_model": len(json.dumps(model, ensure_ascii=False)),
        "algorithms": len(json.dumps(algorithms, ensure_ascii=False)),
    }
    return {
        "sizes": sizes,
        "budget": tools.MAX_RESPONSE_JSON_CHARS,
        "ok": all(size <= tools.MAX_RESPONSE_JSON_CHARS for size in sizes.values()),
        "groups_default_empty": model.get("groups") == [],
    }


def optional_vllm_ttft(
    *,
    base_url: str,
    model: str = DEFAULT_CODEX_MODEL,
    prompt: str = "Reply with OK only.",
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Optional live TTFT probe against production vLLM Responses API."""

    url = base_url.rstrip("/") + "/responses"
    body = json.dumps(
        {"model": model, "input": prompt, "max_output_tokens": 64}
    ).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout_s) as response:
            payload = response.read()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "ttft_ms": elapsed_ms,
            "bytes": len(payload),
            "model": model,
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc), "model": model}


def run_offline_eval(client: Any | None = None) -> dict[str, Any]:
    """Run offline production context checks and return a JSON-serializable report."""

    instructions = measure_base_instructions()
    cases = [expected_first_guide(case) for case in EVAL_CASES]
    topic = measure_topic_savings("recipes/stroke-analysis", "novel")
    metadata = measure_metadata_payloads(client)
    ok = bool(instructions["ok"] and topic["ok"] and metadata["ok"] and metadata["groups_default_empty"])
    return {
        "ok": ok,
        "instructions": instructions,
        "cases": cases,
        "topic_savings": topic,
        "metadata": metadata,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Cohort Scout production context budgets.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument(
        "--live-vllm",
        action="store_true",
        help="Also probe vLLM TTFT when CODEX_VLLM_BASE_URL is set",
    )
    args = parser.parse_args(argv)
    report = run_offline_eval()
    if args.live_vllm:
        base_url = os.getenv("CODEX_VLLM_BASE_URL")
        if not base_url:
            report["vllm"] = {"ok": False, "error": "CODEX_VLLM_BASE_URL unset"}
            report["ok"] = False
        else:
            report["vllm"] = optional_vllm_ttft(
                base_url=base_url,
                model=os.getenv(ENV_CODEX_MODEL, DEFAULT_CODEX_MODEL),
            )
            report["ok"] = bool(report["ok"] and report["vllm"]["ok"])

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        instr = report["instructions"]
        print(
            f"base_instructions: {instr['chars']}/{instr['budget']} chars "
            f"({'ok' if instr['ok'] else 'FAIL'})"
        )
        print(f"topic savings: {report['topic_savings']['saved_chars']} chars")
        print(f"metadata sizes: {report['metadata']['sizes']}")
        for case in report["cases"]:
            mark = "refuse" if case["refuse"] else case.get("command")
            print(f"  {case['case']}: {mark}")
        if "vllm" in report:
            print(f"vllm: {report['vllm']}")
        print("PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
