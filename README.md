# OpenSourceAgent — Python + LangGraph

An agentic AI system that solves issues from open-source Go repositories. Given a GitHub issue URL, the agent analyzes the repository, identifies relevant files, generates a fix plan, applies code changes, validates them using Go tooling, and produces a pull request summary.The system is built using LangGraph, Python, GitPython, and the Gemini API.

--- 

## Architecture & System Features

Unlike a simple linear pipeline or a basic prompt wrapper, this implementation uses a Directed Acyclic Graph (with loops) orchestrated by **LangGraph**:

```
         ┌─────────────────────────────────────────────────────────────┐
         │                    AgentState (TypedDict)                   │
         │ issue, repo_dir, summary, plan,patches,validation, diff, pr │
         │                                                             │   
         └─────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
          ┌───────────────────────────────────────────────────────────────┐
          │                      LangGraph StateGraph                     │
          │                                                               │
          │  fetch_issue → clone_repo → explore_repo → plan_fix [Gemini]  │    
          │  [GitHub API]  [GitPython]   [AST/Walk]        │              │
          │                                                │              │
          │                                      ┌─── human_review ──┐    │
          │                                      │    (interrupt)    │    │
          │                                      └─────────┬─────────┘    │
          │                                                │              │
          │                                          apply_patches        │
          │                                                │              │
          │                                             validate          │
          │                                            /        \         │
          │                                     PASS -/          \- FAIL  │
          │                                      /                  \     │
          │                            generate_diff            retry     │
          │                                  │                   (x2)     │
          │                           write_pr_summary              │     │
          │                                  │                      │     │
          │                                 END ◄───────────────────┘     │
          └───────────────────────────────────────────────────────────────┘
```
---

## Project Structure
```
PythonAgent/
│
├── agent/
│   ├── graph.py
│   ├── state.py
│   ├── prompts.py
│   └── nodes/
│       ├── fetch.py
│       ├── clone.py
│       ├── explore.py
│       ├── plan.py
│       ├── review.py
│       ├── patch.py
│       ├── validate.py
│       ├── diff.py
│       └── pr.py
├── cli.py
├── requirements.txt
├── .env
├── README.md
└── workspace(where repo data,operation and output will be saved)
```
---

## How it Works

### 1. Issue Understanding : 
The agent fetches the GitHub issue and extracts relevant information such as title, description, labels, and repository details.

### 2. Repository Exploration
The repository is cloned locally and analyzed. Relevant Go files and code snippets are identified using issue context and repository structure.

### 3. Fix Planning
Gemini generates a structured plan containing:
- Summary of the issue
- Files to modify
- Implementation steps
- Proposed patches

### 4. Human Review (Makes secure)
Before modifying code, the generated plan can be reviewed and approved.

### 5. Code Modification
Patches are applied to the target files. Backup copies are created before any changes.

### 6. Validation
The agent validates the generated solution using:
```
go build ./...
go vet ./...
go test ./...
gofmt -l .
```

### 7. PR Generation
After successful validation:

- Git diff is generated
- Pull request title is generated
- Pull request description is generated

**pr_summary.md** is created witth pr title and description

---

### Prerequisites
- Python 3.10+
- Go toolchain installed (for `go build/vet/test` validation)

---

## How to Run the Project locally

#### 1. Clone the Repository

```bash
git clone https://github.com/adarshkatare6/PythonAgent
cd PythonAgent
```

#### 2. Create a Virtual Environment

##### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

##### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies

Install required packages:

```bash
pip install -r requirements.txt
```

#### 4. Set up your environment variables:
   ```bash
   # On Windows (PowerShell):
   $env:GEMINI_API_KEY="your-gemini-api-key"
   $env:GITHUB_TOKEN="your-github-personal-access-token" # Optional, to avoid API rate limits

   # On Linux/macOS or Git Bash:
   export GEMINI_API_KEY="your-gemini-api-key"
   export GITHUB_TOKEN="your-github-personal-access-token"
   ```

#### 5. Run the agent
Run the agent against a GitHub issue using:

```bash
python cli.py run <github-issue-url> 
```

**Aproove the changes agent makes in code**
---

### Options:
- `--workspace DIR`: Where repositories are cloned (default: `./workspace`)
- `--model MODEL`: The Gemini model to use (default: `gemini-2.5-flash`)
- `--auto-approve`: Skip human review and proceed automatically
- `--max-retries INT`: Maximum validation retry loops (default: `2`)

---
### Example:

```
bash
python cli.py run https://github.com/spf13/cobra/issues/1904
```

```
  import google.generativeai as genai
============================================================
  Starting OpenSourceAgent Python + LangGraph Rewrite
============================================================
  Issue URL     : https://github.com/spf13/cobra/issues/2193
  Workspace     : Folder\PythonAgent\workspace
  Gemini Model  : gemini-2.5-flash
  Auto Approve  : False
  Max Retries   : 2
============================================================

[1/9] Fetching issue: https://api.github.com/repos/spf13/cobra/issues/2193
  ✓  #2193: BUG: Incorrect copy of command context from parent to child (trivial fix)
     state=open  labels=[]

[2/9] Cloning repository: https://github.com/spf13/cobra.git
  repo already cloned at Folder\PythonAgent\workspace\spf13\cobra — pulling latest…
  ✓  repo ready at Folder\PythonAgent\workspace\spf13\cobra
  ✓  branch 'agent/fix-issue-2193' created

[3/9] Exploring repository structure…
  ✓  indexed 36 Go files
  ✓  5 relevant file(s) loaded for LLM context

[4/9] Generating fix plan (Gemini / attempt 1)…
  ✓  plan generated: Fixes stale context propagation to child commands by ensuring the parent's context always overwrites the child's.
     files to modify: ['command.go']
     patches: 1

══════════════════════════════════════════════════
  FIX PLAN
══════════════════════════════════════════════════
  Summary : Fixes stale context propagation to child commands by ensuring the parent's context always overwrites the child's.

  Files to modify:
    • command.go
  Patches: 1 patch(es)
    • command.go  (search-replace, ~5 lines)
══════════════════════════════════════════════════

[5/9] Do you approve this fix plan? (y/n) y
══════════════════════════════════════════════════
  ✓  Plan approved — proceeding with patches.

[6/9] Applying 1 patch(es)…
  ✗  command.go  [error]
       error: Search string not found in 'command.go'.
  Searched for (first 120 chars): '\t// We have to pass global context to children command\n\t// if context is present on the parent command.\n\tif cmd.ctx == n'
  Tip: Switch to full_content mode in the retry plan.

[7/9] Running validation checks…
  ✓  go build ./...
  ✓  go vet ./...
  ✓  go test ./...
  ✓  gofmt -l .
  ✓  All validation checks passed!

[8/9] Generating unified diff…
  ✓  diff generated (57 lines)

[9/9] Generating Pull Request summary using Gemini…
  ✓  PR summary written to D:Folder\PythonAgent\workspace\spf13\cobra\pr_summary.md

============================================================
  AGENT EXECUTION FINISHED
============================================================
  Status: Success!
  PR summary written to: D:Folder\PythonAgent\workspace\spf13\cobra\pr_summary.md 
```

---

**For any querry mail me at adarshkatare6@gmail.com**

GOOD LUCK MATE
