---
slug: windows-api-gate-repair
date: 2026-11-04
verdict: VIABLE
originating-phase: pvl
---

# Disposable-checkout import isolation

## Hypothesis
The installed project Python can import disposable application sources without importing active-checkout source, despite the installed editable path.

## Mechanism Under Test
Existing project Python launched with `-I`, original root/API source search paths removed, disposable root/API paths prepended, child-only worker settings disabled and inherited SCREENER path/credential settings removed before application imports. The probe checks namespace package paths, concrete source origins, effective cache/equities destinations, loaded modules, and editable finder presence.

## Probe Family
1 — Local process / runtime script.

## Probe Cost Class
cheap-local. Safety gate met: local subprocess and temporary synthetic source snapshot only, no provider calls, real account access, or owner-data writes.

## Probe Method
The eval probe captured `git archive HEAD api`, extracted it into a temporary directory excluding virtual-environment/cache/.env entries, and launched the absolute existing project Python executable with `-I -c <bootstrap> <temporary-root> <original-root>`. The bootstrap sanitized only its child environment, stripped original source roots from sys.path, prepended the temporary roots, checked preloaded application-module origins, imported `api`, `api.data.cache`, and `api.data.equities_store`, asserted namespace/source/store confinement, checked api.main and deploy-conftest origins with find_spec, then checked loaded-module origins and editable finder names. The temporary archive was automatically removed. No pytest invocation was performed.

## Evidence Captured
```json
{"namespace_sandbox_only": true, "cache_origin_and_root_sandbox": true, "equities_path_sandbox": true, "main_and_guard_origins_sandbox": true, "owner_source_modules_loaded": 0, "editable_finders": []}
```
Subprocess exit code: 0. No stderr.
## Verdict
VIABLE

Applies to the checked environment and surfaces. Security reviewer accepted the mechanism with non-waivable execution conditions.

## Resulting Design Constraint
- **What this licenses:** reuse the existing interpreter without dependency installs or changing its .pth files, provided the actual disposable repair-snapshot test process repeats and extends the fail-closed preflight before invoking pytest.main in that same process.
- **What this forbids:** assuming -I alone isolates editable installs; relying only on sys.path appearance; copying owner/untracked private data; starting pytest after an owner import/path/finder/link-escape check fails; running the full gate in the collector's active checkout.
- **What remains uncertain (known-gap):** this api-only probe did not run tests or check every store/config path. Execution must use a complete tracked nonsecret repair snapshot; assert watchlist/layout/config destinations too; seed synthetic default cache/watchlist before deploy-conftest baseline import so the existing real-data guard does not skip; maintain confinement throughout test execution. Full Windows test behavior remains unverified.
