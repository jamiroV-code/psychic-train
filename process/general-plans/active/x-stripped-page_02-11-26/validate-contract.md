# Validate contract: X stripped page

- Write and commit failing fake-reader/fake-clock tests first for account strikes, retry, escalation, reset, 24-hour expiry, single-account fallback, old state, synthetic 20-entry stripped pages, and status.
- Implement account-scoped parse-drop handling without merging aborted tweets or losing page accounting; distinguish classes where feasible and retain existing drift protection.
- Update optional trailing account-health fields and stopped/needs-owner display, plus the incident SPEC and changelog.
- Run targeted X pool, reader and collector tests and synthetic smoke, then one consolidated focused API run and web Vitest/typecheck if touched; no live provider requests.
- Push only the task branch, open one draft PR, and record CI on final head and all gaps in the 11-heading report.
