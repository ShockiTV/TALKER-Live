"""Tests for DialogueRetryQueue."""

import asyncio
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.dialogue.retry_queue import DialogueRetryQueue, RetryItem


# ---------------------------------------------------------------------------
# RetryItem dataclass
# ---------------------------------------------------------------------------

class TestRetryItem:
    """Tests for the RetryItem dataclass."""

    def test_defaults(self):
        """Verify default field values."""
        item = RetryItem(method="event", event_dict={"type": "DEATH"})
        assert item.method == "event"
        assert item.event_dict == {"type": "DEATH"}
        assert item.speaker_id is None
        assert item.attempt_count == 1
        assert isinstance(item.enqueued_at, float)

    def test_instruction_item(self):
        """Instruction items store speaker_id."""
        item = RetryItem(
            method="instruction",
            event_dict={"type": "IDLE"},
            speaker_id="42",
            attempt_count=3,
        )
        assert item.method == "instruction"
        assert item.speaker_id == "42"
        assert item.attempt_count == 3


# ---------------------------------------------------------------------------
# DialogueRetryQueue.enqueue
# ---------------------------------------------------------------------------

class TestEnqueue:
    """Tests for enqueue behaviour."""

    def test_enqueue_increases_size(self):
        """Enqueue adds items to the queue."""
        q = DialogueRetryQueue()
        assert q.size == 0

        q.enqueue("event", {"type": "DEATH"})
        assert q.size == 1

        q.enqueue("instruction", {"type": "IDLE"}, speaker_id="5")
        assert q.size == 2

    def test_enqueue_preserves_attempt_count(self):
        """Attempt count is stored as provided."""
        q = DialogueRetryQueue()
        q.enqueue("event", {"type": "DEATH"}, attempt_count=3)

        # Drain to inspect
        items = list(q._queue)
        assert items[0].attempt_count == 3


# ---------------------------------------------------------------------------
# DialogueRetryQueue.flush
# ---------------------------------------------------------------------------

class TestFlush:
    """Tests for flush behaviour."""

    def _make_generator(self) -> MagicMock:
        gen = MagicMock()
        gen.generate_from_event = AsyncMock()
        gen.generate_from_instruction = AsyncMock()
        return gen

    def test_flush_empty_returns_zero(self):
        """Flush on empty queue returns 0 and does nothing."""
        q = DialogueRetryQueue()
        gen = self._make_generator()
        assert q.flush(gen) == 0

    @pytest.mark.asyncio
    async def test_flush_resubmits_valid_items(self):
        """Valid items are re-submitted via asyncio.create_task."""
        q = DialogueRetryQueue(max_retries=5)
        q.enqueue("event", {"type": "DEATH"}, attempt_count=1)
        q.enqueue("instruction", {"type": "IDLE"}, speaker_id="7", attempt_count=2)

        gen = self._make_generator()
        resubmitted = q.flush(gen)

        assert resubmitted == 2
        assert q.size == 0

        # Let tasks run
        await asyncio.sleep(0.05)

        gen.generate_from_event.assert_called_once()
        gen.generate_from_instruction.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_discards_max_retry_items(self):
        """Items at max_retries are discarded with warning."""
        q = DialogueRetryQueue(max_retries=3)
        q.enqueue("event", {"type": "DEATH"}, attempt_count=3)  # at limit
        q.enqueue("event", {"type": "CALLOUT"}, attempt_count=1)  # valid

        gen = self._make_generator()
        resubmitted = q.flush(gen)

        assert resubmitted == 1
        assert q.size == 0

        await asyncio.sleep(0.05)
        gen.generate_from_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_increments_attempt_count(self):
        """Re-submitted items have incremented attempt_count."""
        q = DialogueRetryQueue(max_retries=5)
        q.enqueue("event", {"type": "DEATH"}, attempt_count=2)

        gen = self._make_generator()

        # Capture what _retry_event sees
        with patch(
            "talker_service.dialogue.retry_queue._retry_event",
            new_callable=AsyncMock,
        ) as mock_retry:
            q.flush(gen)
            await asyncio.sleep(0.05)

            mock_retry.assert_called_once()
            call_args = mock_retry.call_args
            assert call_args[0][2] == 3  # attempt arg

    @pytest.mark.asyncio
    async def test_flush_atomic_no_duplicates(self):
        """Two flush calls process items exactly once."""
        q = DialogueRetryQueue(max_retries=5)
        q.enqueue("event", {"type": "DEATH"})

        gen = self._make_generator()
        count_1 = q.flush(gen)
        count_2 = q.flush(gen)

        assert count_1 == 1
        assert count_2 == 0


# ---------------------------------------------------------------------------
# DialogueRetryQueue.notify_heartbeat
# ---------------------------------------------------------------------------

class TestNotifyHeartbeat:
    """Tests for heartbeat gap detection."""

    def test_first_heartbeat_no_flush(self):
        """First heartbeat never triggers flush."""
        q = DialogueRetryQueue(heartbeat_interval=5.0)
        q.enqueue("event", {"type": "DEATH"})

        result = q.notify_heartbeat(time.time())
        assert result is False

    def test_normal_heartbeat_no_flush(self):
        """Heartbeat within normal interval does not trigger flush."""
        q = DialogueRetryQueue(heartbeat_interval=5.0)
        q.enqueue("event", {"type": "DEATH"})

        now = time.time()
        q.notify_heartbeat(now)
        result = q.notify_heartbeat(now + 4.0)  # within 2x = 10s
        assert result is False

    def test_gap_heartbeat_triggers_flush(self):
        """Heartbeat after a gap >= 2x interval signals flush."""
        q = DialogueRetryQueue(heartbeat_interval=5.0)
        q.enqueue("event", {"type": "DEATH"})

        now = time.time()
        q.notify_heartbeat(now)
        result = q.notify_heartbeat(now + 11.0)  # gap > 10s
        assert result is True

    def test_gap_heartbeat_empty_queue_no_flush(self):
        """Gap detected but empty queue — no flush signal."""
        q = DialogueRetryQueue(heartbeat_interval=5.0)

        now = time.time()
        q.notify_heartbeat(now)
        result = q.notify_heartbeat(now + 11.0)
        assert result is False


# ---------------------------------------------------------------------------
# DialogueRetryQueue.clear / size
# ---------------------------------------------------------------------------

class TestClearAndSize:
    """Tests for clear() and size property."""

    def test_clear_empties_queue(self):
        """clear() removes all items."""
        q = DialogueRetryQueue()
        q.enqueue("event", {"type": "DEATH"})
        q.enqueue("event", {"type": "CALLOUT"})
        assert q.size == 2

        q.clear()
        assert q.size == 0

    def test_size_reflects_queue_length(self):
        """size property matches number of enqueued items."""
        q = DialogueRetryQueue()
        assert q.size == 0
        q.enqueue("event", {"type": "A"})
        assert q.size == 1
        q.enqueue("event", {"type": "B"})
        assert q.size == 2
