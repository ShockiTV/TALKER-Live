"""Tests for DeduplicationTracker."""

import pytest

from talker_service.dialogue.dedup_tracker import DeduplicationTracker
from talker_service.llm.models import Message


class TestDeduplicationTrackerCheckAndMark:
    """Tests for mark/check operations on all three sets."""

    def test_event_not_injected_initially(self):
        tracker = DeduplicationTracker()
        assert not tracker.is_event_injected(1000)

    def test_mark_event_then_check(self):
        tracker = DeduplicationTracker()
        tracker.mark_event(1000)
        assert tracker.is_event_injected(1000)
        assert not tracker.is_event_injected(2000)

    def test_bg_not_injected_initially(self):
        tracker = DeduplicationTracker()
        assert not tracker.is_bg_injected("char_001")

    def test_mark_bg_then_check(self):
        tracker = DeduplicationTracker()
        tracker.mark_bg("char_001")
        assert tracker.is_bg_injected("char_001")
        assert not tracker.is_bg_injected("char_002")

    def test_mem_not_injected_initially(self):
        tracker = DeduplicationTracker()
        assert not tracker.is_mem_injected("char_001", 500)

    def test_mark_mem_then_check(self):
        tracker = DeduplicationTracker()
        tracker.mark_mem("char_001", 500)
        assert tracker.is_mem_injected("char_001", 500)
        assert not tracker.is_mem_injected("char_001", 600)
        assert not tracker.is_mem_injected("char_002", 500)

    def test_counts(self):
        tracker = DeduplicationTracker()
        assert tracker.event_count == 0
        assert tracker.bg_count == 0
        assert tracker.mem_count == 0

        tracker.mark_event(1)
        tracker.mark_event(2)
        tracker.mark_bg("a")
        tracker.mark_mem("b", 3)
        tracker.mark_mem("b", 4)
        tracker.mark_mem("c", 3)

        assert tracker.event_count == 2
        assert tracker.bg_count == 1
        assert tracker.mem_count == 3


class TestDeduplicationTrackerRebuild:
    """Tests for rebuild_from_messages with tag parsing."""

    def test_rebuild_events(self):
        tracker = DeduplicationTracker()
        tracker.mark_event(999)  # will be cleared

        messages = [
            Message(role="system", content="EVT:1000 — DEATH: Wolf killed Bandit"),
            Message(role="system", content="EVT:2000 — IDLE — Fanatic"),
            Message(role="user", content="Pick speaker for EVT:1000"),
        ]

        tracker.rebuild_from_messages(messages)

        assert tracker.is_event_injected(1000)
        assert tracker.is_event_injected(2000)
        assert not tracker.is_event_injected(999)  # was cleared
        assert tracker.event_count == 2

    def test_rebuild_backgrounds(self):
        tracker = DeduplicationTracker()
        messages = [
            Message(role="system", content="BG:12467 — Wolf (Freedom)\nTraits: brave"),
            Message(role="system", content="BG:34521 — Fanatic (Duty)\nTraits: zealous"),
        ]

        tracker.rebuild_from_messages(messages)

        assert tracker.is_bg_injected("12467")
        assert tracker.is_bg_injected("34521")
        assert not tracker.is_bg_injected("99999")
        assert tracker.bg_count == 2

    def test_rebuild_memories(self):
        tracker = DeduplicationTracker()
        messages = [
            Message(role="system", content="MEM:12467:42000 — [SUMMARY] Wolf recalls..."),
            Message(role="system", content="MEM:12467:43000 — [DIGEST] Wolf remembers..."),
            Message(role="system", content="MEM:34521:42000 — [SUMMARY] Fanatic saw..."),
        ]

        tracker.rebuild_from_messages(messages)

        assert tracker.is_mem_injected("12467", 42000)
        assert tracker.is_mem_injected("12467", 43000)
        assert tracker.is_mem_injected("34521", 42000)
        assert not tracker.is_mem_injected("34521", 43000)
        assert tracker.mem_count == 3

    def test_rebuild_ignores_non_system(self):
        tracker = DeduplicationTracker()
        messages = [
            Message(role="user", content="EVT:1000 — should be ignored"),
            Message(role="assistant", content="BG:12467 — should be ignored"),
            Message(role="system", content="EVT:2000 — real event"),
        ]

        tracker.rebuild_from_messages(messages)

        assert not tracker.is_event_injected(1000)
        assert not tracker.is_bg_injected("12467")
        assert tracker.is_event_injected(2000)

    def test_rebuild_mixed_types(self):
        tracker = DeduplicationTracker()
        messages = [
            Message(role="system", content="EVT:1000 — DEATH event"),
            Message(role="system", content="BG:12467 — Wolf (Freedom)\nTraits"),
            Message(role="system", content="MEM:12467:500 — [SUMMARY] text"),
            Message(role="user", content="Pick speaker for EVT:1000"),
            Message(role="assistant", content="12467"),
        ]

        tracker.rebuild_from_messages(messages)

        assert tracker.event_count == 1
        assert tracker.bg_count == 1
        assert tracker.mem_count == 1

    def test_rebuild_clears_previous_state(self):
        tracker = DeduplicationTracker()
        tracker.mark_event(1)
        tracker.mark_bg("old")
        tracker.mark_mem("old", 1)

        tracker.rebuild_from_messages([
            Message(role="system", content="EVT:2000 — new event"),
        ])

        assert not tracker.is_event_injected(1)
        assert not tracker.is_bg_injected("old")
        assert not tracker.is_mem_injected("old", 1)
        assert tracker.is_event_injected(2000)

    def test_rebuild_with_non_tagged_system_message(self):
        """System messages that don't match any tag pattern are ignored."""
        tracker = DeduplicationTracker()
        messages = [
            Message(role="system", content="You are generating dialogue for NPCs..."),
            Message(role="system", content="EVT:1000 — some event"),
        ]

        tracker.rebuild_from_messages(messages)

        assert tracker.event_count == 1
        assert tracker.bg_count == 0
        assert tracker.mem_count == 0
