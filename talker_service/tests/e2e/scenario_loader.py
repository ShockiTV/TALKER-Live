"""Discover and load JSON scenario files for e2e tests."""

import json
from pathlib import Path


SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def discover_scenarios(directory: Path | str | None = None) -> list[Path]:
    """Return sorted list of scenario .json file paths."""
    base = Path(directory) if directory else SCENARIOS_DIR
    return sorted(base.glob("*.json"))


def load_scenario(path: Path | str) -> dict:
    """Load and return a parsed scenario dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def scenario_id(path: Path | str) -> str:
    """Return a short test ID from a scenario file path."""
    return Path(path).stem
