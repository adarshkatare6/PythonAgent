"""Node 2 — clone_repo: clones or pulls the repository using GitPython."""
from __future__ import annotations

import os

import git

from agent.state import AgentState


def clone_repo(state: AgentState) -> dict:
    """
    Ensures the repository is available locally.

    - If already cloned: runs git pull --ff-only
    - Otherwise: git clone

    Returns updates to AgentState:
        repo_dir, branch_name
    """
    owner = state["owner"]
    repo = state["repo"]
    number = state["issue_number"]
    workspace = state.get("workspace_dir", "./workspace")

    repo_dir = os.path.abspath(os.path.join(workspace, owner, repo))
    os.makedirs(os.path.dirname(repo_dir), exist_ok=True)

    clone_url = f"https://github.com/{owner}/{repo}.git"
    branch_name = f"agent/fix-issue-{number}"

    print(f"\n[2/9] Cloning repository: {clone_url}")

    if os.path.exists(os.path.join(repo_dir, ".git")):
        print(f"  repo already cloned at {repo_dir} — pulling latest…")
        git_repo = git.Repo(repo_dir)
        # Ensure we're on main/master before branching
        _checkout_default_branch(git_repo)
        git_repo.remotes.origin.pull()
    else:
        print(f"  cloning into {repo_dir}…")
        git_repo = git.Repo.clone_from(clone_url, repo_dir)

    # Create the fix branch (delete if exists for idempotent re-runs)
    _checkout_default_branch(git_repo)
    try:
        git_repo.git.branch("-D", branch_name)
    except git.GitCommandError:
        pass  # branch didn't exist — that's fine
    git_repo.git.checkout("-b", branch_name)

    print(f"  ✓  repo ready at {repo_dir}")
    print(f"  ✓  branch {branch_name!r} created")

    return {
        "repo_dir": repo_dir,
        "branch_name": branch_name,
        "error": None,
    }


def _checkout_default_branch(git_repo: git.Repo) -> None:
    """Switches to main or master — whichever exists."""
    for branch in ("main", "master"):
        try:
            git_repo.git.checkout(branch)
            return
        except git.GitCommandError:
            continue
