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

## Owner probes (loopback only)

    uv run --project tools/data-integration python tools/data-integration/scripts/probe_tier1.py
    uv run --project tools/data-integration python tools/data-integration/scripts/probe_tier2.py

Each creates its own temp approval record and temp cache, talks only to a loopback fixture
server and prints PASS or FAIL. `probe_tier1.py` (AC-16) needs no browser. `probe_tier2.py`
(AC-17) renders a JS page in a browser, so run `scrapling install` once, or set
`DIT_BROWSER_EXECUTABLE` to a Chromium path; it also prints size hints and timing.
Tier 3 is covered by gating tests only; it is not proven against any real protected site.
