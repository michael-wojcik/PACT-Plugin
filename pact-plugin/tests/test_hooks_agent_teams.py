"""
Location: pact-plugin/tests/test_hooks_agent_teams.py
Summary: Tests for Agent Teams hooks (teammate_idle.py and task_completed.py).
Used by: pytest test suite for validating hook behavior.

Tests verify that both hooks behave as safe no-ops, allowing idle
and task completion respectively, until empirical validation confirms
TaskGet access from hooks.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path so we can import the hook modules
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import teammate_idle
import task_completed


# =============================================================================
# TeammateIdle Hook Tests
# =============================================================================

class TestTeammateIdleNoTeamContext:
    """Tests for teammate_idle when not in an Agent Teams context."""

    def test_exits_0_when_teammate_name_empty(self):
        """Returns exit 0 when TEAMMATE_NAME is empty."""
        env = {"TEAMMATE_NAME": "", "TEAM_NAME": "some-team"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                teammate_idle.main()
            assert exc_info.value.code == 0

    def test_exits_0_when_team_name_empty(self):
        """Returns exit 0 when TEAM_NAME is empty."""
        env = {"TEAMMATE_NAME": "pact-backend-coder", "TEAM_NAME": ""}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                teammate_idle.main()
            assert exc_info.value.code == 0

    def test_exits_0_when_both_empty(self):
        """Returns exit 0 when both env vars are missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                teammate_idle.main()
            assert exc_info.value.code == 0


class TestTeammateIdleNonPactAgent:
    """Tests for teammate_idle with non-PACT agent names."""

    def test_exits_0_for_non_pact_agent(self):
        """Returns exit 0 when teammate name does NOT start with 'pact-'."""
        env = {"TEAMMATE_NAME": "custom-agent", "TEAM_NAME": "my-team"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                teammate_idle.main()
            assert exc_info.value.code == 0

    def test_exits_0_for_random_agent_name(self):
        """Non-pact agent names pass through (exit 0)."""
        env = {"TEAMMATE_NAME": "researcher-1", "TEAM_NAME": "feature-team"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                teammate_idle.main()
            assert exc_info.value.code == 0


class TestTeammateIdlePactAgent:
    """Tests for teammate_idle with PACT specialist agent names."""

    def test_exits_0_for_pact_backend_coder(self, capsys):
        """Returns exit 0 when teammate IS a pact- agent (with reminder)."""
        env = {"TEAMMATE_NAME": "pact-backend-coder", "TEAM_NAME": "auth-feature"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                teammate_idle.main()
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            assert "Reminder" in captured.out
            assert "handoff" in captured.out.lower()

    def test_exits_0_for_pact_test_engineer(self, capsys):
        """Returns exit 0 for pact-test-engineer with reminder message."""
        env = {"TEAMMATE_NAME": "pact-test-engineer", "TEAM_NAME": "auth-feature"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                teammate_idle.main()
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            assert "Reminder" in captured.out

    def test_exits_0_for_pact_architect(self, capsys):
        """Returns exit 0 for pact-architect with reminder message."""
        env = {"TEAMMATE_NAME": "pact-architect", "TEAM_NAME": "design-team"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                teammate_idle.main()
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            assert len(captured.out) > 0

    def test_reminder_mentions_task_update(self, capsys):
        """Reminder message mentions TaskUpdate for storing handoff."""
        env = {"TEAMMATE_NAME": "pact-frontend-coder", "TEAM_NAME": "ui-team"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                teammate_idle.main()
            captured = capsys.readouterr()
            assert "TaskUpdate" in captured.out

    def test_reminder_mentions_send_message(self, capsys):
        """Reminder message mentions SendMessage for completion signal."""
        env = {"TEAMMATE_NAME": "pact-database-engineer", "TEAM_NAME": "data-team"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                teammate_idle.main()
            captured = capsys.readouterr()
            assert "SendMessage" in captured.out


# =============================================================================
# TaskCompleted Hook Tests
# =============================================================================

class TestTaskCompletedNoTeamContext:
    """Tests for task_completed when not in an Agent Teams context."""

    def test_exits_0_when_teammate_name_empty(self):
        """Returns exit 0 when TEAMMATE_NAME is empty."""
        env = {"TEAMMATE_NAME": "", "TASK_SUBJECT": "Some task"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0

    def test_exits_0_when_teammate_name_missing(self):
        """Returns exit 0 when TEAMMATE_NAME env var is not set."""
        env = {"TASK_SUBJECT": "Some task"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0


class TestTaskCompletedNonPactAgent:
    """Tests for task_completed with non-PACT agent names."""

    def test_exits_0_for_non_pact_agent(self):
        """Returns exit 0 when teammate name does NOT start with 'pact-'."""
        env = {"TEAMMATE_NAME": "custom-agent", "TASK_SUBJECT": "Do something"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0


class TestTaskCompletedPhaseAndSignalPrefixes:
    """Tests for task_completed with phase and signal prefix tasks."""

    @pytest.mark.parametrize("prefix", [
        "PREPARE:", "ARCHITECT:", "CODE:", "TEST:",
    ])
    def test_exits_0_for_phase_prefix(self, prefix):
        """Returns exit 0 for phase prefix tasks."""
        env = {
            "TEAMMATE_NAME": "pact-backend-coder",
            "TASK_SUBJECT": f"{prefix} Implement auth module",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0

    @pytest.mark.parametrize("prefix", [
        "BLOCKER:", "HALT:", "ALERT:",
    ])
    def test_exits_0_for_signal_prefix(self, prefix):
        """Returns exit 0 for signal prefix tasks."""
        env = {
            "TEAMMATE_NAME": "pact-test-engineer",
            "TASK_SUBJECT": f"{prefix} Critical issue found",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0

    def test_exits_0_for_quarantine_prefix(self):
        """Returns exit 0 for QUARANTINE: prefix tasks."""
        env = {
            "TEAMMATE_NAME": "pact-architect",
            "TASK_SUBJECT": "QUARANTINE: Stalled task",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0


class TestTaskCompletedPactSpecialist:
    """Tests for task_completed with regular PACT specialist tasks."""

    def test_exits_0_for_regular_pact_task(self):
        """Returns exit 0 for regular PACT specialist tasks (placeholder)."""
        env = {
            "TEAMMATE_NAME": "pact-backend-coder",
            "TASK_SUBJECT": "Implement auth endpoint",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0

    def test_exits_0_for_frontend_coder_task(self):
        """Returns exit 0 for pact-frontend-coder task (placeholder)."""
        env = {
            "TEAMMATE_NAME": "pact-frontend-coder",
            "TASK_SUBJECT": "Build login form component",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0

    def test_exits_0_for_database_engineer_task(self):
        """Returns exit 0 for pact-database-engineer task (placeholder)."""
        env = {
            "TEAMMATE_NAME": "pact-database-engineer",
            "TASK_SUBJECT": "Create users table migration",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                task_completed.main()
            assert exc_info.value.code == 0
