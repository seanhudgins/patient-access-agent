"""Regression test: the late-cancel fee must be disclosed before it can be accepted.

The bug: Clara cancelled an appointment under 24 hours away and passed acknowledge_late_fee=true
after a plain "yes", without ever telling the patient about the $50 fee. The tool now accepts
the acknowledgement only in a later turn than the one where the fee was disclosed.

Run: uv run python tests/test_late_fee.py
"""
import importlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import mock_data  # noqa: E402
import tools  # noqa: E402


def _maria(turn: int) -> dict:
    importlib.reload(mock_data)
    session = tools.new_session()
    session["turn"] = turn
    assert tools.verify_patient("Maria", "Lopez", "1984-03-12", session)["success"]
    return session


def test_ack_in_same_turn_is_refused():
    s = _maria(1)
    first = tools.cancel_appointment("APT-2002", s, acknowledge_late_fee=True)
    assert first.get("requires_acknowledgement"), "fee must be disclosed first"
    again = tools.cancel_appointment("APT-2002", s, acknowledge_late_fee=True)
    assert again.get("requires_acknowledgement"), "same-turn acknowledgement must not count"


def test_ack_after_disclosure_cancels_with_fee():
    s = _maria(1)
    tools.cancel_appointment("APT-2002", s)
    s["turn"] = 2
    done = tools.cancel_appointment("APT-2002", s, acknowledge_late_fee=True)
    assert done["success"] and done["late_cancellation_fee_usd"] == 50.0


def test_listing_then_ack_next_turn_cancels():
    """The real flow: Clara lists (the card shows the fee), patient accepts in the next message."""
    s = _maria(1)
    tools.list_appointments(s)
    s["turn"] = 2
    done = tools.cancel_appointment("APT-2002", s, acknowledge_late_fee=True)
    assert done["success"] and done["late_cancellation_fee_usd"] == 50.0


def test_listing_and_ack_in_same_turn_is_refused():
    s = _maria(1)
    tools.list_appointments(s)
    assert tools.cancel_appointment("APT-2002", s, acknowledge_late_fee=True).get("requires_acknowledgement")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
