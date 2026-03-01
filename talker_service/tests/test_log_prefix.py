"""Tests for the log_prefix helper function."""

import pytest

from talker_service.handlers._log import log_prefix


class TestLogPrefix:
    """Verify log_prefix produces correct output for all combinations."""

    def test_empty_returns_empty_string(self):
        assert log_prefix() == ""

    def test_req_id_only(self):
        assert log_prefix(req_id=5) == "[R:5] "

    def test_req_id_with_session(self):
        assert log_prefix(req_id=5, session_id="player_1") == "[R:5 S:player_1] "

    def test_req_id_with_session_and_dialogue(self):
        assert log_prefix(req_id=5, session_id="player_1", dialogue_id=3) == "[R:5 S:player_1 D#3] "

    def test_default_session_omits_s_segment(self):
        assert log_prefix(req_id=5, session_id="__default__") == "[R:5] "

    def test_default_session_with_dialogue_omits_s(self):
        assert log_prefix(req_id=5, session_id="__default__", dialogue_id=3) == "[R:5 D#3] "

    def test_dialogue_id_only(self):
        """Background tasks (memory compression) use D# only."""
        assert log_prefix(dialogue_id=3) == "[D#3] "

    def test_req_id_zero_omitted(self):
        """req_id=0 is treated as absent."""
        assert log_prefix(req_id=0) == ""

    def test_req_id_zero_with_dialogue(self):
        assert log_prefix(req_id=0, dialogue_id=7) == "[D#7] "

    def test_none_session_omits_s_segment(self):
        assert log_prefix(req_id=10, session_id=None) == "[R:10] "

    def test_dialogue_id_zero_is_included(self):
        """dialogue_id=0 is a valid ID and should be included."""
        assert log_prefix(req_id=1, dialogue_id=0) == "[R:1 D#0] "
