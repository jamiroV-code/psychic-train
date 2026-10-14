# data-integration tooling

Owner-run tooling for sourcing data (fetch tiers, approvals, provenance). It is a
separate uv project: the API never imports it, no CI step installs it, and the API
wheel and `api/uv.lock` are unchanged by it.

## Install (on demand)

    uv sync --project tools/data-integration

`scrapling install` (browser download) is a separate opt-in step.

## Tests

    UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q

Markers `integration`, `browser`, `antibot` are deselected by default. Tests run
against an isolated cache root; the real cache is never touched.

## Isolation check

    python tools/data-integration/scripts/check_clean_install.py

## Local state (outside the repo)

Approvals, scrape store and evidence live under `%LOCALAPPDATA%\my_site\`; override
with `DIT_APPROVALS_DIR`, `DIT_SCRAPE_DIR`, `DIT_EVIDENCE_DIR`.
