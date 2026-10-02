"""Tests for shell command guard policy."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mip_jupyter_dev.codex_bootstrap import write_shell_guard_wrapper
from mip_jupyter_dev.shell_guard import validate_shell_command


def test_rejects_heredoc() -> None:
    cmd = "cat > scratch/foo.py << 'PYEOF'\nprint('x')\nPYEOF"
    assert validate_shell_command(cmd) is not None


def test_rejects_write_stdin() -> None:
    assert validate_shell_command("write_stdin payload") is not None


def test_rejects_raw_notebook_cat() -> None:
    assert validate_shell_command("cat workspace/examples/feres_analysis.ipynb") is not None


def test_rejects_oversized_command() -> None:
    assert validate_shell_command("echo " + "x" * 3000) is not None


def test_allows_scratch_script_run() -> None:
    assert validate_shell_command("python scratch/novel_stroke_analysis.py") is None


def test_allows_jupyter_mcp_cli() -> None:
    assert (
        validate_shell_command(
            "python -m mip_jupyter_dev.jupyter_mcp_cli scratch-copy-template scratch/foo.py"
        )
        is None
    )


def test_shell_guard_wrapper_rejects_lc_notebook_cat(tmp_path: Path) -> None:
    wrapper = tmp_path / "mip-shell-guard"
    write_shell_guard_wrapper(wrapper)
    result = subprocess.run(
        [str(wrapper), "-lc", "cat workspace/examples/feres_analysis.ipynb"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Raw notebook file reads are disabled" in result.stderr


def test_shell_guard_wrapper_rejects_login_c_notebook_cat(tmp_path: Path) -> None:
    wrapper = tmp_path / "mip-shell-guard"
    write_shell_guard_wrapper(wrapper)
    result = subprocess.run(
        [str(wrapper), "--login", "-c", "cat workspace/examples/feres_analysis.ipynb"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Raw notebook file reads are disabled" in result.stderr


def test_shell_guard_wrapper_allows_lc_allowed_command(tmp_path: Path) -> None:
    wrapper = tmp_path / "mip-shell-guard"
    write_shell_guard_wrapper(wrapper)
    result = subprocess.run(
        [str(wrapper), "-lc", "echo ok"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"


def test_shell_guard_wrapper_preserves_long_options_before_c(tmp_path: Path) -> None:
    wrapper = tmp_path / "mip-shell-guard"
    write_shell_guard_wrapper(wrapper)
    result = subprocess.run(
        [str(wrapper), "--norc", "-c", "echo ok"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"
