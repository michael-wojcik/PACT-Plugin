#!/usr/bin/env python3
"""
Location: pact-plugin/hooks/session_end.py
Summary: SessionEnd hook that logs session metadata and captures a last-session
         snapshot for cross-session continuity.
Used by: hooks.json SessionEnd hook

Actions:
1. Log session metadata to ~/.claude/pact-session-log.json (append-only)
2. (Phase 3, Task 12) Write last-session snapshot for session restore

Cannot block session termination — fire-and-forget.

Input: JSON from stdin with session context
Output: None (SessionEnd hooks cannot inject context)
"""

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path


def log_session_metadata(
    project_slug: str,
    team_name: str,
    log_path: str | None = None,
) -> None:
    """
    Append session metadata to the session log file.

    Args:
        project_slug: Project identifier
        team_name: PACT team name for this session
        log_path: Override for log file path (for testing)
    """
    if log_path is None:
        log_path = str(Path.home() / ".claude" / "pact-session-log.json")

    log_file = Path(log_path)

    # Read existing entries
    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            entries = []

    # Append new entry
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_slug": project_slug,
        "team_name": team_name,
    }
    entries.append(entry)

    # Write back
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def get_project_slug() -> str:
    """Derive project slug from environment."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        return Path(project_dir).name
    return ""


def main():
    try:
        team_name = os.environ.get("CLAUDE_CODE_TEAM_NAME", "")
        project_slug = get_project_slug()

        log_session_metadata(
            project_slug=project_slug,
            team_name=team_name,
        )

        sys.exit(0)

    except Exception as e:
        print(f"Hook warning (session_end): {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
