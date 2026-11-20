"""The late-cancel fee: code owns disclosure and consent.

The bug (STATUS, 2026-11-18): Clara cancelled an appointment under 24 hours away after a plain "yes",
without the fee ever appearing in her text. The model used to pass acknowledge_late_fee=true; now the
model can't assert consent at all. The fee must appear in a reply the patient sees (code appends it if
the model leaves it out), and only the patient's next message, if it's a plain yes, counts as agreement.
"""
import pytest
from conftest import MARIA, run_turn, text, tool, verified

import tools


def test_model_cannot_pass_consent():
    schema = next(t for t in tools.TOOL_SCHEMAS if t["name"] == "cancel_appointment")
    assert "acknowledge_late_fee" not in schema["input_schema"]["properties"]
    s = verified(*MARIA)
    assert tools.cancel_appointment("APT-2002", s).get("requires_acknowledgement")
    r = tools.dispatch_tool("cancel_appointment", {"appointment_id": "APT-2002", "acknowledge_late_fee": True}, s)
    assert '"success": true' not in r


def test_listing_is_not_disclosure():
    s = verified(*MARIA)
    tools.list_appointments(s)
    assert "pending_fee" not in s
    s["turn"] = 5
    assert tools.cancel_appointment("APT-2002", s).get("requires_acknowledgement")


@pytest.mark.parametrize("channel", ["web", "sms", "voice", "portal"])
def test_fee_shown_by_code_then_yes_cancels(fake_model, channel):
    s = verified(*MARIA, channel=channel)
    # Turn 1: the model tries to cancel and replies WITHOUT naming the fee (the original bug)
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("Okay, should I go ahead and cancel it?"))
    reply, _ = run_turn("Cancel my cardiology appointment", s)
    assert tools.get_store(s).appointments()["APT-2002"]["status"] == "scheduled"
    assert "$50" in reply or "fifty dollar" in reply, "code must append the fee the model left out"
    assert "**" not in reply and "⚠" not in reply
    # Turn 2: a plain yes now counts, and the cancel goes through with the fee
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("Done, it's cancelled with the $50 fee."))
    run_turn("Yes", s)
    assert tools.get_store(s).appointments()["APT-2002"]["status"] == "cancelled"


def test_yes_before_disclosure_does_not_count(fake_model):
    s = verified(*MARIA, channel="sms")
    # The patient says yes in the SAME turn the fee first comes up: the model retries, still refused
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"),
               tool("cancel_appointment", appointment_id="APT-2002"), text("Want me to cancel?"))
    run_turn("Yes cancel my heart appointment", s)
    assert tools.get_store(s).appointments()["APT-2002"]["status"] == "scheduled"


@pytest.mark.parametrize("answer", ["No, keep it", "wait, what fee?", "Can I reschedule instead?", "yes but don't charge me"])
def test_anything_but_a_plain_yes_does_not_cancel(fake_model, answer):
    s = verified(*MARIA)
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("There's a $50 fee. Do you accept?"))
    run_turn("Cancel APT-2002", s)
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("Okay."))
    run_turn(answer, s)
    assert tools.get_store(s).appointments()["APT-2002"]["status"] == "scheduled"


def test_consent_is_good_for_one_turn_only(fake_model):
    s = verified(*MARIA)
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("There's a $50 fee. Do you accept?"))
    run_turn("Cancel APT-2002", s)
    fake_model(text("Got it, anything else first?"))  # model doesn't cancel in the yes turn
    run_turn("yes", s)
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("ok"))
    run_turn("thanks, go on", s)
    assert tools.get_store(s).appointments()["APT-2002"]["status"] == "scheduled"


def test_ui_button_text_counts_as_yes():
    from safety import is_plain_yes
    assert is_plain_yes("Yes, I accept the $50 fee. Please cancel it.")
    assert is_plain_yes("Sí, acepto")
    assert not is_plain_yes("Never mind, keep my appointment.")


def test_no_fee_appointment_cancels_directly():
    s = verified(*MARIA)
    r = tools.cancel_appointment("APT-2001", s)
    assert r["success"] and r["late_cancellation_fee_usd"] == 0
