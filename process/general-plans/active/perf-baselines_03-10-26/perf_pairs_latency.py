"""Throwaway timing script (PERF): GET /api/pairs, in-process, fixture data, not network.

Run from repo root: PYTHONPATH=. uv run --project api python <this file>
Seeds a real-size fixture (18 coins -> 153 pairs, 2229 bars) in a temp cache dir.
"""
import statistics, tempfile, time
from pathlib import Path
from fastapi.testclient import TestClient
from api.data import cache
from api.main import app
from api.tests.pairs_fixtures import seed_realistic_results

class MP:  # minimal monkeypatch stand-in
    def setattr(self, obj, name, val): setattr(obj, name, val)

tmp = Path(tempfile.mkdtemp())
cache.CACHE_ROOT = tmp
cache.bootstrap_cache_dirs()
seed_realistic_results(tmp, MP())
c = TestClient(app)
r = c.get("/api/pairs"); assert r.status_code == 200, r.text
n = len(r.json().get("pairs", r.json().get("rows", [])) or [])
ms = []
for _ in range(30):
    t = time.perf_counter(); r = c.get("/api/pairs"); ms.append((time.perf_counter() - t) * 1000); assert r.status_code == 200
s = sorted(ms)
p95 = s[int(round(0.95 * len(s))) - 1]
print(f"pairs_in_body={n} bytes={len(r.content)} calls=30 p50={statistics.median(ms):.1f}ms p95={p95:.1f}ms min={s[0]:.1f} max={s[-1]:.1f}")
