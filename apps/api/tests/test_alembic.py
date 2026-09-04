"""Tests for the Alembic migration environment.

These tests only load the configuration and inspect the migration state;
the upgrade/downgrade lifecycle is exercised from the CLI.
"""

import os
import subprocess
import sys

from alembic.config import Config


def test_alembic_config_loads() -> None:
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(api_dir, "alembic.ini")
    config = Config(config_path)
    assert config.config_file_name == config_path
    script_location = config.get_main_option("script_location")
    assert script_location is not None
    assert script_location.endswith("alembic")


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        cwd=api_dir,
        env={**os.environ, "DATABASE_URL": os.environ["DATABASE_URL"]},
        check=False,
    )


def test_alembic_heads_runs() -> None:
    result = _run_alembic("heads")
    assert result.returncode == 0, result.stderr
    assert "0003 (head)" in result.stdout


def test_alembic_current_matches_head() -> None:
    result = _run_alembic("current")
    assert result.returncode == 0, result.stderr
    assert "0003 (head)" in result.stdout


def test_alembic_has_single_head() -> None:
    result = _run_alembic("heads")
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("(head)") == 1
