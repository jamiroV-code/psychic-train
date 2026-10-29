# PC sync scripts (Windows PowerShell)

Git flow for the owner's PC (decisions.md D-28): GitHub is the shared source of truth, nobody pushes to `main`,
the PC pushes task branches and opens DRAFT PRs, the owner merges every PR.

UNVERIFIED IN CI: these scripts were written in a container with no PowerShell. Run each with `-WhatIf` on the PC first.

| Script | What it does |
|---|---|
| `sync-main.ps1` | `git fetch`, then `git pull --ff-only` on `main` only when `main` is checked out and the tree is clean and fast-forwardable. Otherwise it changes nothing and logs one line to `%LOCALAPPDATA%\my_site\logs\sync-main.log`. Never merges, rebases, resets or forces. |
| `push-task-branch.ps1` | Refuses on `main`. Pushes only the checked-out `claude/*` branch (or a named one passed with `-Branch`) using `git push -u origin`, then opens a draft PR with `gh` if installed, else prints the URL. Never uses force. |

Both take `-WhatIf` (print what they would do, change nothing).

## Task Scheduler (sync-main every 15 minutes)

1. Open Task Scheduler, Create Task (not Basic Task). Name: `my_site sync-main`.
2. General: run only when the user is logged on.
3. Triggers: New, Daily, repeat task every 15 minutes for a duration of 1 day.
4. Actions: Start a program: `powershell.exe`; arguments: `-NoProfile -ExecutionPolicy Bypass -File "<repo path>\scripts\pc-sync\sync-main.ps1"`.
5. Test once with `-WhatIf` in a terminal, then run the task by hand and read the log file.

## Secrets

Secrets and cookie files live outside the repo (for example a secrets folder under your user profile) and must never be added to it. These scripts read none.
