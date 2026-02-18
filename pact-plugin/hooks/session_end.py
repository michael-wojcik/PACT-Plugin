#!/usr/bin/env python3
"""
Location: pact-plugin/hooks/session_end.py
Summary: SessionEnd hook that captures a last-session snapshot for cross-session
         continuity.
Used by: hooks.json SessionEnd hook

Actions:
1. Write last-session snapshot to ~/.claude/pact-sessions/{slug}/last-session.md

Cannot block session termination — fire-and-forget.

Input: JSON from stdin with session context
Output: None (SessionEnd hooks cannot inject context)
"""

import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add hooks directory to path for shared package imports
_hooks_dir = Path(__file__).parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from shared.task_utils import get_task_list


def get_project_slug() -> str:
    """Derive project slug from environment."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        return Path(project_dir).name
    return ""


def write_session_snapshot(
    tasks: list[dict] | None,
    project_slug: str,
    sessions_dir: str | None = None,
) -> None:
    """
    Write a structured last-session snapshot from task states.

    Reads completed and incomplete tasks to produce a markdown summary at
    ~/.claude/pact-sessions/{project_slug}/last-session.md. This file is
    read by session_init.py on the next session start to provide continuity.

    Args:
        tasks: List of task dicts from get_task_list(), or None
        project_slug: Project identifier for the session directory
        sessions_dir: Override for sessions base directory (for testing)
    """
    if not project_slug:
        return

    if sessions_dir is None:
        sessions_dir = str(Path.home() / ".claude" / "pact-sessions")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Last Session: {now}", ""]

    completed_lines = []
    incomplete_lines = []
    decision_lines = []
    unresolved_lines = []

    if tasks:
        for task in tasks:
            task_id = task.get("id", "?")
            subject = task.get("subject", "unknown")
            status = task.get("status", "unknown")
            metadata = task.get("metadata", {})

            if status == "completed":
                # Extract 1-line summary from handoff decisions if present
                handoff = metadata.get("handoff", {})
                decisions = handoff.get("decisions", [])
                if decisions and isinstance(decisions, list):
                    summary = decisions[0] if isinstance(decisions[0], str) else str(decisions[0])
                    # Truncate long summaries
                    if len(summary) > 80:
                        summary = summary[:77] + "..."
                    completed_lines.append(f"- #{task_id} {subject} -> {summary}")
                else:
                    completed_lines.append(f"- #{task_id} {subject}")

            elif status in ("in_progress", "pending"):
                incomplete_lines.append(f"- #{task_id} {subject} -- {status}")

            # Collect decisions from all completed tasks with handoff metadata
            if status == "completed":
                handoff = metadata.get("handoff", {})
                for decision in handoff.get("decisions", []):
                    if isinstance(decision, str) and decision not in decision_lines:
                        decision_lines.append(decision)

            # Collect unresolved blockers/algedonic signals
            if metadata.get("type") in ("blocker", "algedonic") and status != "completed":
                unresolved_lines.append(f"- #{task_id} {subject}")

    # Build sections
    lines.append("## Completed Tasks")
    if completed_lines:
        lines.extend(completed_lines)
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Incomplete Tasks")
    if incomplete_lines:
        lines.extend(incomplete_lines)
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Key Decisions")
    if decision_lines:
        for d in decision_lines[:10]:  # Cap at 10 decisions
            lines.append(f"- {d}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Unresolved")
    if unresolved_lines:
        lines.extend(unresolved_lines)
    else:
        lines.append("- (none)")
    lines.append("")

    # Write snapshot file
    snapshot_dir = Path(sessions_dir) / project_slug
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_file = snapshot_dir / "last-session.md"
    snapshot_file.write_text("\n".join(lines), encoding="utf-8")


def main():
    try:
        project_slug = get_project_slug()

        # Write last-session snapshot for cross-session continuity
        tasks = get_task_list()
        write_session_snapshot(
            tasks=tasks,
            project_slug=project_slug,
        )

        sys.exit(0)

    except Exception as e:
        print(f"Hook warning (session_end): {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
