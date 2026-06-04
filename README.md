# OpenSourceAgent — Python + LangGraph Rewrite

An advanced, stateful agentic system built using LangGraph, Python, GitPython, and the Gemini API. This is a robust framework built around explicit state management, retry logic, human-in-the-loop interrupts, and rollback capabilities.

## Architecture & System Features

Unlike a simple linear pipeline or a basic prompt wrapper, this implementation uses a Directed Acyclic Graph (with loops) orchestrated by **LangGraph**:

```
                   ┌─────────────────────────────────────────┐
                   │           AgentState (TypedDict)         │
                   │  issue, repo_dir, summary, plan,         │
                   │  patches, validation, diff, pr           │
                   └─────────────────────────────────────────┘
                                       │
          ┌────────────────────────────▼──────────────────────────────┐
          │                      LangGraph StateGraph                  │
          │                                                            │
          │  fetch_issue → clone_repo → explore_repo → plan_fix       │
          │       │             │             │            │          │
          │  [GitHub API]  [GitPython]   [AST/Walk]    [Gemini]       │
          │                                                │          │
          │                                      ┌─── human_review ──┐│
          │                                      │    (interrupt)    ││
          │                                      └─────────┬─────────┘│
          │                                                │          │
          │                                          apply_patches    │
          │                                                │          │
          │                                             validate      │
          │                                            /        \     │
          │                                     PASS -/          \- FAIL
          │                                      /                  \ │
          │                            generate_diff            retry │
          │                                  │                   (x2) │
          │                           write_pr_summary              │ │
          │                                  │                      │ │
          │                                 END ◄───────────────────┘ │
          └───────────────────────────────────────────────────────────┘
```

### Key Framework Capabilities:
1. **Typed Shared State**: Every node communicates via a single typed schema (`AgentState`), preventing side-effects and making data flow predictable.
2. **First-class Interrupts**: LangGraph's `interrupt()` suspends execution state before applying changes, allowing human developers to review and approve/reject plans.
3. **Automatic Rollbacks / Backup Restoration**: Before any code patch is written, a `.bak` copy is generated. If validation checks fail, the code is rolled back to pristine state automatically.
4. **Self-Correction Retry Loop**: On validation failure, the error logs (from build, vet, or tests) are injected back into Gemini's context for a self-correction cycle (up to 2 times).
5. **Observability & Checkpointing**: `MemorySaver` preserves the execution thread history, enabling crashes/suspensions to be resumed seamlessly.

---

## Getting Started

### Prerequisites
- Python 3.10+
- Go toolchain installed (for `go build/vet/test` validation)

### Installation

1. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your environment variables:
   ```bash
   # On Windows (PowerShell):
   $env:GEMINI_API_KEY="your-gemini-api-key"
   $env:GITHUB_TOKEN="your-github-personal-access-token" # Optional, to avoid API rate limits

   # On Linux/macOS or Git Bash:
   export GEMINI_API_KEY="your-gemini-api-key"
   export GITHUB_TOKEN="your-github-personal-access-token"
   ```

---

## Usage

Run the agent against a GitHub issue using:

```bash
python cli.py run <github-issue-url> [options]
```

### Options:
- `--workspace DIR`: Where repositories are cloned (default: `./workspace`)
- `--model MODEL`: The Gemini model to use (default: `gemini-2.5-flash`)
- `--auto-approve`: Skip human review and proceed automatically
- `--max-retries INT`: Maximum validation retry loops (default: `2`)

### Example:

```bash
python cli.py run https://github.com/spf13/cobra/issues/1904
```

1. **Fetch**: Connects to the GitHub REST API to retrieve issue metadata.
2. **Clone**: Uses GitPython to clone or pull the target repository.
3. **Explore**: Indexes Go source files, packages, and exported symbols.
4. **Plan**: Prompts Gemini to produce a structured JSON fix plan.
5. **Review**: Halts and prompts: *Do you approve this fix plan? (y/n)*.
6. **Patch**: Backs up modified files and applies search-and-replace patches.
7. **Validate**: Runs `go build ./...`, `go vet ./...`, `go test ./...`, and `gofmt -l .`.
8. **Diff & PR**: Creates a unified diff and compiles a `pr_summary.md` detailing the solution.
