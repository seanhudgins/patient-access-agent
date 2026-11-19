"""Handoffs must never be retried after a failure: a write that timed out may still have created
the case or row, and a retry would duplicate it. (In April, Clara reported successful case
creation as failed; this guards the code side of that.)

Run: uv run python tests/test_handoff.py
"""
import pathlib
import socket
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import salesforce_client  # noqa: E402
import tools  # noqa: E402


def _verified() -> dict:
    s = tools.new_session()
    assert tools.verify_patient("James", "Okafor", "1971-11-02", s)["success"]
    return s


def test_salesforce_timeout_is_unconfirmed(monkeypatch=None):
    real_open, real_token = urllib.request.urlopen, salesforce_client._get_access_token
    urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(socket.timeout("timed out"))
    salesforce_client._get_access_token = lambda: "token"
    import os
    os.environ.setdefault("SALESFORCE_INSTANCE_URL", "https://example.invalid")
    try:
        r = salesforce_client.create_case_sf("s", "d")
    finally:
        urllib.request.urlopen, salesforce_client._get_access_token = real_open, real_token
    assert r == {"success": False, "unconfirmed": True, "error": r["error"]} and "confirm" in r["error"]


def test_salesforce_failure_says_do_not_retry():
    real, use = tools.create_case_sf, tools.USE_SALESFORCE
    tools.create_case_sf = lambda **k: {"success": False, "unconfirmed": True, "error": "timed out"}
    tools.USE_SALESFORCE = True
    try:
        r = tools.handoff_to_staff("patient_access", "Wants a person.", _verified(), priority="high")
    finally:
        tools.create_case_sf, tools.USE_SALESFORCE = real, use
    assert r["success"] is False and r["retry"] is False
    assert "may not have gone through" in r["error"] and "555-301-4000" in r["error"]


def test_store_write_error_says_do_not_retry():
    s = _verified()
    store = tools.get_store(s)
    store.add_handoff = lambda h: (_ for _ in ()).throw(TimeoutError("sheets append timed out"))
    r = tools.handoff_to_staff("nurse_line", "Medication question.", s)
    assert r["success"] is False and r["retry"] is False


def test_success_still_works():
    r = tools.handoff_to_staff("nurse_line", "Medication question.", _verified())
    assert r["success"] and r["handoff_id"].startswith("HO-")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
