"""llh config — paths via env vars, portable across machines."""
import os
from pathlib import Path

HOME = Path.home()

# source session dirs (per machine)
CC_PROJECTS = Path(os.environ.get("LLH_CC_PROJECTS", str(HOME / ".claude" / "projects")))
DSH_SESSIONS = Path(os.environ.get("LLH_DSH_SESSIONS", str(HOME / ".dsh" / "sessions")))

# ssot store (a git repo, private). default home; override per machine:
#   setx LLH_SSOT_DIR E:\workstation\ai\session-ssot
SSOT_DIR = Path(os.environ.get("LLH_SSOT_DIR", str(HOME / "llm-history")))
IR_DIR = SSOT_DIR / "ir"
HANDOFF_DIR = SSOT_DIR / "handoff"

SSOT_REMOTE = os.environ.get("LLH_SSOT_REMOTE", "https://github.com/wesson88/session-ssot.git")

# llh go defaults
HOME_TARGET = os.environ.get("LLH_HOME_TARGET", "claude-code")
WORKSPACE = os.environ.get("LLH_WORKSPACE", os.getcwd())  # where CLAUDE.md lands on `go`
