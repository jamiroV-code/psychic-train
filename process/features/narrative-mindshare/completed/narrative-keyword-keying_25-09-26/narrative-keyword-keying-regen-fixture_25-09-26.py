"""Throwaway (plan step 8): regenerate the narrative categories golden fixture
from build_contract_snapshot() against the fixed trigger + keyword-keyed seed."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
import pytest
from api.tests.routers import test_narrative_categories_contract as contract

with pytest.MonkeyPatch.context() as mp, tempfile.TemporaryDirectory() as tmp:
    contract.GOLDEN_PATH.write_text(contract.build_contract_snapshot(mp, Path(tmp)), encoding="utf-8", newline="\n")
print(f"wrote {contract.GOLDEN_PATH}")
