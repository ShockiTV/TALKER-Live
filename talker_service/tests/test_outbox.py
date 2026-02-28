"""Tests for transport.outbox — per-session message buffering."""

import time
from unittest.mock import patch

import pytest

from talker_service.transport.outbox import Outbox, OutboxMessage


# ---------------------------------------------------------------------------
# append / basic
# ---------------------------------------------------------------------------

class TestOutboxAppend:
    def test_append_increases_size(self):
        ob = Outbox()
        assert ob.size == 0
        ob.append('{"t":"test"}')
        assert ob.size == 1

    def test_append_multiple_preserves_order(self):
        ob = Outbox()
        ob.append("msg1")
        ob.append("msg2")
        ob.append("msg3")
        assert ob.size == 3

    def test_is_empty_reflects_state(self):
        ob = Outbox()
        assert ob.is_empty
        ob.append("x")
        assert not ob.is_empty


# ---------------------------------------------------------------------------
# drain
# ---------------------------------------------------------------------------

class TestOutboxDrain:
    def test_drain_returns_all_messages_in_order(self):
        ob = Outbox()
        ob.append("msg1")
        ob.append("msg2")
        ob.append("msg3")
        result = ob.drain()
        assert result == ["msg1", "msg2", "msg3"]

    def test_drain_clears_outbox(self):
        ob = Outbox()
        ob.append("msg1")
        ob.drain()
        assert ob.is_empty
        assert ob.size == 0

    def test_drain_empty_outbox_returns_empty_list(self):
        ob = Outbox()
        result = ob.drain()
        assert result == []


# ---------------------------------------------------------------------------
# TTL expiration
# ---------------------------------------------------------------------------

class TestOutboxTTL:
    def test_fresh_messages_delivered(self):
        ob = Outbox(ttl_seconds=60)
        ob.append("fresh")
        result = ob.drain()
        assert result == ["fresh"]

    def test_stale_messages_discarded(self):
        ob = Outbox(ttl_seconds=10)
        ob.append("stale")

        # Fast-forward monotonic clock past TTL
        with patch("talker_service.transport.outbox.time.monotonic") as mock_mono:
            # The message was created at real monotonic time.
            # Set drain-time to be way past TTL.
            created = ob._messages[0].created_at
            mock_mono.return_value = created + 20  # 20s > 10s TTL
            result = ob.drain()
        assert result == []

    def test_mixed_fresh_and_stale(self):
        ob = Outbox(ttl_seconds=30)

        # Two stale messages created "40s ago"
        now = time.monotonic()
        ob._messages.append(OutboxMessage(raw="stale1", created_at=now - 40))
        ob._messages.append(OutboxMessage(raw="stale2", created_at=now - 40))

        # Three fresh messages created just now
        ob.append("fresh1")
        ob.append("fresh2")
        ob.append("fresh3")

        result = ob.drain()
        assert result == ["fresh1", "fresh2", "fresh3"]


# ---------------------------------------------------------------------------
# Max size / FIFO eviction
# ---------------------------------------------------------------------------

class TestOutboxMaxSize:
    def test_oldest_evicted_at_capacity(self):
        ob = Outbox(max_size=3)
        ob.append("msg1")
        ob.append("msg2")
        ob.append("msg3")
        assert ob.size == 3
        ob.append("msg4")  # should evict msg1
        assert ob.size == 3
        result = ob.drain()
        assert result == ["msg2", "msg3", "msg4"]

    def test_max_size_one(self):
        ob = Outbox(max_size=1)
        ob.append("a")
        ob.append("b")
        ob.append("c")
        assert ob.size == 1
        assert ob.drain() == ["c"]

    def test_size_never_exceeds_max(self):
        ob = Outbox(max_size=5)
        for i in range(20):
            ob.append(f"msg{i}")
        assert ob.size == 5


# ---------------------------------------------------------------------------
# len / repr
# ---------------------------------------------------------------------------

class TestOutboxDunder:
    def test_len(self):
        ob = Outbox()
        assert len(ob) == 0
        ob.append("x")
        assert len(ob) == 1

    def test_repr(self):
        ob = Outbox(max_size=10, ttl_seconds=60)
        r = repr(ob)
        assert "Outbox" in r
        assert "max_size=10" in r
