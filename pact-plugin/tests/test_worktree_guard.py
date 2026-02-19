# pact-plugin/tests/test_worktree_guard.py
"""
Tests for worktree_guard.py — PreToolUse hook matching Edit|Write that
blocks edits to application code outside the active worktree.

Tests cover:
1. Edit inside worktree → allow
2. Edit outside worktree to app code → block
3. Edit outside worktree to .claude/ → allow (AI tooling)
4. Edit outside worktree to docs/ → allow (documentation)
5. No PACT_WORKTREE_PATH set → allow (inactive, no-op)
6. CLAUDE.md always allowed
7. main() entry point: stdin JSON parsing, exit codes, output format
"""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


class TestWorktreeGuard:
    """Tests for worktree_guard.check_worktree_boundary()."""

    def test_allows_edit_inside_worktree(self):
        from worktree_guard import check_worktree_boundary

        result = check_worktree_boundary(
            file_path="/tmp/worktrees/feat-auth/src/auth.ts",
            worktree_path="/tmp/worktrees/feat-auth"
        )
        assert result is None

    def test_blocks_app_code_outside_worktree(self):
        from worktree_guard import check_worktree_boundary

        result = check_worktree_boundary(
            file_path="/Users/mj/project/src/auth.ts",
            worktree_path="/tmp/worktrees/feat-auth"
        )
        assert result is not None
        assert "outside worktree" in result.lower()

    def test_allows_claude_dir_outside_worktree(self):
        from worktree_guard import check_worktree_boundary

        result = check_worktree_boundary(
            file_path="/Users/mj/.claude/CLAUDE.md",
            worktree_path="/tmp/worktrees/feat-auth"
        )
        assert result is None

    def test_allows_docs_outside_worktree(self):
        from worktree_guard import check_worktree_boundary

        result = check_worktree_boundary(
            file_path="/Users/mj/project/docs/architecture/design.md",
            worktree_path="/tmp/worktrees/feat-auth"
        )
        assert result is None

    def test_noop_when_no_worktree_path(self):
        from worktree_guard import check_worktree_boundary

        result = check_worktree_boundary(
            file_path="/Users/mj/project/src/auth.ts",
            worktree_path=""
        )
        assert result is None

    def test_allows_claude_md_anywhere(self):
        from worktree_guard import check_worktree_boundary

        result = check_worktree_boundary(
            file_path="/Users/mj/project/CLAUDE.md",
            worktree_path="/tmp/worktrees/feat-auth"
        )
        assert result is None


class TestMainEntryPoint:
    """Tests for worktree_guard.main() stdin/stdout/exit behavior."""

    def test_main_exits_0_when_no_worktree_path(self):
        from worktree_guard import main

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

    def test_main_exits_0_when_edit_inside_worktree(self):
        from worktree_guard import main

        input_data = json.dumps({
            "tool_input": {"file_path": "/tmp/worktrees/feat-auth/src/auth.ts"}
        })

        with patch.dict("os.environ", {"PACT_WORKTREE_PATH": "/tmp/worktrees/feat-auth"}), \
             patch("worktree_guard.check_worktree_boundary", return_value=None), \
             patch("sys.stdin", io.StringIO(input_data)):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

    def test_main_exits_2_when_edit_outside_worktree(self, capsys):
        from worktree_guard import main

        input_data = json.dumps({
            "tool_input": {"file_path": "/Users/mj/project/src/auth.ts"}
        })

        error_msg = "File is outside worktree boundary"
        with patch.dict("os.environ", {"PACT_WORKTREE_PATH": "/tmp/worktrees/feat-auth"}), \
             patch("worktree_guard.check_worktree_boundary", return_value=error_msg), \
             patch("sys.stdin", io.StringIO(input_data)):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_main_exits_0_on_invalid_json(self):
        from worktree_guard import main

        with patch.dict("os.environ", {"PACT_WORKTREE_PATH": "/tmp/worktrees/feat-auth"}), \
             patch("sys.stdin", io.StringIO("not json")):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

    def test_main_exits_0_when_no_file_path(self):
        from worktree_guard import main

        input_data = json.dumps({"tool_input": {}})

        with patch.dict("os.environ", {"PACT_WORKTREE_PATH": "/tmp/worktrees/feat-auth"}), \
             patch("sys.stdin", io.StringIO(input_data)):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
