"""Deep-equality assertions for e2e RunResult vs scenario expected values."""

from .harness import RunResult


def assert_scenario(result: RunResult, scenario: dict) -> None:
    """Assert RunResult matches all declared expected keys in the scenario.

    Keys not present in scenario["expected"] are not asserted.
    """
    expected = scenario.get("expected", {})

    if "state_queries" in expected:
        _assert_state_queries(result.state_queries, expected["state_queries"])

    if "http_calls" in expected:
        _assert_http_calls(result.http_calls, expected["http_calls"])

    if "zmq_published" in expected:
        _assert_zmq_published(result.zmq_published, expected["zmq_published"])


def _assert_state_queries(actual: list[dict], expected: list[dict]) -> None:
    assert len(actual) == len(expected), (
        f"Expected {len(expected)} state queries, got {len(actual)}.\n"
        f"Actual topics: {[e['topic'] for e in actual]}"
    )
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["topic"] == exp["topic"], (
            f"State query {i}: topic mismatch — got {act['topic']!r}, expected {exp['topic']!r}"
        )
        assert act["payload"] == exp["payload"], (
            f"State query {i} ({act['topic']}): payload mismatch.\n"
            f"Expected: {exp['payload']}\n"
            f"Actual:   {act['payload']}"
        )


def _assert_http_calls(actual, expected: list[dict]) -> None:
    assert len(actual) == len(expected), (
        f"Expected {len(expected)} HTTP calls, got {len(actual)}."
    )
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act.url == exp["url"], (
            f"HTTP call {i}: URL mismatch — got {act.url!r}, expected {exp['url']!r}"
        )
        assert act.body == exp["body"], (
            f"HTTP call {i}: body mismatch.\n"
            f"Expected: {exp['body']}\n"
            f"Actual:   {act.body}"
        )


def _assert_zmq_published(actual: list[dict], expected: list[dict]) -> None:
    assert len(actual) == len(expected), (
        f"Expected {len(expected)} ZMQ publishes, got {len(actual)}.\n"
        f"Actual topics: {[e['topic'] for e in actual]}"
    )
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["topic"] == exp["topic"], (
            f"ZMQ publish {i}: topic mismatch — got {act['topic']!r}, expected {exp['topic']!r}"
        )
        assert act["payload"] == exp["payload"], (
            f"ZMQ publish {i} ({act['topic']}): payload mismatch.\n"
            f"Expected: {exp['payload']}\n"
            f"Actual:   {act['payload']}"
        )
