"""Node 7 — validate: runs subprocess go build, vet, test, gofmt."""
from __future__ import annotations

import os
import subprocess

from agent.state import AgentState
from agent.nodes.patch import restore_backups

import shutil
GOFMT = shutil.which("gofmt") or r"C:\Program Files\Go\bin\gofmt.exe"

def validate(state: AgentState) -> dict:
    """
    Runs Go build, vet, test, and formatting checks on the repository.
    If any check fails, restores the .bak backup files.

    Returns updates to AgentState:
        validation, error
    """
    repo_dir = state["repo_dir"]
    patches = state.get("plan", {}).get("patches", [])

    print("\n[7/9] Running validation checks…")

    results = {}
    all_passed = True

    # 1. go build ./...
    passed, output = _run_cmd(repo_dir, ["go", "build", "./..."])
    results["go build ./..."] = {"passed": passed, "output": output}
    if passed:
        print("  ✓  go build ./...")
    else:
        print("  ✗  go build ./...")
        all_passed = False

    # 2. go vet ./...
    if all_passed:
        passed, output = _run_cmd(repo_dir, ["go", "vet", "./..."])
        results["go vet ./..."] = {"passed": passed, "output": output}
        if passed:
            print("  ✓  go vet ./...")
        else:
            print("  ✗  go vet ./...")
            all_passed = False
    else:
        results["go vet ./..."] = {"passed": False, "output": "Skipped because build failed"}

    # 3. go test ./...
    if all_passed:
        passed, output = _run_cmd(repo_dir, ["go", "test", "./..."])
        results["go test ./..."] = {"passed": passed, "output": output}
        if passed:
            print("  ✓  go test ./...")
        else:
            print("  ✗  go test ./...")
            all_passed = False
    else:
        results["go test ./..."] = {"passed": False, "output": "Skipped because build/vet failed"}

    # 4. gofmt - first auto-fix formatting, then verify
    if all_passed:
        # Auto-fix formatting issues before checking
        # This handles tab/space mismatches from LLM-generated code
        _run([GOFMT, "-w", "."], repo_dir)
        
        passed, output = _run_gofmt(repo_dir)
        results["gofmt -l ."] = {"passed": passed, "output": output}
        if passed:
            print("  ✓  gofmt -l .")
        else:
            print("  ✗  gofmt -l .")
            all_passed = False
    else:
        results["gofmt -l ."] = {"passed": False, "output": "Skipped because build/vet/test failed"}

    if not all_passed:
        print("  ✗  Validation failed. Restoring backups…")
        restore_backups(repo_dir, patches)
        return {
            "validation": results,
            "error": "Validation checks failed. Restored backups.",
        }

    # If they all passed, clean up backups (since they are no longer needed)
    _clean_backups(repo_dir, patches)

    print("  ✓  All validation checks passed!")
    return {"validation": results, "error": None}


def _run_cmd(dir: str, args: list[str]) -> tuple[bool, str]:
    try:
        import os
        env = os.environ.copy()
        go_path_win = r"C:\Program Files\Go\bin"
        if go_path_win not in env.get("PATH", "") and os.path.exists(os.path.join(go_path_win, "go.exe")):
            env["PATH"] = go_path_win + os.pathsep + env.get("PATH", "")

        # Use shell=True for windows to ensure environment/PATH variables resolve go correctly
        res = subprocess.run(
            args,
            cwd=dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
            env=env,
        )
        return res.returncode == 0, res.stdout
    except Exception as e:
        return False, f"Failed to execute command {' '.join(args)}: {e}"

def _run(cmd: list, cwd: str) -> None:
    subprocess.run(cmd, cwd=cwd, capture_output=True)

def _run_gofmt(dir: str) -> tuple[bool, str]:
    try:
        import os
        env = os.environ.copy()
        go_path_win = r"C:\Program Files\Go\bin"
        if go_path_win not in env.get("PATH", "") and os.path.exists(os.path.join(go_path_win, "go.exe")):
            env["PATH"] = go_path_win + os.pathsep + env.get("PATH", "")

        res = subprocess.run(
            ["gofmt", "-l", "."],
            cwd=dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
            env=env,
        )
        if res.returncode != 0:
            return False, res.stdout
        output = res.stdout.strip()
        if output:
            return False, f"unformatted files:\n{output}"
        return True, ""
    except Exception as e:
        return False, f"Failed to execute gofmt: {e}"


def _clean_backups(repo_dir: str, patches: list[dict]) -> None:
    """Removes the backup .bak files after a successful run."""
    for patch in patches:
        file_rel = patch.get("file", "")
        if not file_rel:
            continue
        abs_path = os.path.join(repo_dir, file_rel.replace("/", os.sep))
        bak = abs_path + ".bak"
        if os.path.exists(bak):
            try:
                os.remove(bak)
            except OSError:
                pass
