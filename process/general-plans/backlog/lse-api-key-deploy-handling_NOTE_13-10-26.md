# LSE API key: persistent, non-committed supply to the PC (decision needed)

**Status:** open, decision proposal only. No change made.
**Origin:** equities batch 5 (T45-T51); `lse-live-shape-verification_NOTE_03-10-26.md` operating note.

## Problem

`api/data/lse_adapter.py` reads `LSE_API_KEY` from the API process environment at start. `deploy/start-api.ps1` does not pass it, so the user sets it by hand in each PowerShell window before starting the API. If the scheduled task (Task Scheduler, `deploy/register-tasks.ps1`) restarts the API, it starts without a key: the equities worker does not start (`missing-key`) and equities fetches report unavailable. On 12-10-26 the first manual entry stored only 1 character; a clipboard re-entry fixed it.

## Options to decide

1. **User-level environment variable** (`[Environment]::SetEnvironmentVariable('LSE_API_KEY', ..., 'User')`): persists across reboots, readable by the scheduled task when it runs as that user, no repo file. Risk: visible to every process of that user; set once from the clipboard, never typed into a committed script.
2. **A config entry outside the repo** (for example a file under the user profile that `start-api.ps1` reads and passes to the process): more explicit, but needs a change to `deploy/start-api.ps1` (owned by `deploy/`, RT4, needs the user's PC record) and a file permission note.
3. **Keep the per-window method** and add only a length/empty check message in `start-api.ps1`.

## Constraints

- The key never enters the repo, a commit, a prompt or a log (public repo; LSE forbids redistribution).
- Any change to `deploy/*.ps1` is an RT4 task with a PC acceptance run, like R12.
- Decision belongs to the user; recommend option 1 as the smallest step if a restart without the key keeps happening.
