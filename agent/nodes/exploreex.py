"""Node 3 — explore_repo: walks the repo and builds an LLM-ready summary."""
from __future__ import annotations

import os
import re

from agent.state import AgentState

# Regex to detect exported Go symbols
_EXPORTED_RE = re.compile(
    r"^(?:func|type|var|const)\s+([A-Z][A-Za-z0-9_]*)", re.MULTILINE
)

_SKIP_DIRS = {".git", "vendor", "testdata", "node_modules", ".github"}
_MAX_SNIPPET_FILES = 12
_MAX_SNIPPET_CHARS = 15_000


def explore_repo(state: AgentState) -> dict:
    """
    Walks the repository and builds:
    - A compact text summary of all .go files (path, package, exported symbols)
    - File snippets for the top-N most relevant files

    Returns updates to AgentState:
        repo_summary, file_snippets
    """
    repo_dir = state["repo_dir"]
    issue = state["issue"]

    print(f"\n[3/9] Exploring repository structure…")

    files = _walk_go_files(repo_dir)
    summary_lines = [
        f"Repository root: {repo_dir}",
        f"Total .go files: {len(files)}",
        "",
    ]
    for f in files:
        syms = f["symbols"][:12]  # cap to keep summary compact
        sym_str = ", ".join(syms) if syms else "(none)"
        summary_lines.append(
            f"  {f['rel_path']}  [pkg:{f['package']}  lines:{f['lines']}]"
        )
        summary_lines.append(f"    exports: {sym_str}")

    repo_summary = "\n".join(summary_lines)
    print(f"  ✓  indexed {len(files)} Go files")

    # Find relevant files by keyword matching
    keywords = _extract_keywords(
        issue.get("title", "") + " " + issue.get("body", "")
    )
    relevant = _find_relevant(files, keywords)[:_MAX_SNIPPET_FILES]

    file_snippets: dict[str, str] = {}
    for f in relevant:
        abs_path = os.path.join(repo_dir, f["rel_path"])
        try:
            content = open(abs_path, encoding="utf-8", errors="replace").read()
            if len(content) > _MAX_SNIPPET_CHARS:
                content = content[:_MAX_SNIPPET_CHARS] + "\n// ... (truncated)"
            file_snippets[f["rel_path"]] = content
        except OSError:
            pass

    print(f"  ✓  {len(file_snippets)} relevant file(s) loaded for LLM context")

    return {
        "repo_summary": repo_summary,
        "file_snippets": file_snippets,
        "error": None,
    }


# ── helpers ──────────────────────────────────────────────────────────────────

def _walk_go_files(repo_dir: str) -> list[dict]:
    """Returns metadata for every .go file, sorted by rel_path."""
    results = []
    for dirpath, dirnames, filenames in os.walk(repo_dir):
        # Prune skipped dirs in-place so os.walk won't descend into them
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            if not fname.endswith(".go"):
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, repo_dir).replace("\\", "/")
            try:
                content = open(abs_path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue

            pkg = _extract_package(content)
            symbols = _EXPORTED_RE.findall(content)
            results.append({
                "rel_path": rel_path,
                "package": pkg,
                "lines": content.count("\n") + 1,
                "symbols": symbols,
            })

    return sorted(results, key=lambda f: f["rel_path"])


def _extract_package(content: str) -> str:
    m = re.search(r"^package\s+(\w+)", content, re.MULTILINE)
    return m.group(1) if m else "?"


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text)
    seen: set[str] = set()
    out = []
    for t in tokens:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _find_relevant(files: list[dict], keywords: list[str]) -> list[dict]:
    scored = []
    for f in files:
        haystack = (
            f["rel_path"] + " " + f["package"] + " " + " ".join(f["symbols"])
        ).lower()
        score = sum(1 for kw in keywords if kw.lower() in haystack)
        if score > 0:
            scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored]
