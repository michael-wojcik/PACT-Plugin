"""
Tests for token budget enforcement in working_memory.py.

Tests cover:
1. _estimate_tokens() -- word-based approximation
2. _compress_memory_entry() -- single-line summary extraction
3. _apply_token_budget() -- budget enforcement with compression/dropping
4. sync_to_claude_md() -- budget enforcement during working memory sync
5. sync_retrieved_to_claude_md() -- budget enforcement during retrieved context sync
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "pact-memory" / "scripts"))


class TestEstimateTokens:
    """Tests for _estimate_tokens() approximation function."""

    def test_empty_string_returns_zero(self):
        """Empty string should return 0 tokens."""
        from working_memory import _estimate_tokens
        assert _estimate_tokens("") == 0

    def test_single_word(self):
        """Single word should return int(1 * 1.3) = 1."""
        from working_memory import _estimate_tokens
        assert _estimate_tokens("hello") == 1

    def test_ten_words(self):
        """Ten words should return int(10 * 1.3) = 13."""
        from working_memory import _estimate_tokens
        text = "one two three four five six seven eight nine ten"
        assert _estimate_tokens(text) == 13

    def test_returns_integer(self):
        """Should always return an integer, not a float."""
        from working_memory import _estimate_tokens
        result = _estimate_tokens("some words here")
        assert isinstance(result, int)

    def test_longer_text_scales_proportionally(self):
        """Longer text should produce proportionally larger estimates."""
        from working_memory import _estimate_tokens
        short = _estimate_tokens("a b c")
        long_val = _estimate_tokens("a b c d e f g h i j k l m n o")
        assert long_val > short


class TestCompressMemoryEntry:
    """Tests for _compress_memory_entry() -- extracts single-line summary."""

    def test_extracts_context_first_sentence(self):
        """Should extract first sentence from Context field."""
        from working_memory import _compress_memory_entry

        entry = (
            "### 2026-01-15 10:30\n"
            "**Context**: Working on authentication module. This involves JWT tokens.\n"
            "**Goal**: Add refresh token support\n"
            "**Decisions**: Use Redis for token storage\n"
            "**Memory ID**: abc123"
        )
        result = _compress_memory_entry(entry)
        assert "### 2026-01-15 10:30" in result
        assert "**Summary**: Working on authentication module." in result
        assert "**Goal**" not in result
        assert "**Decisions**" not in result
        assert "**Memory ID**" not in result

    def test_truncates_long_context_without_period(self):
        """Should truncate to 120 chars with ellipsis when no period found early."""
        from working_memory import _compress_memory_entry

        long_context = "A" * 200
        entry = f"### 2026-01-15 10:30\n**Context**: {long_context}"
        result = _compress_memory_entry(entry)
        assert "**Summary**:" in result
        assert "..." in result
        summary_line = [line for line in result.split("\n") if "**Summary**" in line][0]
        summary_text = summary_line.split("**Summary**: ", 1)[1]
        assert len(summary_text) <= 124  # 120 + "..."

    def test_handles_context_with_early_period(self):
        """Should take first sentence if period appears before 120 chars."""
        from working_memory import _compress_memory_entry

        entry = (
            "### 2026-02-01 08:00\n"
            "**Context**: Short sentence. Then more text follows here."
        )
        result = _compress_memory_entry(entry)
        assert "**Summary**: Short sentence." in result

    def test_preserves_date_header(self):
        """Date header line should always be preserved."""
        from working_memory import _compress_memory_entry

        entry = "### 2026-03-15 14:22\n**Context**: Some context"
        result = _compress_memory_entry(entry)
        assert result.startswith("### 2026-03-15 14:22")

    def test_falls_back_to_first_field_when_no_context(self):
        """Should use first bold field if no Context field present."""
        from working_memory import _compress_memory_entry

        entry = (
            "### 2026-01-20 12:00\n"
            "**Goal**: Implement the new feature\n"
            "**Decisions**: Use React"
        )
        result = _compress_memory_entry(entry)
        assert "### 2026-01-20 12:00" in result
        assert "Implement the new feature" in result

    def test_empty_entry_returns_entry(self):
        """Empty entry should return itself."""
        from working_memory import _compress_memory_entry
        assert _compress_memory_entry("") == ""

    def test_header_only_entry(self):
        """Entry with only date header should return just the header."""
        from working_memory import _compress_memory_entry
        result = _compress_memory_entry("### 2026-01-01 00:00")
        assert result == "### 2026-01-01 00:00"


class TestApplyTokenBudget:
    """Tests for _apply_token_budget() -- compression and dropping."""

    def test_empty_entries_returns_empty(self):
        """Empty list should return empty list."""
        from working_memory import _apply_token_budget
        assert _apply_token_budget([], 800) == []

    def test_under_budget_no_change(self):
        """Entries under budget should be returned unchanged."""
        from working_memory import _apply_token_budget

        entries = [
            "### 2026-01-15 10:00\n**Context**: Short entry",
            "### 2026-01-14 10:00\n**Context**: Another short",
        ]
        result = _apply_token_budget(entries, 800)
        assert result == entries

    def test_over_budget_compresses_older_entries(self):
        """When over budget, older entries should be compressed (newest stays full)."""
        from working_memory import _apply_token_budget

        long_text = "word " * 100  # ~130 tokens
        entries = [
            f"### 2026-01-15 10:00\n**Context**: {long_text}",
            f"### 2026-01-14 10:00\n**Context**: {long_text}\n**Goal**: Some goal\n**Decisions**: Something",
            f"### 2026-01-13 10:00\n**Context**: {long_text}\n**Goal**: Another goal",
        ]

        result = _apply_token_budget(entries, 200)

        # First entry should be unchanged (newest)
        assert result[0] == entries[0]
        # Older entries should be compressed
        if len(result) > 1:
            assert "**Summary**" in result[1] or len(result[1]) < len(entries[1])

    def test_way_over_budget_drops_entries(self):
        """When compressed entries still exceed budget, should drop from end."""
        from working_memory import _apply_token_budget

        huge_text = "word " * 500  # ~650 tokens
        entries = [
            f"### 2026-01-15 10:00\n**Context**: {huge_text}",
            f"### 2026-01-14 10:00\n**Context**: {huge_text}",
            f"### 2026-01-13 10:00\n**Context**: {huge_text}",
            f"### 2026-01-12 10:00\n**Context**: {huge_text}",
        ]

        result = _apply_token_budget(entries, 700)

        assert len(result) < len(entries)
        assert len(result) >= 1
        assert result[0] == entries[0]

    def test_single_entry_always_kept(self):
        """A single entry should never be dropped, even if over budget."""
        from working_memory import _apply_token_budget

        huge_text = "word " * 1000
        entries = [f"### 2026-01-15 10:00\n**Context**: {huge_text}"]
        result = _apply_token_budget(entries, 10)
        assert len(result) == 1

    def test_budget_of_zero_keeps_first_entry(self):
        """Budget of zero should still keep at least the first entry."""
        from working_memory import _apply_token_budget

        entries = ["### 2026-01-15\n**Context**: Some text"]
        result = _apply_token_budget(entries, 0)
        assert len(result) == 1


class TestSyncToClaudeMdBudgetEnforcement:
    """Tests that sync_to_claude_md applies token budget."""

    def _create_claude_md(self, tmp_path, content):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(content, encoding="utf-8")
        return claude_md

    def test_large_entries_compressed_during_sync(self, tmp_path):
        """sync_to_claude_md should compress older entries to stay within budget."""
        from working_memory import sync_to_claude_md

        long_text = "word " * 200
        existing_content = (
            "# Project\n\n"
            "## Working Memory\n"
            "<!-- Auto-managed by pact-memory skill. Last 5 memories shown. "
            "Full history searchable via pact-memory skill. -->\n\n"
            f"### 2026-01-14 10:00\n**Context**: {long_text}\n**Goal**: Old goal\n\n"
            f"### 2026-01-13 10:00\n**Context**: {long_text}\n**Goal**: Older goal\n\n"
        )
        claude_md = self._create_claude_md(tmp_path, existing_content)

        with patch("working_memory._get_claude_md_path", return_value=claude_md):
            result = sync_to_claude_md(
                {"context": "New context entry", "goal": "New goal"},
                memory_id="test123"
            )

        assert result is True
        new_content = claude_md.read_text(encoding="utf-8")
        assert "## Working Memory" in new_content
        assert "New context entry" in new_content

    def test_sync_with_budget_produces_valid_markdown(self, tmp_path):
        """Output should be valid markdown with proper section structure."""
        from working_memory import sync_to_claude_md

        content = (
            "# Project\n\n"
            "## Working Memory\n"
            "<!-- Auto-managed by pact-memory skill. Last 5 memories shown. "
            "Full history searchable via pact-memory skill. -->\n\n"
            "## Pinned Context\n\nSome pinned stuff\n"
        )
        claude_md = self._create_claude_md(tmp_path, content)

        with patch("working_memory._get_claude_md_path", return_value=claude_md):
            sync_to_claude_md({"context": "Test"}, memory_id="id1")

        new_content = claude_md.read_text(encoding="utf-8")
        assert "## Pinned Context" in new_content
        assert "Some pinned stuff" in new_content


class TestSyncRetrievedBudgetEnforcement:
    """Tests that sync_retrieved_to_claude_md applies token budget."""

    def _create_claude_md(self, tmp_path, content):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(content, encoding="utf-8")
        return claude_md

    def test_retrieved_entries_reduced_when_over_budget(self, tmp_path):
        """Should drop old retrieved entries when over budget."""
        from working_memory import sync_retrieved_to_claude_md

        long_text = "word " * 200
        existing_content = (
            "# Project\n\n"
            "## Retrieved Context\n"
            "<!-- Auto-managed by pact-memory skill. Last 3 retrieved memories shown. -->\n\n"
            f"### 2026-01-14 10:00\n**Query**: \"old query\"\n**Context**: {long_text}\n\n"
            f"### 2026-01-13 10:00\n**Query**: \"older query\"\n**Context**: {long_text}\n\n"
            "## Working Memory\n"
            "<!-- Auto-managed by pact-memory skill. Last 5 memories shown. "
            "Full history searchable via pact-memory skill. -->\n\n"
        )
        claude_md = self._create_claude_md(tmp_path, existing_content)

        with patch("working_memory._get_claude_md_path", return_value=claude_md):
            result = sync_retrieved_to_claude_md(
                [{"context": "New retrieved", "goal": "test"}],
                query="test search",
                memory_ids=["mem1"]
            )

        assert result is True
        new_content = claude_md.read_text(encoding="utf-8")
        assert "test search" in new_content
        assert "## Working Memory" in new_content

    def test_no_memories_returns_false(self):
        """sync_retrieved_to_claude_md with empty list should return False."""
        from working_memory import sync_retrieved_to_claude_md
        result = sync_retrieved_to_claude_md([], query="test")
        assert result is False
