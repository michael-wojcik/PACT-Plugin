"""
Tests for session_init.py — SessionStart hook.

Tests cover:
generate_team_name():
1. Happy path: session_id from input_data -> "PACT-{first 8 chars}"
2. Env var fallback: CLAUDE_SESSION_ID used when input_data has no session_id
3. Random fallback: random hex suffix when neither source available
4. Short session_id: less than 8 chars used as-is
5. Empty session_id: treated as falsy, falls back to env or random
6. Input_data session_id takes precedence over env var
7. Output format validation (PACT- prefix, hex suffix)
8. None session_id: treated as falsy, falls back to random

restore_last_session():
9. Returns None if no snapshot file exists
10. Returns content with header if file exists
11. Rotates file to last-session.prev.md
12. Returns None if project_slug is empty
13. Returns None if snapshot file is empty
"""

import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


class TestGenerateTeamName:
    """Tests for generate_team_name() -- session-unique team name generation."""

    def test_uses_session_id_from_input_data(self):
        """Should return PACT- followed by first 8 chars of session_id."""
        from session_init import generate_team_name

        result = generate_team_name({"session_id": "0001639f-a74f-41c4-bd0b-93d9d206e7f7"})

        assert result == "PACT-0001639f"

    def test_truncates_session_id_to_8_chars(self):
        """Should use only the first 8 characters of a long session_id."""
        from session_init import generate_team_name

        result = generate_team_name({"session_id": "abcdef1234567890"})

        assert result == "PACT-abcdef12"

    def test_env_var_fallback_when_no_session_id_in_input(self, monkeypatch):
        """Should fall back to CLAUDE_SESSION_ID env var when input_data lacks session_id."""
        from session_init import generate_team_name

        monkeypatch.setenv("CLAUDE_SESSION_ID", "deadbeef-1234-5678-9abc-def012345678")

        result = generate_team_name({})

        assert result == "PACT-deadbeef"

    def test_env_var_fallback_when_session_id_key_missing(self, monkeypatch):
        """Should fall back to env var when session_id key is absent from input_data."""
        from session_init import generate_team_name

        monkeypatch.setenv("CLAUDE_SESSION_ID", "cafebabe-0000-1111-2222-333344445555")

        result = generate_team_name({"other_key": "value"})

        assert result == "PACT-cafebabe"

    def test_random_fallback_when_no_session_id_anywhere(self, monkeypatch):
        """Should generate random hex suffix when neither source provides session_id."""
        from session_init import generate_team_name

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        result = generate_team_name({})

        assert result.startswith("PACT-")
        suffix = result[len("PACT-"):]
        assert len(suffix) == 8
        assert re.fullmatch(r"[a-f0-9]{8}", suffix), f"Expected hex suffix, got: {suffix}"

    def test_random_fallback_produces_different_values(self, monkeypatch):
        """Random fallback should produce different names across calls (probabilistic)."""
        from session_init import generate_team_name

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        results = {generate_team_name({}) for _ in range(10)}

        assert len(results) > 1, "Expected different random names across 10 calls"

    def test_short_session_id_used_as_is(self):
        """Should use the full session_id when shorter than 8 chars."""
        from session_init import generate_team_name

        result = generate_team_name({"session_id": "abc"})

        assert result == "PACT-abc"

    def test_empty_session_id_falls_back_to_env(self, monkeypatch):
        """Empty string session_id should be treated as falsy, falling back to env var."""
        from session_init import generate_team_name

        monkeypatch.setenv("CLAUDE_SESSION_ID", "feedface-0000-1111-2222-333344445555")

        result = generate_team_name({"session_id": ""})

        assert result == "PACT-feedface"

    def test_empty_session_id_falls_back_to_random(self, monkeypatch):
        """Empty string session_id with no env var should fall back to random."""
        from session_init import generate_team_name

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        result = generate_team_name({"session_id": ""})

        assert result.startswith("PACT-")
        suffix = result[len("PACT-"):]
        assert len(suffix) == 8
        assert re.fullmatch(r"[a-f0-9]{8}", suffix)

    def test_input_data_takes_precedence_over_env_var(self, monkeypatch):
        """session_id from input_data should take priority over CLAUDE_SESSION_ID env var."""
        from session_init import generate_team_name

        monkeypatch.setenv("CLAUDE_SESSION_ID", "envenvev-0000-1111-2222-333344445555")

        result = generate_team_name({"session_id": "inputinp-aaaa-bbbb-cccc-ddddeeeeffff"})

        assert result == "PACT-inputinp"

    def test_exactly_8_char_session_id(self):
        """Should handle a session_id that is exactly 8 characters."""
        from session_init import generate_team_name

        result = generate_team_name({"session_id": "a1b2c3d4"})

        assert result == "PACT-a1b2c3d4"

    def test_none_session_id_falls_to_random(self, monkeypatch):
        """None session_id in input_data should fall back to random."""
        from session_init import generate_team_name

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        result = generate_team_name({"session_id": None})

        assert result.startswith("PACT-")
        suffix = result[len("PACT-"):]
        assert len(suffix) == 8
        assert re.fullmatch(r"[a-f0-9]{8}", suffix)

    def test_return_type_is_string(self):
        """Should always return a string."""
        from session_init import generate_team_name

        result = generate_team_name({"session_id": "test1234"})

        assert isinstance(result, str)


