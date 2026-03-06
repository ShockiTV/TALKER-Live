"""Tests for ContextBlock — append-only context block for LLM prompt caching."""

import pytest

from talker_service.dialogue.context_block import (
    BackgroundItem,
    ContextBlock,
    MemoryItem,
)


class TestContextBlockAdd:
    """Tests for add_background and add_memory mutations."""

    def test_add_background_returns_true(self):
        block = ContextBlock()
        assert block.add_background("w01", "Wolf", "Loners", "A lone wanderer.")

    def test_add_background_duplicate_returns_false(self):
        block = ContextBlock()
        block.add_background("w01", "Wolf", "Loners", "A lone wanderer.")
        assert not block.add_background("w01", "Wolf", "Loners", "Different text.")

    def test_add_background_different_ids(self):
        block = ContextBlock()
        assert block.add_background("w01", "Wolf", "Loners", "text")
        assert block.add_background("f01", "Fanatic", "Duty", "text2")
        assert block.bg_count == 2

    def test_add_memory_returns_true(self):
        block = ContextBlock()
        assert block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "Wolf recalls...")

    def test_add_memory_duplicate_returns_false(self):
        block = ContextBlock()
        block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "Wolf recalls...")
        assert not block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "Different text.")

    def test_add_memory_same_char_different_ts(self):
        block = ContextBlock()
        assert block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "text1")
        assert block.add_memory("w01", "Wolf", 2000, "DIGESTS", "text2")
        assert block.mem_count == 2

    def test_add_memory_same_ts_different_char(self):
        block = ContextBlock()
        assert block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "text1")
        assert block.add_memory("f01", "Fanatic", 1000, "SUMMARIES", "text2")
        assert block.mem_count == 2

    def test_duplicate_does_not_modify_items(self):
        block = ContextBlock()
        block.add_background("w01", "Wolf", "Loners", "text")
        assert block.item_count == 1
        block.add_background("w01", "Wolf", "Loners", "other text")
        assert block.item_count == 1  # unchanged


class TestContextBlockDedup:
    """Tests for has_background, has_memory, and missing query methods."""

    def test_has_background_present(self):
        block = ContextBlock()
        block.add_background("w01", "Wolf", "Loners", "text")
        assert block.has_background("w01")

    def test_has_background_absent(self):
        block = ContextBlock()
        assert not block.has_background("w01")

    def test_has_memory_present(self):
        block = ContextBlock()
        block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "text")
        assert block.has_memory("w01", 1000)

    def test_has_memory_absent(self):
        block = ContextBlock()
        assert not block.has_memory("w01", 1000)

    def test_has_memory_wrong_ts(self):
        block = ContextBlock()
        block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "text")
        assert not block.has_memory("w01", 2000)

    def test_has_memory_wrong_char(self):
        block = ContextBlock()
        block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "text")
        assert not block.has_memory("f01", 1000)

    def test_missing_all_absent(self):
        block = ContextBlock()
        assert block.missing(["a", "b", "c"]) == ["a", "b", "c"]

    def test_missing_some_present(self):
        block = ContextBlock()
        block.add_background("a", "A", "X", "t")
        block.add_background("c", "C", "X", "t")
        assert block.missing(["a", "b", "c"]) == ["b"]

    def test_missing_all_present(self):
        block = ContextBlock()
        block.add_background("a", "A", "X", "t")
        block.add_background("b", "B", "X", "t")
        assert block.missing(["a", "b"]) == []

    def test_missing_empty_input(self):
        block = ContextBlock()
        assert block.missing([]) == []


class TestContextBlockRender:
    """Tests for render_markdown output."""

    def test_empty_block_renders_empty_string(self):
        block = ContextBlock()
        assert block.render_markdown() == ""

    def test_background_format(self):
        block = ContextBlock()
        block.add_background("w01", "Wolf", "Loners", "A lone wanderer.")
        md = block.render_markdown()
        assert md == "## Wolf (Loners) [id:w01]\nA lone wanderer."

    def test_memory_format(self):
        block = ContextBlock()
        block.add_memory("w01", "Wolf", 1000, "SUMMARIES", "Wolf recalls the firefight.")
        md = block.render_markdown()
        assert md == "[SUMMARIES] Wolf [id:w01] @1000: Wolf recalls the firefight."

    def test_mixed_items_insertion_order(self):
        block = ContextBlock()
        block.add_background("a", "Alice", "Loners", "bg-a")
        block.add_memory("a", "Alice", 100, "SUMMARIES", "mem-a-1")
        block.add_background("b", "Bob", "Duty", "bg-b")
        block.add_memory("b", "Bob", 200, "DIGESTS", "mem-b-1")
        block.add_memory("a", "Alice", 300, "CORES", "mem-a-2")

        md = block.render_markdown()
        lines = md.split("\n\n")
        assert len(lines) == 5
        assert lines[0] == "## Alice (Loners) [id:a]\nbg-a"
        assert lines[1] == "[SUMMARIES] Alice [id:a] @100: mem-a-1"
        assert lines[2] == "## Bob (Duty) [id:b]\nbg-b"
        assert lines[3] == "[DIGESTS] Bob [id:b] @200: mem-b-1"
        assert lines[4] == "[CORES] Alice [id:a] @300: mem-a-2"

    def test_append_only_prefix_stability(self):
        """Adding items only extends the Markdown; existing prefix is unchanged."""
        block = ContextBlock()
        block.add_background("a", "Alice", "Loners", "bg-a")
        prefix_v1 = block.render_markdown()

        block.add_memory("a", "Alice", 100, "SUMMARIES", "mem")
        prefix_v2 = block.render_markdown()

        # v2 starts with v1
        assert prefix_v2.startswith(prefix_v1)
        # v2 is longer
        assert len(prefix_v2) > len(prefix_v1)


class TestContextBlockInspection:
    """Tests for inspection / helper properties."""

    def test_item_count(self):
        block = ContextBlock()
        assert block.item_count == 0
        block.add_background("a", "A", "X", "t")
        block.add_memory("a", "A", 1, "S", "t")
        assert block.item_count == 2

    def test_bg_count(self):
        block = ContextBlock()
        block.add_background("a", "A", "X", "t")
        block.add_background("b", "B", "X", "t")
        assert block.bg_count == 2

    def test_mem_count(self):
        block = ContextBlock()
        block.add_memory("a", "A", 1, "S", "t1")
        block.add_memory("a", "A", 2, "S", "t2")
        block.add_memory("b", "B", 1, "S", "t3")
        assert block.mem_count == 3

    def test_get_all_backgrounds(self):
        block = ContextBlock()
        block.add_background("a", "A", "X", "ta")
        block.add_memory("a", "A", 1, "S", "m")
        block.add_background("b", "B", "Y", "tb")
        bgs = block.get_all_backgrounds()
        assert len(bgs) == 2
        assert all(isinstance(b, BackgroundItem) for b in bgs)
        assert bgs[0].char_id == "a"
        assert bgs[1].char_id == "b"

    def test_get_all_memories(self):
        block = ContextBlock()
        block.add_background("a", "A", "X", "t")
        block.add_memory("a", "A", 1, "S", "m1")
        block.add_memory("b", "B", 2, "D", "m2")
        mems = block.get_all_memories()
        assert len(mems) == 2
        assert all(isinstance(m, MemoryItem) for m in mems)
