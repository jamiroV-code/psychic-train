# PC sync scripts (Windows PowerShell)

Git flow (D-28, updated 2026-11-11): GitHub `main` is canonical and the PC must fast-forward it at least daily. Agents may self-merge only when all owner merge gates in `AGENTS.md` pass. No direct pushes to `main`.

UNVERIFIED IN CI: these scripts were written in a container with no PowerShell. Run each with `-WhatIf` on the PC first.

| Script | What it does |
|---|---|
| `sync-main.ps1` | `git fetch`, then `git pull --ff-only` on `main` only when `main` is checked out and the tree is clean and fast-forwardable. Otherwise it changes nothing and logs one line to `%LOCALAPPDATA%\my_site\logs\sync-main.log`. Never merges, rebases, resets or forces. This is download-only; it never uploads local edits or commits. |
| `push-task-branch.ps1` | Refuses on `main`. Pushes only the checked-out `claude/*` branch (`-Branch` may confirm the name but never bypasses the `claude/*` rule; `main`, detached HEAD and any other branch are refused) using `git push -u origin`, then opens a draft PR with `gh` if installed, else prints the URL. Never uses force. |

Both take `-WhatIf` (print what they would do, change nothing).

## Exit codes

| Script | Code | Meaning |
|---|---|---|
| both | 0 | success, dry run, or (sync-main only) skipped on purpose: not on `main`, dirty tree, or diverged |
| `sync-main.ps1` | 1 | real failure: not a git repo, `git fetch` failed, or the fast-forward was refused |
| `push-task-branch.ps1` | 1 | refused (not a `claude/*` branch, `main`, detached HEAD) or the push failed |
| `push-task-branch.ps1` | 2 | pushed, but no draft PR was opened (`gh` missing, not logged in, or PR already exists); the message gives the URL |

Task Scheduler shows a non-zero code as a failed run, so a real failure is visible there.

## Task Scheduler (required; every 15 minutes)

The task `my_site sync-main` runs `sync-main.ps1` every 15 minutes while the owner is logged on. Create or repair it from PowerShell:

```powershell
$script = "$env:USERPROFILE\documents\my_site\scripts\pc-sync\sync-main.ps1"
$task = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`""
schtasks.exe /Create /SC MINUTE /MO 15 /TN "my_site sync-main" /TR $task /IT /F
```

Verify it with `schtasks.exe /Query /TN "my_site sync-main" /V /FO LIST`. Run the script with `-WhatIf`, then run the task by hand and inspect `%LOCALAPPDATA%\my_site\logs\sync-main.log`. Confirm a successful fast-forward at least once per day.

A `skipped: working tree is not clean`, `not main`, or diverged message means sync did not happen. Preserve local work and resolve it on a task branch/PR; never clean, reset, stash or overwrite to make the task pass. `push-task-branch.ps1` is a separate upload step for a checked-out `claude/*` branch; `sync-main.ps1` never uploads or commits local work.

## Secrets

Secrets and cookie files live outside the repo (for example a secrets folder under your user profile) and must never be added to it. These scripts read none.
