"""
graph.py — defines the LangGraph StateGraph pipeline,
including nodes, sequential edges, conditional routing, and checkpointing.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from agent.nodes import (
    fetch_issue,
    clone_repo,
    explore_repo,
    plan_fix,
    human_review,
    apply_patches,
    validate,
    generate_diff,
    write_pr_summary,
)


def prepare_retry(state: AgentState) -> dict:
    """Helper node that increments the retry counter when validation fails."""
    current_retry = state.get("retry_count", 0)
    print(f"\n  ↺  Validation failed. Incrementing retry count to {current_retry + 1}...")
    return {"retry_count": current_retry + 1}


def route_after_review(state: AgentState) -> str:
    """Routes the agent based on human approval state."""
    if state.get("approved", False):
        return "apply_patches"
    return END


def route_after_validation(state: AgentState) -> str:
    """Routes to diff generation if validation passes, or to retry/end if it fails."""
    validation = state.get("validation", {})
    all_passed = True
    if not validation:
        all_passed = False
    else:
        for k, v in validation.items():
            if not v.get("passed"):
                all_passed = False
                break

    if all_passed:
        return "generate_diff"

    # Validation failed. Check if we have retries left.
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)
    if retry_count < max_retries:
        return "prepare_retry"

    print("  ✗  Validation failed and no retries remaining. Stopping.")
    return END


# Define graph builder
builder = StateGraph(AgentState)

# Add all nodes
builder.add_node("fetch_issue", fetch_issue)
builder.add_node("clone_repo", clone_repo)
builder.add_node("explore_repo", explore_repo)
builder.add_node("plan_fix", plan_fix)
builder.add_node("human_review", human_review)
builder.add_node("apply_patches", apply_patches)
builder.add_node("validate", validate)
builder.add_node("prepare_retry", prepare_retry)
builder.add_node("generate_diff", generate_diff)
builder.add_node("write_pr_summary", write_pr_summary)

# Define edges
builder.add_edge(START, "fetch_issue")
builder.add_edge("fetch_issue", "clone_repo")
builder.add_edge("clone_repo", "explore_repo")
builder.add_edge("explore_repo", "plan_fix")
builder.add_edge("plan_fix", "human_review")

builder.add_conditional_edges(
    "human_review",
    route_after_review,
    {
        "apply_patches": "apply_patches",
        END: END,
    },
)

builder.add_edge("apply_patches", "validate")

builder.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "generate_diff": "generate_diff",
        "prepare_retry": "prepare_retry",
        END: END,
    },
)

builder.add_edge("prepare_retry", "plan_fix")
builder.add_edge("generate_diff", "write_pr_summary")
builder.add_edge("write_pr_summary", END)

# Compile with a memory checkpointer to support interrupts and session persistence
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
