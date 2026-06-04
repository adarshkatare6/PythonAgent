"""Node 6 — apply_patches: applies the LLM-generated patches to source files.

Strategy:
  1. Primary  — exact string search-replace (str.replace)
  2. Fallback — full file rewrite when search string not found but
                replace content starts with "package " (valid Go file)

Every file is backed up as <file>.bak before modification.
Backups are restored automatically on validation failure (see graph.py).
"""
from __future__ import annotations

import os
import shutil

from agent.state import AgentState


def apply_patches(state: AgentState) -> dict:
    """
    Applies all patches from state["plan"]["patches"] to state["repo_dir"].

    Returns updates to AgentState:
        patch_results
    """
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
    """Restores .bak files for all patched files. Called on validation failure."""
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

    # ── Search-replace mode ───────────────────────────────────────────────
    try:
        original = open(abs_path, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        return {
            "file": file_rel,
            "strategy": "error",
            "error": f"Cannot read file: {exc}",
        }

    # Normalise line endings for reliable matching
    norm = original.replace("\r\n", "\n")
    search_norm = search.replace("\r\n", "\n")
    replace_norm = replace.replace("\r\n", "\n")

    if search_norm in norm:
        new_content = norm.replace(search_norm, replace_norm, 1)
        try:
            _backup_and_write(abs_path, new_content)
            return {"file": file_rel, "strategy": "search-replace", "error": None}
        except OSError as exc:
            return {"file": file_rel, "strategy": "error", "error": str(exc)}

    # ── Fallback: treat replace as full file if it looks like Go source ───
    if replace_norm.lstrip().startswith("package "):
        try:
            _backup_and_write(abs_path, replace_norm)
            return {
                "file": file_rel,
                "strategy": "full-rewrite (fallback)",
                "error": None,
            }
        except OSError as exc:
            return {"file": file_rel, "strategy": "error", "error": str(exc)}

    return {
        "file": file_rel,
        "strategy": "error",
        "error": (
            f"Search string not found in {file_rel!r} and replace is not a full file."
        ),
    }


def _backup_and_write(abs_path: str, content: str) -> None:
    if os.path.exists(abs_path):
        shutil.copy2(abs_path, abs_path + ".bak")
    with open(abs_path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _abs(repo_dir: str, rel_path: str) -> str:
    return os.path.join(repo_dir, rel_path.replace("/", os.sep))
