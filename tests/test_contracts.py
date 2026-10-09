import json
from pathlib import Path

from stockai.contracts.helpers import check_no_lookahead, stub_out
from stockai.contracts.schemas import validate

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"


def test_fixture_valid_and_no_lookahead():
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    assert validate(snap, "snapshot") == []
    assert check_no_lookahead(snap) == []


def test_lookahead_is_caught():
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["news"].append({"id": "x", "title": "t", "url": "u", "source": "s", "published_at": "2026-10-10T00:00:00"})
    assert check_no_lookahead(snap)


def test_stub_out_valid():
    assert validate(stub_out("m2"), "module_out") == []


def test_invalid_snapshot_blocked():
    assert validate({"meta": {}}, "snapshot")
