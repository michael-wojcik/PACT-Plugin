# pact-plugin/tests/test_session_end.py
"""
Tests for session_end.py — SessionEnd hook that logs session metadata.

Tests cover:
1. Logs session metadata to pact-session-log.json (append-only)
2. Creates log file if it doesn't exist
3. Handles missing environment variables gracefully
4. Log entry contains required fields (timestamp, project_slug, team_name)
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


class TestSessionEnd:
    """Tests for session_end.log_session_metadata()."""

    def test_creates_log_file_if_missing(self, tmp_path):
        from session_end import log_session_metadata

        log_file = tmp_path / "pact-session-log.json"

        log_session_metadata(
            project_slug="test-project",
            team_name="PACT-abc12345",
            log_path=str(log_file)
        )

        assert log_file.exists()
        entries = json.loads(log_file.read_text())
        assert len(entries) == 1
        assert entries[0]["project_slug"] == "test-project"
        assert entries[0]["team_name"] == "PACT-abc12345"
        assert "timestamp" in entries[0]

    def test_appends_to_existing_log(self, tmp_path):
        from session_end import log_session_metadata

        log_file = tmp_path / "pact-session-log.json"
        log_file.write_text('[{"timestamp": "2026-01-01", "project_slug": "old"}]')

        log_session_metadata(
            project_slug="new-project",
            team_name="PACT-def67890",
            log_path=str(log_file)
        )

        entries = json.loads(log_file.read_text())
        assert len(entries) == 2
        assert entries[1]["project_slug"] == "new-project"

    def test_handles_missing_values_gracefully(self, tmp_path):
        from session_end import log_session_metadata

        log_file = tmp_path / "pact-session-log.json"

        log_session_metadata(
            project_slug="",
            team_name="",
            log_path=str(log_file)
        )

        entries = json.loads(log_file.read_text())
        assert len(entries) == 1
        assert entries[0]["project_slug"] == ""


class TestGetProjectSlug:
    """Tests for session_end.get_project_slug()."""

    def test_returns_basename_from_env(self):
        from session_end import get_project_slug

        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": "/Users/mj/Sites/my-project"}):
            assert get_project_slug() == "my-project"

    def test_returns_empty_when_no_env(self):
        from session_end import get_project_slug

        with patch.dict("os.environ", {}, clear=True):
            assert get_project_slug() == ""
