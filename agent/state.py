"""
AgentState — the single shared state TypedDict that flows through
every node in the LangGraph pipeline.

Each node receives the full state and returns only the keys it changes.
LangGraph merges the returned dict back into the state automatically.
"""
from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # ── Input ────────────────────────────────────────────────────────────────
    issue_url: str          
    workspace_dir: str      # root dir where repos are cloned
    gemini_model: str       # e.g. "gemini-2.5-flash"
    auto_approve: bool      # skip human confirmation node
    max_retries: int        # max validation retry loops (default 2)

    # ── Fetched issue data ───────────────────────────────────────────────────
    issue: dict[str, Any]   # raw GitHub issue JSON (title, body, labels, …)
    owner: str              # e.g. "spf13"
    repo: str               # e.g. "cobra"
    issue_number: int       # e.g. 1234

    # ── Cloned repo ──────────────────────────────────────────────────────────
    repo_dir: str           # absolute path to local repo root
    branch_name: str        # e.g. "agent/fix-issue-1234"

    # ── Repo exploration ─────────────────────────────────────────────────────
    repo_summary: str       # compact text listing of Go files + symbols
    file_snippets: dict[str, str]   # {rel_path: file_content} for top-5 files

    # ── Fix plan (from Gemini) ───────────────────────────────────────────────
    plan: dict[str, Any]    # {summary, files_to_modify, steps, patches}
    approved: bool          # set by human_review node

    # ── Patch results ────────────────────────────────────────────────────────
    patch_results: list[dict[str, Any]]  # [{file, strategy, error}]

    # ── Validation ───────────────────────────────────────────────────────────
    validation: dict[str, Any]   # {step: {passed, output}}
    retry_count: int             # how many re-plan attempts so far

    # ── Output ───────────────────────────────────────────────────────────────
    diff: str               # unified diff string from git diff HEAD
    pr: dict[str, str]      # {title, body}
    pr_summary_path: str    # absolute path to written pr_summary.md

    # ── Error handling ───────────────────────────────────────────────────────
    error: Optional[str]    # last error message (None = no error)
