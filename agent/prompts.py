"""
contains all the LLM prompt templates in one place.
Keeping prompts separated from node logic makes prompt engineering
a first-class concern — easy to iterate without touching business logic.
"""

# ── Fix Plan Prompt ───────────────────────────────────────────────────────────

FIX_PLAN_PROMPT = """\
You are an expert Go engineer helping to fix a GitHub issue.

## GitHub Issue

Repository: {owner}/{repo}
Issue #{number}: {title}
Labels: {labels}

### Issue Body
{body}

## Repository Structure
{repo_summary}

{snippets_section}

## Your Task

Produce a JSON fix plan with EXACTLY this structure (raw JSON only — no markdown fences):

{{
  "summary": "one-line description of the fix",
  "files_to_modify": ["relative/path/to/file.go"],
  "steps": [
    "Step 1: ...",
    "Step 2: ..."
  ],
  "patches": [
    {{
      "file": "relative/path/to/file.go",
      "search": "exact existing code to replace (verbatim, including indentation)",
      "replace": "exact new code (verbatim, including indentation)",
      "full_content": ""
    }}
  ]
}}

## CRITICAL RULES FOR THE "search" FIELD
 
1. The "search" string MUST be copied CHARACTER FOR CHARACTER from the file content shown above.
   Do NOT rewrite, paraphrase, or reconstruct it from memory.
 
2. Include 4-6 lines of surrounding context (lines before and after the change),
   not just the single line being changed. This makes matching reliable.
 
3. Preserve EXACT whitespace and indentation — tabs vs spaces matter.
 
4. If you cannot find the EXACT text in the snippets above, use "full_content" mode:
   set full_content to the complete new file and leave search/replace empty.
 
5. Do NOT generate a patch for a file whose content was not shown above.
 
## OTHER RULES
- Only modify files directly related to the issue
- Match the existing code style exactly
- No new dependencies unless required
- Follow idiomatic Go: fmt.Errorf("%w") for wrapping, table-driven tests, godoc on exported symbols
- Output ONLY the JSON object — no explanation, no markdown fences
"""

SNIPPETS_SECTION = """\
## Relevant File Contents

{snippets}
"""

FILE_SNIPPET_BLOCK = """\
### {path}
NOTE: Line numbers are shown as prefixes (e.g. "  42: code"). Strip them before using as search strings.
```go
{content}
```"""

# ── Retry Plan Prompt (adds validation failure context) ───────────────────────

RETRY_PLAN_PROMPT = """\
Your previous fix plan failed validation. Here are the errors:

{validation_errors}

Please produce a NEW fix plan that addresses these errors.
Keep the same JSON structure as before.
Output ONLY the raw JSON — no explanation, no fences.

Original issue context:
Repository: {owner}/{repo}
Issue #{number}: {title}
{body}

Repository structure:
{repo_summary}

{snippets_section}
"""

# ── PR Description Prompt ─────────────────────────────────────────────────────

PR_PROMPT = """\
You are an expert Go engineer writing a GitHub pull request description.

## Issue
Repository: {owner}/{repo}
Issue #{number}: {title}

{body}

## Fix Summary
{plan_summary}

## Unified Diff
{diff}

## Instructions
Output EXACTLY two sections separated by a line containing only "---":

Line 1: PR title in conventional commit format (e.g. "fix: handle nil map in ParseFlags")
Lines 3+: PR body in GitHub Markdown. Include:
  - "Fixes #{number}" on the first line
  - A brief description of what changed and why
  - A "## Changes" section listing modified files
  - A "## Testing" section describing how the fix was verified

Output ONLY the title, separator, and body — no extra commentary.
"""
