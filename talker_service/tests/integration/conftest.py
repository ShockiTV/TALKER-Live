"""Shared mock infrastructure for integration lifecycle tests.

Provides:
- MockStateClient     — records batch query requests, returns configured responses
- MockPublisher       — records published {topic, payload} dicts
- MockLLMClient       — records LLM requests, returns pre-configured responses in order
- LifecycleSnapshot   — dataclass: input_event, state_requests, llm_requests, published
- run_lifecycle()     — wires mocks to DialogueGenerator and executes one event lifecycle
- assert_state_requests()  — assert method names and args match
- assert_llm_requests()    — assert content_patterns appear in LLM messages (regex)
- assert_published()       — assert topic and payload keys match

NOTE: These tests were written for the old DialogueGenerator API.
DialogueGenerator was removed in the tools-based-memory migration and replaced
by ConversationManager (tool-based LLM dialogue). These tests are skipped until
they are rewritten for the new API.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

import pytest

try:
    from talker_service.dialogue.generator import DialogueGenerator
except ImportError:
    DialogueGenerator = None  # Removed in tools-based-memory migration

from talker_service.state.batch import BatchResult


# =============================================================================
# MOCK STATE CLIENT
# =============================================================================

class MockStateClient:
    """Mock state client that records requests and returns configured responses."""

    def __init__(
        self,
        memory_json: str,
        character_json: str,
        scene_json: str,
        characters_alive_json: str,
        events_json: str = "[]",
        personalities_json: str = "{}",
        backstories_json: str = "{}",
    ):
        self.memory_response = json.loads(memory_json)
        self.character_response = json.loads(character_json)
        self.scene_response = json.loads(scene_json)
        self.characters_alive_response = json.loads(characters_alive_json)
        self.events_response = json.loads(events_json)
        self.personalities_response = json.loads(personalities_json)
        self.backstories_response = json.loads(backstories_json)
        # Record requests as JSON-serializable dicts
        self.requests: list[dict] = []

    async def execute_batch(self, batch, *, timeout=None, session=None) -> "BatchResult":
        """Route batch sub-queries to individual mock methods, recording requests."""
        results: dict[str, dict] = {}
        for q in batch.build():
            qid = q["id"]
            resource = q["resource"]
            params = q.get("params", {})
            try:
                if resource == "store.memories":
                    self.requests.append({
                        "method": "query_memories",
                        "args": {"character_id": params["character_id"]}
                    })
                    results[qid] = {"ok": True, "data": self.memory_response}
                elif resource == "query.character":
                    self.requests.append({
                        "method": "query_character",
                        "args": {"character_id": params["id"]}
                    })
                    results[qid] = {"ok": True, "data": self.character_response}
                elif resource == "store.events":
                    # Return events data without recording (internal detail)
                    results[qid] = {"ok": True, "data": self.events_response}
                elif resource == "query.world":
                    self.requests.append({
                        "method": "query_world_context",
                        "args": {}
                    })
                    results[qid] = {"ok": True, "data": self.scene_response}
                elif resource == "query.characters_alive":
                    ids = params.get("ids", [])
                    self.requests.append({
                        "method": "query_characters_alive",
                        "args": {"story_ids": ids}
                    })
                    alive_data = self.characters_alive_response.get("alive", {})
                    results[qid] = {"ok": True, "data": alive_data}
                elif resource == "store.personalities":
                    target_ids = [str(i) for i in params.get("target", [])]
                    data = {k: v for k, v in self.personalities_response.items() if k in target_ids}
                    results[qid] = {"ok": True, "data": data}
                elif resource == "store.backstories":
                    target_ids = [str(i) for i in params.get("target", [])]
                    data = {k: v for k, v in self.backstories_response.items() if k in target_ids}
                    results[qid] = {"ok": True, "data": data}
                else:
                    results[qid] = {"ok": False, "error": f"unknown resource: {resource}"}
            except Exception as e:
                results[qid] = {"ok": False, "error": str(e)}
        return BatchResult(results)


# =============================================================================
# MOCK PUBLISHER
# =============================================================================

class MockPublisher:
    """Mock ZMQ publisher that records published messages as JSON."""

    def __init__(self):
        self.published: list[dict] = []

    async def publish(self, topic: str, payload: dict, *, session: str | None = None) -> bool:
        self.published.append({"topic": topic, "payload": payload})
        return True


# =============================================================================
# MOCK LLM CLIENT
# =============================================================================

class MockLLMClient:
    """Mock LLM client that records requests and returns configured responses."""

    def __init__(self, response_jsons: list[str]):
        self.responses = [r.strip() for r in response_jsons]
        self.call_index = 0
        # Record requests as JSON-serializable structures
        self.requests: list[dict] = []

    async def complete(self, messages: list, options: Any = None) -> str:
        # Convert Message objects to dicts for recording
        msgs_as_dicts = [{"role": m.role, "content": m.content} for m in messages]
        self.requests.append({
            "messages": msgs_as_dicts,
            "options": {
                "temperature": getattr(options, "temperature", None),
                "max_tokens": getattr(options, "max_tokens", None),
            } if options else None
        })
        if self.call_index < len(self.responses):
            response = self.responses[self.call_index]
            self.call_index += 1
            return response
        return "Fallback response."


# =============================================================================
# LIFECYCLE SNAPSHOT
# =============================================================================

@dataclass
class LifecycleSnapshot:
    """Full lifecycle state for assertions - all as JSON-serializable."""
    input_event: dict
    state_requests: list[dict]
    llm_requests: list[dict]
    published: list[dict]


# =============================================================================
# LIFECYCLE RUNNER
# =============================================================================

async def run_lifecycle(
    input_event_json: str,
    scene_json: str,
    characters_alive_json: str,
    memory_json: str,
    character_json: str,
    llm_responses: list[str],
    events_json: str = "[]",
    personalities_json: str = "{}",
    backstories_json: str = "{}",
) -> LifecycleSnapshot:
    """Run full event lifecycle and return snapshot.

    Wires MockStateClient, MockPublisher, MockLLMClient to a DialogueGenerator,
    fires generate_from_event(), and returns all recorded interactions.

    Args:
        input_event_json:      Full input payload JSON (with "event" and "is_important" keys)
        scene_json:            Mock scene/world context response JSON
        characters_alive_json: Mock characters-alive response JSON ({"alive": {...}})
        memory_json:           Mock memory store response JSON (narrative + last_update_time_ms)
        character_json:        Mock character detail response JSON
        llm_responses:         Ordered list of mock LLM response strings
        events_json:           Mock store.events response JSON (list of event dicts, default [])

    Returns:
        LifecycleSnapshot with all recorded state requests, LLM requests, and publishes
    """
    if DialogueGenerator is None:
        pytest.skip(
            "DialogueGenerator removed in tools-based-memory migration — "
            "integration tests need rewrite for ConversationManager"
        )

    input_event = json.loads(input_event_json)

    state_client = MockStateClient(
        memory_json=memory_json,
        character_json=character_json,
        scene_json=scene_json,
        characters_alive_json=characters_alive_json,
        events_json=events_json,
        personalities_json=personalities_json,
        backstories_json=backstories_json,
    )

    publisher = MockPublisher()
    llm_client = MockLLMClient(llm_responses)

    generator = DialogueGenerator(
        llm_client=llm_client,
        state_client=state_client,
        publisher=publisher,
        llm_timeout=5.0,
    )

    event_data = input_event.get("event", input_event)
    is_important = input_event.get("is_important", False)

    await generator.generate_from_event(event_data, is_important)

    return LifecycleSnapshot(
        input_event=input_event,
        state_requests=state_client.requests,
        llm_requests=llm_client.requests,
        published=publisher.published,
    )


# =============================================================================
# ASSERTION HELPERS
# =============================================================================

def assert_state_requests(actual: list[dict], expected_json: str) -> None:
    """Assert state requests match expected JSON.

    For query_characters_alive, only checks that expected IDs are a subset
    of actual IDs (batch queries send ALL story IDs).

    Args:
        actual:        List of recorded state request dicts
        expected_json: JSON array of expected request dicts with "method" and "args"
    """
    expected = json.loads(expected_json)
    assert len(actual) == len(expected), \
        f"Expected {len(expected)} state requests, got {len(actual)}"
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["method"] == exp["method"], \
            f"Request {i}: method mismatch (got {act['method']!r}, expected {exp['method']!r})"
        if exp["method"] == "query_characters_alive":
            # Batch queries send ALL story IDs; check expected IDs are a subset
            assert set(exp["args"]["story_ids"]).issubset(
                set(act["args"]["story_ids"])
            ), (
                f"Request {i}: alive query missing expected IDs: "
                f"{set(exp['args']['story_ids']) - set(act['args']['story_ids'])}"
            )
        else:
            assert act["args"] == exp["args"], \
                f"Request {i}: args mismatch\nExpected: {exp['args']}\nActual: {act['args']}"


def assert_llm_requests(actual: list[dict], expected_json: str) -> None:
    """Assert LLM requests match expected structure and content patterns.

    Expected format supports:
    - Number of LLM calls (by list length)
    - For each call: content_patterns that must appear in role-specific messages
    - options (temperature, max_tokens)

    Pattern matching is case-insensitive regex search.

    Args:
        actual:        List of recorded LLM request dicts
        expected_json: JSON array of expected LLM request specs
    """
    expected = json.loads(expected_json)
    assert len(actual) == len(expected), \
        f"Expected {len(expected)} LLM calls, got {len(actual)}"

    for i, (act, exp) in enumerate(zip(actual, expected)):
        act_msgs = act["messages"]

        # Combine messages by role for pattern matching
        system_content = " ".join(m["content"] for m in act_msgs if m["role"] == "system")
        user_content = " ".join(m["content"] for m in act_msgs if m["role"] == "user")

        # Check patterns from expected messages
        for exp_msg in exp.get("messages", []):
            role = exp_msg["role"]
            patterns = exp_msg.get("content_patterns", [])
            content_to_search = system_content if role == "system" else user_content

            for pattern in patterns:
                assert re.search(pattern, content_to_search, re.IGNORECASE), (
                    f"LLM call {i} ({role}): missing pattern {pattern!r} in content"
                )

        # Assert options if specified
        if exp.get("options"):
            for key, val in exp["options"].items():
                assert act["options"].get(key) == val, (
                    f"LLM call {i}: option {key} mismatch "
                    f"(got {act['options'].get(key)!r}, expected {val!r})"
                )


def assert_published(actual: list[dict], expected_json: str) -> None:
    """Assert published commands match expected JSON.

    Checks topic equality and expected payload keys are present with correct values.

    Args:
        actual:        List of recorded published message dicts
        expected_json: JSON array of expected publish dicts with "topic" and "payload"
    """
    expected = json.loads(expected_json)
    assert len(actual) == len(expected), \
        f"Expected {len(expected)} published messages, got {len(actual)}"
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["topic"] == exp["topic"], \
            f"Publish {i}: topic mismatch (got {act['topic']!r}, expected {exp['topic']!r})"
        for key, val in exp["payload"].items():
            assert act["payload"].get(key) == val, \
                f"Publish {i}: payload.{key} mismatch (got {act['payload'].get(key)!r}, expected {val!r})"
