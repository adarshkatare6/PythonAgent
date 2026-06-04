"""Node 5 — human_review: shows the fix plan and waits for user approval.

Uses LangGraph's interrupt() for a true pause-and-resume pattern.
When auto_approve=True the node approves automatically.
"""
from __future__ import annotations

from langgraph.types import interrupt

from agent.state import AgentState


def human_review(state: AgentState) -> dict:
    """
    Presents the fix plan to the user and waits for approval.

    With LangGraph's interrupt():
    - Graph execution pauses here
    - The caller (cli.py) can inspect the state, then resume
      by invoking the graph again with {"approved": True/False}

    When auto_approve=True, skips the interrupt entirely.

    Returns updates to AgentState:
        approved
    """
    plan = state.get("plan", {})
    auto_approve = state.get("auto_approve", False)

    _print_plan(plan)

    if auto_approve:
        print("  [auto-approve] Proceeding without user confirmation.")
        return {"approved": True}

    # LangGraph interrupt: execution pauses here.
    # The value passed to interrupt() is surfaced to the caller as the
    # "interrupt value" — we send the plan so the caller can display it.
    decision = interrupt({
        "message": "Do you approve this fix plan? (y/n)",
        "plan": plan,
    })

    approved = str(decision).strip().lower() in ("y", "yes", "1", "true")
    if approved:
        print("  ✓  Plan approved — proceeding with patches.")
    else:
        print("  ✗  Plan rejected — stopping.")

    return {"approved": approved}


def _print_plan(plan: dict) -> None:
    print("\n" + "═" * 50)
    print("  FIX PLAN")
    print("═" * 50)
    print(f"  Summary : {plan.get('summary', '(none)')}")
    print()
    print("  Files to modify:")
    for f in plan.get("files_to_modify", []):
        print(f"    • {f}")
    print()
    print("  Steps:")
    for i, s in enumerate(plan.get("steps", []), 1):
        print(f"    {i}. {s}")
    print()
    patches = plan.get("patches", [])
    print(f"  Patches: {len(patches)} patch(es)")
    for p in patches:
        if p.get("full_content"):
            print(f"    • {p['file']}  (full file rewrite)")
        else:
            lines = p.get("replace", "").count("\n") + 1
            print(f"    • {p['file']}  (search-replace, ~{lines} lines)")
    print("═" * 50)
