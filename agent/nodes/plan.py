"""Node 4 — plan_fix: sends issue + repo context to Gemini and parses a structured fix plan."""
from __future__ import annotations

import json
import os
import re

import google.generativeai as genai

from agent.prompts import (
    FIX_PLAN_PROMPT,
    RETRY_PLAN_PROMPT,
    SNIPPETS_SECTION,
    FILE_SNIPPET_BLOCK,
)
from agent.state import AgentState


def plan_fix(state: AgentState) -> dict:
    """
    Calls Gemini to produce a structured JSON fix plan.

    On first call uses FIX_PLAN_PROMPT.
    On retry calls (retry_count > 0) uses RETRY_PLAN_PROMPT which
    includes the previous validation error output so Gemini can self-correct.

    Returns updates to AgentState:
        plan
    """
    _configure_gemini(state)

    retry_count = state.get("retry_count", 0)
    is_retry = retry_count > 0

    print(
        f"\n[4/9] {'Re-generating' if is_retry else 'Generating'} fix plan "
        f"(Gemini / attempt {retry_count + 1})…"
    )

    prompt = _build_prompt(state, is_retry=is_retry)

    model = genai.GenerativeModel(state.get("gemini_model", "gemini-2.5-flash"))
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=8192,
            temperature=0.2,
        )
    )
    raw = response.text

    try:
        plan = _parse_plan(raw)
    except Exception as e:
        debug_path = os.path.join(state.get("workspace_dir", "."), "debug_raw_response.json")
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(raw)
            print(f"  [DEBUG] Saved raw LLM response to {debug_path}")
        except Exception:
            pass
        raise e

    print(f"  ✓  plan generated: {plan.get('summary', '(no summary)')}")
    print(f"     files to modify: {plan.get('files_to_modify', [])}")
    print(f"     patches: {len(plan.get('patches', []))}")

    return {"plan": plan, "error": None}


# ── helpers ──────────────────────────────────────────────────────────────────

def _configure_gemini(state: AgentState) -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    genai.configure(api_key=api_key)


def _build_snippets_section(file_snippets: dict[str, str]) -> str:
    if not file_snippets:
        return ""
    blocks = "\n\n".join(
        FILE_SNIPPET_BLOCK.format(path=p, content=c)
        for p, c in file_snippets.items()
    )
    return SNIPPETS_SECTION.format(snippets=blocks)


def _build_prompt(state: AgentState, is_retry: bool) -> str:
    issue = state["issue"]
    labels = [lb["name"] for lb in issue.get("labels", [])]
    snippets_section = _build_snippets_section(state.get("file_snippets", {}))

    if is_retry:
        validation = state.get("validation", {})
        errors = _format_validation_errors(validation)
        return RETRY_PLAN_PROMPT.format(
            validation_errors=errors,
            owner=state["owner"],
            repo=state["repo"],
            number=state["issue_number"],
            title=issue["title"],
            body=issue.get("body", ""),
            repo_summary=state.get("repo_summary", ""),
            snippets_section=snippets_section,
        )

    return FIX_PLAN_PROMPT.format(
        owner=state["owner"],
        repo=state["repo"],
        number=state["issue_number"],
        title=issue["title"],
        labels=", ".join(labels),
        body=issue.get("body", ""),
        repo_summary=state.get("repo_summary", ""),
        snippets_section=snippets_section,
    )


def _format_validation_errors(validation: dict) -> str:
    lines = []
    for step, result in validation.items():
        if not result.get("passed"):
            lines.append(f"FAILED: {step}")
            if result.get("output"):
                lines.append(result["output"].strip())
    return "\n".join(lines) if lines else "Unknown validation error"


def _parse_plan(raw: str) -> dict:
    """Robustly extract a JSON object from the LLM response."""
    cleaned = raw.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        # Remove opening fence line
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        # Remove closing fence
        cleaned = re.sub(r"\n?```$", "", cleaned.strip())
        cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass

    # Fallback: find first { ... } block
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1], strict=False)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON plan from LLM response:\n{raw[:500]}")
