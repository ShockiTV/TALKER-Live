"""Deep-equality assertions for e2e RunResult vs scenario expected values."""

from .harness import RunResult

# Sentinel value used in scenario JSON to indicate "any non-empty list"
_ANY_LIST_SENTINEL = "__ANY_LIST__"


def assert_scenario(result: RunResult, scenario: dict) -> None:
    """Assert RunResult matches all declared expected keys in the scenario.

    Keys not present in scenario["expected"] are not asserted.
    All llm_mocks entries MUST include a 'request' field — asserted against
    the corresponding HTTP call body (by index). Missing 'request' is a test error.
    """
    expected = scenario.get("expected", {})

    if "state_queries" in expected:
        _assert_state_queries(result.state_queries, expected["state_queries"])

    if "http_calls" in expected:
        _assert_http_calls(result.http_calls, expected["http_calls"])

    _assert_llm_mock_requests(result.http_calls, scenario.get("llm_mocks", []))

    if "ws_published" in expected:
        _assert_ws_published(result.ws_published, expected["ws_published"])


def _deep_match(actual, expected):
    """Deep compare with support for __ANY_LIST__ sentinel.

    Returns True if actual matches expected, treating __ANY_LIST__ as
    'any non-empty list'.
    """
    if expected == _ANY_LIST_SENTINEL:
        return isinstance(actual, list) and len(actual) > 0
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected.keys()) != set(actual.keys()):
            return False
        return all(_deep_match(actual[k], expected[k]) for k in expected)
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        return all(_deep_match(a, e) for a, e in zip(actual, expected))
    return actual == expected


def _assert_state_queries(actual: list[dict], expected: list[dict]) -> None:
    assert len(actual) == len(expected), (
        f"Expected {len(expected)} state queries, got {len(actual)}.\n"
        f"Actual topics: {[e['topic'] for e in actual]}"
    )
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["topic"] == exp["topic"], (
            f"State query {i}: topic mismatch — got {act['topic']!r}, expected {exp['topic']!r}"
        )
        assert _deep_match(act["payload"], exp["payload"]), (
            f"State query {i} ({act['topic']}): payload mismatch.\n"
            f"Expected: {exp['payload']}\n"
            f"Actual:   {act['payload']}"
        )


def _assert_llm_mock_requests(http_calls, llm_mocks: list[dict]) -> None:
    """Assert each llm_mock's 'request' body matches the corresponding HTTP call.

    'request' is REQUIRED on every llm_mocks entry — missing it is a test error.
    """
    assert len(http_calls) == len(llm_mocks), (
        f"Expected {len(llm_mocks)} HTTP call(s) (matching llm_mocks), got {len(http_calls)}."
    )
    for i, (call, mock) in enumerate(zip(http_calls, llm_mocks)):
        assert "request" in mock, (
            f"llm_mocks[{i}] is missing a 'request' field — "
            f"all scenario llm_mocks entries must declare expected request bodies."
        )
        assert call.body == mock["request"], (
            f"LLM mock {i}: request body mismatch.\n"
            f"Expected: {mock['request']}\n"
            f"Actual:   {call.body}"
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


def _assert_ws_published(actual: list[dict], expected: list[dict]) -> None:
    assert len(actual) == len(expected), (
        f"Expected {len(expected)} WS publishes, got {len(actual)}.\n"
        f"Actual topics: {[e['topic'] for e in actual]}"
    )
    # Dynamic fields that are not part of scenario fixtures
    _DYNAMIC_FIELDS = {"dialogue_id"}

    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["topic"] == exp["topic"], (
            f"WS publish {i}: topic mismatch — got {act['topic']!r}, expected {exp['topic']!r}"
        )
        # Strip dynamic fields before comparison
        act_payload = {k: v for k, v in act["payload"].items() if k not in _DYNAMIC_FIELDS}
        assert act_payload == exp["payload"], (
            f"WS publish {i} ({act['topic']}): payload mismatch.\n"
            f"Expected: {exp['payload']}\n"
            f"Actual:   {act_payload}"
        )
