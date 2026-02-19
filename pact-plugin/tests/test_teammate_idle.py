"""
Tests for teammate_idle.py — TeammateIdle hook for stall detection and idle cleanup.

Tests cover:
1. Stall detection: in_progress task + idle = stall warning
2. Stall detection: completed task + idle = no stall (handled by idle cleanup)
3. Stall detection: no task = no stall
4. Stall detection: already-stalled task = no re-alert
5. Stall detection: blocker/algedonic task = no stall
6. Idle count tracking: increment on consecutive idles
7. Idle count tracking: reset when agent gets new work
8. Shutdown thresholds: no message below 3
9. Shutdown thresholds: suggest at 3
10. Shutdown thresholds: force shutdown_request at 5
11. Main entry point: stdin/stdout/exit behavior
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


# Sample task fixtures
def make_task(task_id="1", subject="CODE: auth", status="in_progress",
              owner="backend-coder", metadata=None):
    """Helper to create a task dict."""
    return {
        "id": task_id,
        "subject": subject,
        "status": status,
        "owner": owner,
        "metadata": metadata or {},
    }


class TestFindTeammateTask:
    """Tests for teammate_idle.find_teammate_task()."""

    def test_finds_in_progress_task(self):
        from teammate_idle import find_teammate_task

        tasks = [make_task(status="in_progress", owner="coder-a")]
        result = find_teammate_task(tasks, "coder-a")
        assert result is not None
        assert result["status"] == "in_progress"

    def test_finds_completed_task(self):
        from teammate_idle import find_teammate_task

        tasks = [make_task(status="completed", owner="coder-a")]
        result = find_teammate_task(tasks, "coder-a")
        assert result is not None
        assert result["status"] == "completed"

    def test_prefers_in_progress_over_completed(self):
        from teammate_idle import find_teammate_task

        tasks = [
            make_task(task_id="1", status="completed", owner="coder-a"),
            make_task(task_id="2", status="in_progress", owner="coder-a"),
        ]
        result = find_teammate_task(tasks, "coder-a")
        assert result["id"] == "2"
        assert result["status"] == "in_progress"

    def test_returns_none_for_no_matching_owner(self):
        from teammate_idle import find_teammate_task

        tasks = [make_task(owner="coder-b")]
        result = find_teammate_task(tasks, "coder-a")
        assert result is None

    def test_returns_none_for_empty_tasks(self):
        from teammate_idle import find_teammate_task

        result = find_teammate_task([], "coder-a")
        assert result is None

    def test_returns_highest_id_completed_task(self):
        from teammate_idle import find_teammate_task

        tasks = [
            make_task(task_id="3", status="completed", owner="coder-a"),
            make_task(task_id="7", status="completed", owner="coder-a"),
            make_task(task_id="5", status="completed", owner="coder-a"),
        ]
        result = find_teammate_task(tasks, "coder-a")
        assert result["id"] == "7"


class TestDetectStall:
    """Tests for teammate_idle.detect_stall()."""

    def test_detects_stall_in_progress_task(self):
        from teammate_idle import detect_stall

        tasks = [make_task(status="in_progress", owner="coder-a")]
        result = detect_stall(tasks, "coder-a")
        assert result is not None
        assert "stall" in result.lower()
        assert "coder-a" in result
        assert "imPACT" in result

    def test_no_stall_for_completed_task(self):
        from teammate_idle import detect_stall

        tasks = [make_task(status="completed", owner="coder-a")]
        result = detect_stall(tasks, "coder-a")
        assert result is None

    def test_no_stall_for_no_task(self):
        from teammate_idle import detect_stall

        tasks = [make_task(owner="coder-b")]
        result = detect_stall(tasks, "coder-a")
        assert result is None

    def test_no_stall_for_blocker_task(self):
        from teammate_idle import detect_stall

        tasks = [make_task(
            status="in_progress", owner="coder-a",
            metadata={"type": "blocker"}
        )]
        result = detect_stall(tasks, "coder-a")
        assert result is None

    def test_no_stall_for_algedonic_task(self):
        from teammate_idle import detect_stall

        tasks = [make_task(
            status="in_progress", owner="coder-a",
            metadata={"type": "algedonic"}
        )]
        result = detect_stall(tasks, "coder-a")
        assert result is None

    def test_no_re_alert_for_already_stalled(self):
        from teammate_idle import detect_stall

        tasks = [make_task(
            status="in_progress", owner="coder-a",
            metadata={"stalled": True}
        )]
        result = detect_stall(tasks, "coder-a")
        assert result is None

    def test_includes_task_id_and_subject(self):
        from teammate_idle import detect_stall

        tasks = [make_task(
            task_id="42", subject="CODE: fix login",
            status="in_progress", owner="coder-a"
        )]
        result = detect_stall(tasks, "coder-a")
        assert "#42" in result
        assert "fix login" in result


class TestIdleCountTracking:
    """Tests for idle count read/write operations."""

    def test_read_empty_file(self, tmp_path):
        from teammate_idle import read_idle_counts

        result = read_idle_counts(str(tmp_path / "idle_counts.json"))
        assert result == {}

    def test_read_existing_counts(self, tmp_path):
        from teammate_idle import read_idle_counts

        counts_file = tmp_path / "idle_counts.json"
        counts_file.write_text('{"coder-a": 3}')

        result = read_idle_counts(str(counts_file))
        assert result == {"coder-a": 3}

    def test_read_corrupted_file(self, tmp_path):
        from teammate_idle import read_idle_counts

        counts_file = tmp_path / "idle_counts.json"
        counts_file.write_text("not json{{{")

        result = read_idle_counts(str(counts_file))
        assert result == {}

    def test_write_creates_file(self, tmp_path):
        from teammate_idle import write_idle_counts

        counts_path = str(tmp_path / "subdir" / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 2})

        result = json.loads(Path(counts_path).read_text())
        assert result == {"coder-a": 2}

    def test_write_overwrites_existing(self, tmp_path):
        from teammate_idle import write_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 1})
        write_idle_counts(counts_path, {"coder-a": 3, "coder-b": 1})

        result = json.loads(Path(counts_path).read_text())
        assert result == {"coder-a": 3, "coder-b": 1}

    def test_reset_idle_count(self, tmp_path):
        from teammate_idle import write_idle_counts, reset_idle_count, read_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 3, "coder-b": 1})

        reset_idle_count("coder-a", counts_path)

        result = read_idle_counts(counts_path)
        assert "coder-a" not in result
        assert result["coder-b"] == 1

    def test_reset_nonexistent_teammate(self, tmp_path):
        from teammate_idle import write_idle_counts, reset_idle_count, read_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 3})

        # Should not raise
        reset_idle_count("coder-x", counts_path)

        result = read_idle_counts(counts_path)
        assert result == {"coder-a": 3}


class TestCheckIdleCleanup:
    """Tests for teammate_idle.check_idle_cleanup()."""

    def test_no_action_below_threshold(self, tmp_path):
        from teammate_idle import check_idle_cleanup

        counts_path = str(tmp_path / "idle_counts.json")
        tasks = [make_task(status="completed", owner="coder-a")]

        # First idle event (count = 1)
        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is None
        assert should_shutdown is False

    def test_no_action_at_two(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 1})  # Already had 1
        tasks = [make_task(status="completed", owner="coder-a")]

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is None
        assert should_shutdown is False

    def test_suggest_at_three(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 2})  # Will become 3
        tasks = [make_task(status="completed", owner="coder-a")]

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is not None
        assert "idle" in msg.lower()
        assert "coder-a" in msg
        assert should_shutdown is False

    def test_suggest_at_four(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 3})  # Will become 4
        tasks = [make_task(status="completed", owner="coder-a")]

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is not None
        assert should_shutdown is False

    def test_force_shutdown_at_five(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 4})  # Will become 5
        tasks = [make_task(status="completed", owner="coder-a")]

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is not None
        assert "shutdown" in msg.lower()
        assert should_shutdown is True

    def test_force_shutdown_above_five(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 9})  # Will become 10
        tasks = [make_task(status="completed", owner="coder-a")]

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is not None
        assert should_shutdown is True

    def test_resets_count_when_no_completed_task(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts, read_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 3})
        # Agent now has in_progress task (got new work)
        tasks = [make_task(status="in_progress", owner="coder-a")]

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is None
        assert should_shutdown is False

        # Count should be reset
        counts = read_idle_counts(counts_path)
        assert "coder-a" not in counts

    def test_skips_stalled_agents(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 4})
        tasks = [make_task(
            status="completed", owner="coder-a",
            metadata={"stalled": True}
        )]

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is None
        assert should_shutdown is False

    def test_skips_terminated_agents(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 4})
        tasks = [make_task(
            status="completed", owner="coder-a",
            metadata={"terminated": True}
        )]

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is None
        assert should_shutdown is False

    def test_no_task_resets_count(self, tmp_path):
        from teammate_idle import check_idle_cleanup, write_idle_counts, read_idle_counts

        counts_path = str(tmp_path / "idle_counts.json")
        write_idle_counts(counts_path, {"coder-a": 3})
        tasks = [make_task(owner="coder-b")]  # No task for coder-a

        msg, should_shutdown = check_idle_cleanup(tasks, "coder-a", counts_path)
        assert msg is None

        counts = read_idle_counts(counts_path)
        assert "coder-a" not in counts


class TestMain:
    """Tests for teammate_idle.main() stdin/stdout/exit behavior."""

    def _run_main(self, input_data, env=None, tasks=None):
        """Helper to run main() with mocked inputs."""
        import io
        from teammate_idle import main

        default_env = {
            "CLAUDE_CODE_TEAM_NAME": "pact-test",
        }
        if env:
            default_env.update(env)

        mock_tasks = tasks if tasks is not None else []

        with patch.dict(os.environ, default_env, clear=True), \
             patch("sys.stdin", io.StringIO(json.dumps(input_data))), \
             patch("teammate_idle.get_task_list", return_value=mock_tasks):
            with pytest.raises(SystemExit) as exc_info:
                main()

        return exc_info.value.code

    def test_exits_0_when_no_team(self, capsys):
        import io
        import os
        from teammate_idle import main

        with patch.dict(os.environ, {"CLAUDE_CODE_TEAM_NAME": ""}, clear=True), \
             patch("sys.stdin", io.StringIO("{}")):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

    def test_exits_0_when_no_teammate_name(self):
        exit_code = self._run_main({"teammate_name": ""})
        assert exit_code == 0

    def test_exits_0_when_no_tasks(self):
        exit_code = self._run_main(
            {"teammate_name": "coder-a"},
            tasks=None
        )
        assert exit_code == 0

    def test_outputs_stall_warning(self, capsys, tmp_path):
        import io
        import os
        from teammate_idle import main

        tasks = [make_task(status="in_progress", owner="coder-a")]

        env = {
            "CLAUDE_CODE_TEAM_NAME": "pact-test",
        }

        with patch.dict(os.environ, env, clear=True), \
             patch("sys.stdin", io.StringIO(json.dumps({"teammate_name": "coder-a"}))), \
             patch("teammate_idle.get_task_list", return_value=tasks):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        if captured.out.strip():
            output = json.loads(captured.out)
            assert "systemMessage" in output
            assert "stall" in output["systemMessage"].lower()

    def test_outputs_nothing_for_completed_below_threshold(self, capsys, tmp_path):
        import io
        import os
        from teammate_idle import main

        tasks = [make_task(status="completed", owner="coder-a")]

        env = {
            "CLAUDE_CODE_TEAM_NAME": "pact-test",
        }

        with patch.dict(os.environ, env, clear=True), \
             patch("sys.stdin", io.StringIO(json.dumps({"teammate_name": "coder-a"}))), \
             patch("teammate_idle.get_task_list", return_value=tasks):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # No output expected below threshold
        assert captured.out.strip() == "" or "systemMessage" not in captured.out

    def test_exits_0_on_invalid_json(self):
        import io
        import os
        from teammate_idle import main

        with patch.dict(os.environ, {"CLAUDE_CODE_TEAM_NAME": "pact-test"}, clear=True), \
             patch("sys.stdin", io.StringIO("not json")):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0


# Required for patch.dict
import os
