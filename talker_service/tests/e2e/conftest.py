"""Pytest configuration for e2e tests."""

import dataclasses
import json
from pathlib import Path

import jsonschema
import pytest

from .scenario_loader import discover_scenarios, load_scenario, scenario_id
from .schema_compiler import compile_schema

# E2e tests may spin up async harnesses and mock LLM round-trips — allow more time.
pytestmark = pytest.mark.timeout(30)


# ── Schema validation at collection time ──────────────────────

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docs" / "ws-api.yaml"


def _validate_scenario(scenario: dict, compiled: dict, path: Path) -> list[str]:
    """Validate one scenario against the compiled WS schema.

    Returns a list of human-readable error strings (empty == valid).
    """
    errors: list[str] = []

    def _check(instance, schema_fragment, label: str) -> None:
        try:
            jsonschema.validate(instance, schema_fragment)
        except jsonschema.ValidationError as exc:
            errors.append(f"  {label}: {exc.message}")

    # 1. input.payload
    input_cfg = scenario.get("input", {})
    topic = input_cfg.get("topic")
    payload = input_cfg.get("payload")
    if topic and payload and topic in compiled:
        payload_schema = compiled[topic].get("payload")
        if payload_schema:
            _check(payload, payload_schema, f"input.payload ({topic})")

    # 2. state_mocks.<topic>.response
    for mock_topic, mock_data in scenario.get("state_mocks", {}).items():
        if mock_topic not in compiled:
            continue
        resp_schema = compiled[mock_topic].get("response")
        if resp_schema and "response" in mock_data:
            _check(mock_data["response"], resp_schema, f"state_mocks.{mock_topic}")

    # 3. expected.ws_published[].payload
    for i, pub in enumerate(scenario.get("expected", {}).get("ws_published", [])):
        t = pub.get("topic")
        if t and t in compiled:
            pub_schema = compiled[t].get("payload")
            if pub_schema:
                _check(pub["payload"], pub_schema, f"expected.ws_published[{i}] ({t})")

    # 4. expected.state_queries[].payload
    for i, sq in enumerate(scenario.get("expected", {}).get("state_queries", [])):
        t = sq.get("topic")
        if t and t in compiled:
            req_schema = compiled[t].get("request")
            if req_schema:
                _check(sq["payload"], req_schema, f"expected.state_queries[{i}] ({t})")

    return errors


def pytest_collection_modifyitems(config, items):
    """Validate all scenario files against the WS API schema during collection.

    Runs once at collection time — before any sockets or event loops spin up.
    Any validation error causes an immediate, clear failure.
    """
    if not _SCHEMA_PATH.exists():
        return  # Schema file absent — skip validation silently

    compiled = compile_schema(str(_SCHEMA_PATH))
    all_errors: list[str] = []

    for path in discover_scenarios():
        scenario = load_scenario(path)
        errs = _validate_scenario(scenario, compiled, path)
        if errs:
            all_errors.append(f"{path.name}:")
            all_errors.extend(errs)

    if all_errors:
        msg = "Scenario files failed WS schema validation:\n" + "\n".join(all_errors)
        pytest.exit(msg, returncode=1)


@pytest.fixture
async def e2e_harness():
    """Provide a fresh E2eHarness per test, tear down after."""
    from .harness import E2eHarness

    harness = E2eHarness()
    yield harness
    await harness.shutdown()


def pytest_runtest_makereport(item, call):
    """Write captured payloads to .test_artifacts after each e2e test."""
    if call.when != "call":
        return

    harness = None
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
            "ws_published": result.ws_published,
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
            "ws_published": [
                e
                for e in harness._lua_sim.received_from_service
                if e["topic"] != "state.response"
                and e["topic"] != "state.query"
                and not e["topic"].startswith("state.query.")
            ],
        }

    payloads_file.write_text(json.dumps(existing, indent=2))