class TestRestoreLastSession:
    """Tests for restore_last_session() -- cross-session continuity."""

    def test_returns_none_when_no_snapshot(self, tmp_path):
        """Should return None when no last-session.md exists."""
        from session_init import restore_last_session

        result = restore_last_session(
            project_slug="nonexistent",
            sessions_dir=str(tmp_path),
        )

        assert result is None

    def test_returns_content_with_header(self, tmp_path):
        """Should return snapshot content with descriptive header."""
        from session_init import restore_last_session

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        snapshot = "# Last Session: 2026-02-18 10:00 UTC\n## Completed Tasks\n- #1 auth\n"
        (proj_dir / "last-session.md").write_text(snapshot)

        result = restore_last_session(
            project_slug="my-project",
            sessions_dir=str(tmp_path),
        )

        assert result is not None
        assert "Previous session summary" in result
        assert "read-only reference" in result
        assert "# Last Session:" in result
        assert "#1 auth" in result

    def test_rotates_file_to_prev(self, tmp_path):
        """Should move last-session.md to last-session.prev.md after reading."""
        from session_init import restore_last_session

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        snapshot_content = "# Last Session: 2026-02-18\n## Completed Tasks\n- #1 test\n"
        (proj_dir / "last-session.md").write_text(snapshot_content)

        restore_last_session(
            project_slug="my-project",
            sessions_dir=str(tmp_path),
        )

        # Original file should be removed
        assert not (proj_dir / "last-session.md").exists()
        # Prev file should contain the content
        prev_file = proj_dir / "last-session.prev.md"
        assert prev_file.exists()
        assert prev_file.read_text() == snapshot_content

    def test_returns_none_when_empty_slug(self, tmp_path):
        """Should return None when project_slug is empty."""
        from session_init import restore_last_session

        result = restore_last_session(
            project_slug="",
            sessions_dir=str(tmp_path),
        )

        assert result is None

    def test_returns_none_when_empty_file(self, tmp_path):
        """Should return None when snapshot file exists but is empty."""
        from session_init import restore_last_session

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        (proj_dir / "last-session.md").write_text("")

        result = restore_last_session(
            project_slug="my-project",
            sessions_dir=str(tmp_path),
        )

        assert result is None

    def test_overwrites_existing_prev_file(self, tmp_path):
        """Should overwrite any existing last-session.prev.md during rotation."""
        from session_init import restore_last_session

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        (proj_dir / "last-session.prev.md").write_text("old prev content")
        new_content = "# Last Session: new\n## Completed Tasks\n- #2 new\n"
        (proj_dir / "last-session.md").write_text(new_content)

        restore_last_session(
            project_slug="my-project",
            sessions_dir=str(tmp_path),
        )

        # Prev file should have new content, not old
        assert (proj_dir / "last-session.prev.md").read_text() == new_content
