# Backlog: discover-context.mjs routing helpers use POSIX-only path matching, break on Windows

**Date raised**: 25-09-26
**Raised by**: `vc-update-process-agent` closeout of `narrative-keyword-keying_25-09-26`
**Status**: OPEN
**Origin**: UPDATE PROCESS session (this worktree runs on `win32`/Git Bash)

## Why this exists

`.claude/skills/vc-context-discovery/scripts/discover-context.mjs`'s routing helpers
(`groupOf()`, `groupEntrypoints()` in the `--emit-routing`/`--check-routing` code path) assume
POSIX forward-slash paths:

- `groupOf()` does `relPath.replace(/^process\/context\//, "")` then `.split(path.sep)` — on
  `win32`, `path.sep` is `\`, but the collected file paths from the directory walk are already
  backslash-separated (e.g. `process\context\data-sources\all-data-sources.md`), so the forward-
  slash regex never strips the prefix.
- `groupEntrypoints()` filters with `/(^|\/)all-[^/]+\.md$/.test(d.path)` — this forward-slash-only
  regex never matches a backslash-separated Windows path, so every group entrypoint (`all-tests.md`,
  `all-data-sources.md`, `all-planning.md`) is silently excluded.

Net effect: on Windows, `--emit-routing` regenerates the `<!-- GENERATED:routing -->` block with
**zero** context groups even when real, correctly-frontmattered groups exist — it wiped the
`data-sources/`, `planning/`, and `tests/` rows from `process/context/all-context.md` when run
during this session. `--check-routing` will also always report "STALE" on Windows for the same
reason, even when the block is actually correct, so its exit code cannot be trusted on this
platform.

## What happened this session

Ran `discover-context.mjs --emit-routing` to fix an unrelated stale-block warning from
`validate-context-discovery.mjs`. It destroyed the 3 correct group rows. Caught immediately by
reviewing the diff before finishing; manually restored the correct table content by hand. No
groups were actually lost on disk (the `all-{group}.md` files themselves are untouched) — only the
generated summary table in `all-context.md` was briefly wrong, and has been fixed back.

## Fix

Normalize paths to forward slashes before matching, e.g. `d.path.split(path.sep).join("/")` (or
build the regex from `path.sep` dynamically) in both `groupOf()` and `groupEntrypoints()`. Small,
contained fix — same script, ~2 lines.

## Do NOT

Do not run `--emit-routing` again on a Windows/Git Bash checkout until this is fixed — it will
silently wipe the Current Context Groups table. `--check-routing`'s "STALE" verdict is also not
trustworthy on Windows until this is fixed.
