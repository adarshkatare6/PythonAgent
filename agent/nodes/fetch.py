"""Node 1 — fetch_issue: reads a GitHub issue via the REST API."""
from __future__ import annotations

import os
import re
import requests

from agent.state import AgentState


_ISSUE_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)"
)


def fetch_issue(state: AgentState) -> dict:
    """
    Fetches the GitHub issue from the REST API.

    Returns updates to AgentState:
        issue, owner, repo, issue_number
    """
    url = state["issue_url"]
    m = _ISSUE_URL_RE.match(url.strip())
    if not m:
        raise ValueError(f"Not a valid GitHub issue URL: {url!r}")

    owner = m.group("owner")
    repo = m.group("repo")
    number = int(m.group("number"))

    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"\n[1/9] Fetching issue: {api_url}")
    resp = requests.get(api_url, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(
            f"GitHub API returned {resp.status_code}: {resp.json().get('message', '')}"
        )

    issue = resp.json()
    labels = [lb["name"] for lb in issue.get("labels", [])]
    print(f"  ✓  #{number}: {issue['title']}")
    print(f"     state={issue['state']}  labels={labels}")

    return {
        "issue": issue,
        "owner": owner,
        "repo": repo,
        "issue_number": number,
        "error": None,
    }
