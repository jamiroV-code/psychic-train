"""Create `api/data/watchlist.json` from the checked-in example when absent.

`watchlist.json` is gitignored (pipeline-completeness D1), so a fresh
checkout has no watchlist and `/screener` starts empty. This script is the
documented, non-manual fresh-checkout path (D5): it copies
`api/data/watchlist.example.json` to the real watchlist ONLY when the target
does not exist. It never overwrites and never merges — an existing watchlist
is the user's data.

`api/data/watchlist.py` is deliberately NOT changed (out of this plan's lane);
a loader fallback is named Future Work.

Exit codes: 0 = target created, or already present; 1 = the example file is
missing.

Run: `uv run --project api python -m api.scripts.bootstrap_watchlist`
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse  # noqa: E402
import shutil  # noqa: E402

from api.data import watchlist as watchlist_store  # noqa: E402

DEFAULT_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "watchlist.example.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--example", default=None,
                        help=f"source file (default {DEFAULT_EXAMPLE_PATH})")
    parser.add_argument("--target", default=None,
                        help="destination watchlist (default api/data/watchlist.json)")
    # `[] if argv is None else argv` so a bare `main()` under pytest never
    # consumes pytest's own sys.argv (C5/E7).
    args = parser.parse_args([] if argv is None else argv)

    example = Path(args.example) if args.example else DEFAULT_EXAMPLE_PATH
    # Read the module attribute at CALL time so tests that redirect it work.
    target = Path(args.target) if args.target else watchlist_store.DEFAULT_WATCHLIST_PATH

    if target.exists():
        print(f"watchlist already present, left untouched: {target}")
        return 0
    if not example.exists():
        print(f"bootstrap_watchlist: example file not found: {example}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example, target)
    print(f"watchlist created from {example}: {target}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # pragma: no cover
        print(f"bootstrap_watchlist: fatal: {exc!r}", file=sys.stderr)
        sys.exit(1)
