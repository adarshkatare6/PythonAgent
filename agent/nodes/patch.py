"""Node 6 — apply_patches: applies the LLM-generated patches to source files."""
from __future__ import annotations

import os
import shutil

from agent.state import AgentState


def apply_patches(state: AgentState) -> dict:
    repo_dir = state["repo_dir"]
    patches = state.get("plan", {}).get("patches", [])

    print(f"\n[6/9] Applying {len(patches)} patch(es)…")

    results = []
    all_ok = True

    for patch in patches:
        result = _apply_one(repo_dir, patch)
        results.append(result)

        icon = "✓" if result["error"] is None else "✗"
        print(f"  {icon}  {result['file']}  [{result['strategy']}]")
        if result["error"]:
            print(f"       error: {result['error']}")
            all_ok = False

    if not all_ok:
        return {
            "patch_results": results,
            "error": "One or more patches failed — see patch_results for details",
        }

    return {"patch_results": results, "error": None}


def restore_backups(repo_dir: str, patches: list[dict]) -> None:
    for patch in patches:
        abs_path = _abs(repo_dir, patch["file"])
        bak = abs_path + ".bak"
        if os.path.exists(bak):
            shutil.copy2(bak, abs_path)
            os.remove(bak)
            print(f"  ↩  restored {patch['file']}")


# ── internals ────────────────────────────────────────────────────────────────

def _apply_one(repo_dir: str, patch: dict) -> dict:
    file_rel = patch.get("file", "")
    full_content = patch.get("full_content", "")
    search = patch.get("search", "")
    replace = patch.get("replace", "")

    abs_path = _abs(repo_dir, file_rel)

    # ── Full-content rewrite mode ─────────────────────────────────────────
    if full_content.strip():
        try:
            _backup_and_write(abs_path, full_content)
            return {"file": file_rel, "strategy": "full-rewrite", "error": None}
        except OSError as exc:
            return {"file": file_rel, "strategy": "error", "error": str(exc)}

    # ── Read file ─────────────────────────────────────────────────────────
    try:
        original = open(abs_path, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        return {"file": file_rel, "strategy": "error", "error": f"Cannot read file: {exc}"}

    # Normalise line endings
    norm = original.replace("\r\n", "\n")
    search_norm = search.replace("\r\n", "\n")
    replace_norm = replace.replace("\r\n", "\n")

    # ── Attempt 1: Exact match ────────────────────────────────────────────
    if search_norm and search_norm in norm:
        new_content = norm.replace(search_norm, replace_norm, 1)
        try:
            _backup_and_write(abs_path, new_content)
            return {"file": file_rel, "strategy": "search-replace", "error": None}
        except OSError as exc:
            return {"file": file_rel, "strategy": "error", "error": str(exc)}

    # FIX 4: Attempt 2: Strip leading line numbers (e.g. "  42: code" → "code")
    # Gemini sometimes copies line-numbered snippets verbatim into search field
    search_stripped = _strip_line_numbers(search_norm)
    if search_stripped and search_stripped != search_norm and search_stripped in norm:
        replace_stripped = _strip_line_numbers(replace_norm)
        new_content = norm.replace(search_stripped, replace_stripped, 1)
        try:
            _backup_and_write(abs_path, new_content)
            return {"file": file_rel, "strategy": "search-replace (stripped line numbers)", "error": None}
        except OSError as exc:
            return {"file": file_rel, "strategy": "error", "error": str(exc)}

    # FIX 5: Attempt 3: Whitespace-normalised fuzzy match
    # Handles cases where Gemini uses spaces but file uses tabs (or vice versa)
    fuzzy_result = _fuzzy_replace(norm, search_norm, replace_norm)
    if fuzzy_result is not None:
        try:
            _backup_and_write(abs_path, fuzzy_result)
            return {"file": file_rel, "strategy": "search-replace (fuzzy whitespace)", "error": None}
        except OSError as exc:
            return {"file": file_rel, "strategy": "error", "error": str(exc)}

    # ── Fallback: treat replace as full file if it looks like Go source ───
    if replace_norm.lstrip().startswith("package "):
        try:
            _backup_and_write(abs_path, replace_norm)
            return {"file": file_rel, "strategy": "full-rewrite (fallback)", "error": None}
        except OSError as exc:
            return {"file": file_rel, "strategy": "error", "error": str(exc)}

    return {
        "file": file_rel,
        "strategy": "error",
        "error": (
            f"Search string not found in {file_rel!r}.\n"
            f"  Searched for (first 120 chars): {search_norm[:120]!r}\n"
            f"  Tip: Switch to full_content mode in the retry plan."
        ),
    }


def _strip_line_numbers(text: str) -> str:
    """
    FIX 4: Remove leading line number prefixes like '  42: ' or '1112:  ' from each line.
    Gemini sometimes copies snippets with line numbers directly into the search field.
    """
    lines = text.splitlines(keepends=True)
    stripped = []
    for line in lines:
        # Match optional spaces, digits, colon, optional space
        m = __import__("re").match(r"^\s*\d+:\s?", line)
        if m:
            stripped.append(line[m.end():])
        else:
            stripped.append(line)
    return "".join(stripped)


def _fuzzy_replace(original: str, search: str, replace: str) -> str | None:
    """
    FIX 5: Try matching after normalising all whitespace.
    Handles tab/space mismatches between Gemini output and actual file.
    Uses regex to ensure only the matched block is replaced, preserving partial lines.
    """
    import re

    # Escape the search string so special regex characters are treated literally.
    # Split the search string by whitespace sequences.
    tokens = re.split(r'(\s+)', search)
    pattern_parts = []
    for token in tokens:
        if not token:
            continue
        if token.isspace():
            # Match any sequence of whitespace
            pattern_parts.append(r'\s+')
        else:
            pattern_parts.append(re.escape(token))
            
    pattern_str = "".join(pattern_parts)
    
    try:
        match = re.search(pattern_str, original)
        if match:
            start, end = match.span()
            return original[:start] + replace + original[end:]
    except Exception:
        pass
    return None


def _backup_and_write(abs_path: str, content: str) -> None:
    if os.path.exists(abs_path):
        shutil.copy2(abs_path, abs_path + ".bak")
    with open(abs_path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _abs(repo_dir: str, rel_path: str) -> str:
    return os.path.join(repo_dir, rel_path.replace("/", os.sep))