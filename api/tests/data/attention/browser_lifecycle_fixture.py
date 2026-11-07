"""Disposable launcher for the BP4a/BP4b forced-parent-death acceptance."""
import json
import sys
import time
from pathlib import Path

from api.tests.data.attention.test_browser_host import exchange, host
from api.tests.data.attention.fixture_seams import install_network_denial


def main():
    install_network_denial()
    with host(Path(sys.argv[1])).launch("a", "a", 12345) as session:
        result = exchange(session)["result"]
        print(json.dumps({"pid": session.pid, "grandchild": result["grandchild"]}), flush=True)
        time.sleep(600)


if __name__ == "__main__":
    main()
