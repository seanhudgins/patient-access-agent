"""The late-cancel fee: code owns disclosure and consent.

The bug (STATUS, 2026-11-18): Clara cancelled an appointment under 24 hours away after a plain "yes",
without the fee ever appearing in her text. The model used to pass acknowledge_late_fee=true; now the
model can't assert consent at all. The fee must appear in a reply the patient sees (code appends it if
the model leaves it out), and only the patient's next message, if it's a plain yes, counts as agreement.
"""
import pytest
from conftest import MARIA, SARAH, run_turn, text, tool, verified

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
    assert "Dr. Reed" in reply, "the fee sentence names the appointment"
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


NOT_CONSENT = [
    "No, keep it", "wait, what fee?", "Can I reschedule instead?", "yes but don't charge me",
    # from the 2026-11-20 checkpoint review: each of these used to count as a yes
    "Yes, reschedule it instead", "ok but can you waive the fee?", "Sure, what fee?", "Okay what are my options",
    "yeah I can't afford that", "Yes but I won't pay that", "Fine, forget it", "ok, leave it",
    "ok don\u2019t cancel it", "Si cancelo, me cobran?", "yes?", "ok cancel the other one", "sure thing, later",
]


@pytest.mark.parametrize("answer", NOT_CONSENT)
def test_anything_but_a_plain_yes_does_not_cancel(fake_model, answer):
    s = verified(*MARIA)
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("There's a $50 fee. Do you accept?"))
    run_turn("Cancel APT-2002", s)
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("Okay."))
    run_turn(answer, s)
    assert tools.get_store(s).appointments()["APT-2002"]["status"] == "scheduled"


@pytest.mark.parametrize("answer", NOT_CONSENT)
def test_not_consent_phrases(answer):
    from safety import is_plain_yes
    assert not is_plain_yes(answer)


@pytest.mark.parametrize("answer", ["Yes", "yes.", "YES", "Yes, cancel it", "ok go ahead", "Yes please",
                                    "Yes, I accept the $50 fee. Please cancel it.", "Sí, acepto", "si",
                                    "I accept the fee", "sure", "Okay, that's fine"])
def test_plain_yes_phrases(answer):
    from safety import is_plain_yes
    assert is_plain_yes(answer)


def test_model_text_mentioning_50_is_not_disclosure(fake_model):
    """A $50 the model writes (a copay, or injected text) never counts: code always adds its own sentence."""
    s = verified(*MARIA)
    fake_model(tool("cancel_appointment", appointment_id="APT-2002"), text("Your copay was $50. Cancel it?"))
    reply, _ = run_turn("Cancel my cardiology appointment", s)
    assert "late-cancellation fee" in reply and "Dr. Reed" in reply


def test_fee_sentence_names_the_appointment_and_uses_constants():
    import safety
    from constants import LATE_CANCEL_FEE_USD, LATE_CANCEL_HOURS
    pending = {"appointment_id": "APT-2002", "provider_name": "Dr. Reed", "when": "Friday, November 20 at 8:00 AM"}
    for channel in ("web", "sms", "voice", "portal"):
        sentence = safety.fee_sentence(channel, pending)
        assert "Dr. Reed" in sentence and "Friday, November 20" in sentence
    assert f"${LATE_CANCEL_FEE_USD:.0f}" in safety.fee_sentence("web", pending)
    assert str(LATE_CANCEL_HOURS) in safety.fee_sentence("web", pending)
    assert safety.number_words(LATE_CANCEL_HOURS) in safety.fee_sentence("voice", pending)


def test_second_late_cancel_does_not_overwrite_pending():
    s = verified(*SARAH)  # APT-2010 is inside 24 hours
    first = tools.cancel_appointment("APT-2010", s)
    assert first["requires_acknowledgement"]
    s["pending_fee"]["appointment_id"] = "APT-9999"  # pretend another late visit is waiting
    second = tools.cancel_appointment("APT-2010", s)
    assert second["success"] is False and "already waiting" in second["error"]
    assert s["pending_fee"]["appointment_id"] == "APT-9999"


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
