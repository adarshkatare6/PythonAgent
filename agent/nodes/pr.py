"""Node 9 — write_pr_summary: generates the pull request description using Gemini."""
from __future__ import annotations

import os

import google.generativeai as genai

from agent.prompts import PR_PROMPT
from agent.state import AgentState
from agent.nodes.plan import _configure_gemini


def write_pr_summary(state: AgentState) -> dict:
    """
    Asks Gemini to write a Pull Request description based on the changes.
    Saves the description and diff to <repo_dir>/pr_summary.md.

    Returns updates to AgentState:
        pr, pr_summary_path
    """
    _configure_gemini(state)

    print("\n[9/9] Generating Pull Request summary using Gemini…")

    issue = state["issue"]
    prompt = PR_PROMPT.format(
        owner=state["owner"],
        repo=state["repo"],
        number=state["issue_number"],
        title=issue["title"],
        body=issue.get("body", ""),
        plan_summary=state.get("plan", {}).get("summary", ""),
        diff=state.get("diff", ""),
    )

    model = genai.GenerativeModel(state.get("gemini_model", "gemini-2.5-flash"))
    response = model.generate_content(prompt)
    raw = response.text

    # Parse title and body
    lines = raw.strip().split("\n")
    separator_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == "---":
            separator_idx = i
            break

    if separator_idx != -1:
        title = "\n".join(lines[:separator_idx]).strip()
        body = "\n".join(lines[separator_idx + 1:]).strip()
    else:
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

    # Clean up markdown code block markers around title if any
    title = title.replace("`", "").strip()

    pr_data = {"title": title, "body": body}

    # Write pr_summary.md into repo root
    repo_dir = state["repo_dir"]
    pr_summary_path = os.path.join(repo_dir, "pr_summary.md")
    
    summary_content = f"# {title}\n\n{body}\n\n## Unified Diff\n\n```diff\n{state.get('diff', '')}\n```\n"
    
    try:
        with open(pr_summary_path, "w", encoding="utf-8") as f:
            f.write(summary_content)
        print(f"  ✓  PR summary written to {pr_summary_path}")
    except OSError as e:
        print(f"  ✗  Failed to write PR summary: {e}")
        return {"pr": pr_data, "error": f"Failed to write PR summary file: {e}"}

    return {
        "pr": pr_data,
        "pr_summary_path": pr_summary_path,
        "error": None,
    }
