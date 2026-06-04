"""Node 8 — generate_diff: generates a unified git diff of the changes."""
from __future__ import annotations

import git

from agent.state import AgentState


def generate_diff(state: AgentState) -> dict:
    """
    Generates a unified diff using GitPython.

    Returns updates to AgentState:
        diff
    """
    repo_dir = state["repo_dir"]
    print(f"\n[8/9] Generating unified diff…")

    try:
        repo = git.Repo(repo_dir)
        # Try diff against HEAD first
        diff = repo.git.diff("HEAD")
        if not diff.strip():
            # Fallback to general diff
            diff = repo.git.diff()
        
        print(f"  ✓  diff generated ({len(diff.splitlines())} lines)")
        return {"diff": diff, "error": None}
    except Exception as e:
        print(f"  ✗  failed to generate diff: {e}")
        return {"diff": "", "error": f"Failed to generate diff: {e}"}
