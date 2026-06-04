"""cli.py — command line interface for running the OpenSourceAgent."""
from __future__ import annotations

import argparse
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Force stdout/stderr to support UTF-8 on Windows command lines to avoid UnicodeEncodeErrors
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from langgraph.types import Command
from agent.graph import graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenSourceAgent: An agentic framework for fixing GitHub issues using Python + LangGraph + Gemini."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the agent on a GitHub issue URL.")
    run_parser.add_argument("issue_url", type=str, help="GitHub issue URL (e.g. https://github.com/owner/repo/issues/123)")
    run_parser.add_argument(
        "--workspace",
        type=str,
        default="./workspace",
        help="Root directory where repositories will be cloned.",
    )
    run_parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model to use (default: gemini-2.5-flash).",
    )
    run_parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip human review node and approve the fix plan automatically.",
    )
    run_parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum number of planning/validation retry loops (default: 2).",
    )

    args = parser.parse_args()

    # Validate environment
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please set it in your environment or in a .env file.", file=sys.stderr)
        sys.exit(1)

    if args.command == "run":
        initial_state = {
            "issue_url": args.issue_url,
            "workspace_dir": os.path.abspath(args.workspace),
            "gemini_model": args.model,
            "auto_approve": args.auto_approve,
            "max_retries": args.max_retries,
            "retry_count": 0,
        }

        # Unique thread ID for state checkpointing
        config = {"configurable": {"thread_id": "opensourceagent_run"}}

        print("=" * 60)
        print("  Starting OpenSourceAgent Python + LangGraph Rewrite")
        print("=" * 60)
        print(f"  Issue URL     : {args.issue_url}")
        print(f"  Workspace     : {initial_state['workspace_dir']}")
        print(f"  Gemini Model  : {args.model}")
        print(f"  Auto Approve  : {args.auto_approve}")
        print(f"  Max Retries   : {args.max_retries}")
        print("=" * 60)

        # Run the graph
        try:
            state = graph.invoke(initial_state, config)
        except Exception as e:
            print(f"\nError during agent execution: {e}", file=sys.stderr)
            sys.exit(1)

        # Human review interrupt loop
        while True:
            snapshot = graph.get_state(config)
            if not snapshot.next:
                # Execution finished
                break

            # If execution is paused at an interrupt, snapshot.next will not be empty.
            # Get the interrupt message if available.
            prompt_msg = "\nDo you approve this fix plan? (y/n): "
            if snapshot.tasks and snapshot.tasks[0].interrupts:
                interrupt_val = snapshot.tasks[0].interrupts[0].value
                if isinstance(interrupt_val, dict) and "message" in interrupt_val:
                    prompt_msg = f"\n{interrupt_val['message']} "

            try:
                user_choice = input(prompt_msg).strip().lower()
            except KeyboardInterrupt:
                print("\nExecution cancelled by user.")
                sys.exit(0)

            # Resume execution with the user decision
            try:
                state = graph.invoke(Command(resume=user_choice), config)
            except Exception as e:
                print(f"\nError resuming agent execution: {e}", file=sys.stderr)
                sys.exit(1)

        # Print final result
        snapshot = graph.get_state(config)
        final_state = snapshot.values
        
        print("\n" + "=" * 60)
        print("  AGENT EXECUTION FINISHED")
        print("=" * 60)
        
        if final_state.get("approved") is False:
            print("  Status: Rejected by user.")
        elif final_state.get("error"):
            print(f"  Status: Failed with error: {final_state.get('error')}")
        else:
            print("  Status: Success!")
            if final_state.get("pr_summary_path"):
                print(f"  PR summary written to: {final_state.get('pr_summary_path')}")
            if final_state.get("diff"):
                print("\n  Summary of changes:")
                print("  " + "-" * 40)
                diff_lines = final_state["diff"].splitlines()
                for line in diff_lines[:30]:
                    print(f"    {line}")
                if len(diff_lines) > 30:
                    print(f"    ... and {len(diff_lines) - 30} more lines")
        print("=" * 60)


if __name__ == "__main__":
    main()
