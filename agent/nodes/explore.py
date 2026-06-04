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
_MAX_SNIPPET_FILES = 5
_MAX_SNIPPET_CHARS = 20_000   # FIX 1: was 8000, large files like command.go need more
_CONTEXT_WINDOW = 60          # lines above/below a keyword hit to extract


def explore_repo(state: AgentState) -> dict:
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
        syms = f["symbols"][:12]
        sym_str = ", ".join(syms) if syms else "(none)"
        summary_lines.append(
            f"  {f['rel_path']}  [pkg:{f['package']}  lines:{f['lines']}]"
        )
        summary_lines.append(f"    exports: {sym_str}")

    repo_summary = "\n".join(summary_lines)
    print(f"  ✓  indexed {len(files)} Go files")

    keywords = _extract_keywords(
        issue.get("title", "") + " " + issue.get("body", "")
    )
    relevant = _find_relevant(files, keywords)[:_MAX_SNIPPET_FILES]

    file_snippets: dict[str, str] = {}
    for f in relevant:
        abs_path = os.path.join(repo_dir, f["rel_path"])
        try:
            content = open(abs_path, encoding="utf-8", errors="replace").read()
            # FIX 2: For large files, extract relevant sections instead of
            # blindly truncating from the top (which misses the actual fix area)
            if len(content) > _MAX_SNIPPET_CHARS:
                content = _extract_relevant_sections(content, keywords)
            else:
                # Add line numbers to all lines for consistency
                content = "\n".join(f"{i+1:4d}: {line}" for i, line in enumerate(content.splitlines()))
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

def _extract_relevant_sections(content: str, keywords: list[str]) -> str:
    """
    FIX 2: Instead of truncating large files from the top, find lines that
    contain keywords and extract a window of context around each hit.
    This ensures the actual fix area is always included in the LLM context.
    """
    lines = content.splitlines()
    total = len(lines)
    included: set[int] = set()

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw.lower() in line_lower for kw in keywords):
            lo = max(0, i - _CONTEXT_WINDOW)
            hi = min(total, i + _CONTEXT_WINDOW + 1)
            included.update(range(lo, hi))

    if not included:
        # No keyword hits — fall back to first _MAX_SNIPPET_CHARS
        return content[:_MAX_SNIPPET_CHARS] + "\n// ... (truncated — no keyword hits)"

    # Emit sections with gap markers so Gemini knows lines were skipped
    result_lines = []
    prev = -1
    for i in sorted(included):
        if prev != -1 and i > prev + 1:
            result_lines.append(f"// ... (lines {prev+2}–{i} omitted)")
        result_lines.append(f"{i+1:4d}: {lines[i]}")
        prev = i

    extracted = "\n".join(result_lines)

    # Safety cap — if still too large, truncate at char limit
    if len(extracted) > _MAX_SNIPPET_CHARS:
        extracted = extracted[:_MAX_SNIPPET_CHARS] + "\n// ... (truncated)"

    return extracted


def _walk_go_files(repo_dir: str) -> list[dict]:
    results = []
    for dirpath, dirnames, filenames in os.walk(repo_dir):
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
                # FIX 3: store raw content so _find_relevant can search inside file body too
                "content": content,
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
    """
    FIX 3: Score files by searching inside file BODY too, not just
    path/package/symbols. This catches files where the fix area
    is in the body but not reflected in exported symbol names.
    """
    scored = []
    for f in files:
        # Search in path + symbols (fast, existing logic)
        haystack_meta = (
            f["rel_path"] + " " + f["package"] + " " + " ".join(f["symbols"])
        ).lower()
        score_meta = sum(1 for kw in keywords if kw.lower() in haystack_meta)

        # Also search inside file content body (catches inline comments, var names)
        content_lower = f.get("content", "").lower()
        score_body = sum(
            min(content_lower.count(kw.lower()), 3)  # cap at 3 per keyword
            for kw in keywords
        )

        score = score_meta * 3 + score_body  # weight metadata hits higher
        if score > 0:
            scored.append((score, f))

    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored]