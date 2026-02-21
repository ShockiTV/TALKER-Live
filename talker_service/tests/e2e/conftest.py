"""Pytest configuration for e2e tests."""

import dataclasses
import json
from pathlib import Path

import pytest

from .harness import E2eHarness

# E2e tests may spin up async harnesses and mock LLM round-trips — allow more time.
pytestmark = pytest.mark.timeout(30)


@pytest.fixture
async def e2e_harness():
    """Provide a fresh E2eHarness per test, tear down after."""
    harness = E2eHarness()
    yield harness
    await harness.shutdown()


def pytest_runtest_makereport(item, call):
    """Write captured payloads to .test_artifacts after each e2e test."""
    if call.when != "call":
        return

    harness: E2eHarness | None = None
    for fixture_name in item.fixturenames:
        if fixture_name == "e2e_harness":
            harness = item.funcargs.get("e2e_harness")
            break

    if harness is None or not harness._started:
        return

    artifacts_dir = Path(__file__).parent.parent.parent / ".test_artifacts" / "last_run"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    payloads_file = artifacts_dir / "payloads.json"
    existing = {}
    if payloads_file.exists():
        try:
            existing = json.loads(payloads_file.read_text())
        except Exception:
            existing = {}

    test_id = item.nodeid

    if harness.last_result is not None:
        # Use the already-collected RunResult (includes HTTP calls)
        result = harness.last_result
        existing[test_id] = {
            "state_queries": result.state_queries,
            "http_calls": [dataclasses.asdict(c) for c in result.http_calls],
            "zmq_published": result.zmq_published,
        }
    elif harness._lua_sim is not None:
        # Fallback: reconstruct from lua_sim records (no HTTP calls available)
        existing[test_id] = {
            "state_queries": [
                {
                    "topic": e["topic"],
                    "payload": {k: v for k, v in e["payload"].items() if k != "request_id"},
                }
                for e in harness._lua_sim.received_from_service
                if e["topic"] == "state.query" or e["topic"].startswith("state.query.")
            ],
            "http_calls": [],
            "zmq_published": [
                e
                for e in harness._lua_sim.received_from_service
                if e["topic"] != "state.response"
                and e["topic"] != "state.query"
                and not e["topic"].startswith("state.query.")
            ],
        }

    payloads_file.write_text(json.dumps(existing, indent=2))
