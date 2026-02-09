#!/usr/bin/env python3
"""
Location: pact-plugin/hooks/teammate_idle.py
Summary: TeammateIdle hook for PACT v3.0 Agent Teams.
Used by: hooks.json TeammateIdle event registration

Fires when a teammate goes idle. Currently a safe no-op that prints
an informational reminder for PACT specialists, but always allows
idle (exit 0). Does NOT block agents from going idle.

Input (env vars): TEAMMATE_NAME, TEAM_NAME, SESSION_ID, CWD, TRANSCRIPT_PATH

Note: This hook needs empirical validation. The TeammateIdle event
behavior (env vars available, exit code semantics) is based on
platform documentation but has not been tested in production.
TODO: Once TaskGet access from hooks is confirmed empirically,
this hook could validate that a handoff exists in Task metadata
before allowing idle (exit 2 to keep working).
"""
import os
import sys


def main():
    teammate_name = os.environ.get("TEAMMATE_NAME", "")
    team_name = os.environ.get("TEAM_NAME", "")

    if not teammate_name or not team_name:
        # Not in an Agent Teams context — allow idle
        sys.exit(0)

    # Only act on PACT specialists (name starts with "pact-")
    if not teammate_name.startswith("pact-"):
        sys.exit(0)

    # Informational reminder only — does not block idle.
    # Exit 0 allows idle; exit 2 would keep the agent working.
    # Using exit 0 until empirical validation confirms that
    # TaskGet is accessible from hooks, at which point this
    # hook can validate handoff presence before allowing idle.
    print("Reminder: Ensure you have stored your handoff in Task "
          "metadata via TaskUpdate and sent a completion signal "
          "via SendMessage before going idle.")
    sys.exit(0)


if __name__ == "__main__":
    main()
