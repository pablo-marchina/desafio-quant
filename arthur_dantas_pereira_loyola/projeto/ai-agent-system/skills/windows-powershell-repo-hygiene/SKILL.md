---
name: windows-powershell-repo-hygiene
description: Use when working in this Windows/PowerShell repository environment and Codex needs to recover from sandbox failures, make small controlled file edits, preserve UTF-8 encoding, inspect git diffs, run venv-based Python validation, avoid committing secrets/caches/venv, or safely commit and push changes.
---

# Windows PowerShell Repo Hygiene

Use this skill to keep repository work safe when the Windows sandbox or PowerShell editing path becomes part of the task.

## Core Rules

- Prefer `apply_patch` for manual edits.
- If `apply_patch` fails because of Windows sandbox issues, use PowerShell only for small, targeted edits.
- After any PowerShell write, immediately reread the file and inspect `git diff`.
- Write UTF-8 without BOM when PowerShell edits source or Markdown files.
- Do not edit or commit `.env`, secrets, `venv`, caches, or generated local state.
- Use the project venv Python, not global Python.
- Keep commits small and explainable.

## Safe PowerShell Editing Pattern

Use this pattern only when patching is blocked or unsuitable:

```powershell
$path = 'relative\\path\\file.py'
$text = [System.IO.File]::ReadAllText($path)
$text = $text.Replace('old text', 'new text')
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $text, $utf8NoBom)
```

Then always run:

```powershell
Get-Content -Raw relative\\path\\file.py
git diff -- relative/path/file.py
```

## Encoding Hygiene

Watch for these diff smells:

- invisible BOM markers before code, especially before `from __future__`.
- mojibake patterns such as unexpected `A`-with-tilde sequences, replacement characters, or changed accented words.
- large unrelated line-ending churn.
- accidental Markdown/code block quote damage from PowerShell string interpolation.

If they appear, fix before testing or committing.

## Validation Checklist

For Python project changes, run from the correct directory with the venv:

```powershell
.\\venv\\Scripts\\python.exe -m pip check
```

From `ai-agent-system`:

```powershell
..\\venv\\Scripts\\python.exe -m pytest
```

If only docs changed, tests may be unnecessary, but still inspect `git diff`.

## Git Hygiene

Before staging:

```powershell
git status -sb
git diff --stat
git diff -- <changed-files>
```

Stage only intended files:

```powershell
git add path/to/file1 path/to/file2
```

Before commit:

```powershell
git config user.name
git config user.email
git diff --cached --stat
```

Expected project identity:

```text
malafisor-arthurloyola <malafisor.es@gmail.com>
```

After commit and push:

```powershell
git status -sb
git log -1 --pretty=format:"%h %an <%ae> %s"
```

## When Updating Obsidian

The Obsidian vault lives outside the workspace, so writes need explicit approval. Keep edits small and use UTF-8 without BOM. Update the single handoff file, not a new handoff per session.

## Project-Specific Reminders

- Keep real code under `ai-agent-system/src/radar/`.
- Do not recreate old empty scaffolds such as `agent/`, `api/`, `config/`, `llm/`, or `memory` at the root of `ai-agent-system`.
- Never use external APIs unless the user explicitly authorizes them.
- Never commit secrets or `.env`.