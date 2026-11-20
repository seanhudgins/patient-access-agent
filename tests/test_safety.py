"""The emergency floor and card redaction hold on every exit path and every channel, whatever the model does."""
import pytest
from conftest import SARAH, Response, run_turn, text, tool, verified

import agent
import safety

CHEST = "I need to book a visit, also my chest pain started an hour ago"


@pytest.mark.parametrize("message", [CHEST, "I can't breathe well", "tengo dolor de pecho", "me desmayé hoy",
                                     "No puedo respirar bien", "pienso en quitarme la vida"])
def test_emergency_pattern_english_and_spanish(message):
    assert safety.is_emergency(message)


@pytest.mark.parametrize("message", ["I need a refill", "Book me for a skin check", "What are your hours?"])
def test_no_false_alarm(message):
    assert not safety.is_emergency(message)


@pytest.mark.parametrize("channel", ["web", "sms", "voice", "portal"])
@pytest.mark.parametrize("script", [
    [text("Sure, which day works for you?")],              # model forgets the emergency
    [text("")],                                              # empty reply
    [Response([], "end_turn")],                              # no content at all
    [Response([], "refusal")],                               # refused
    [text("Booking now", stop="max_tokens")],               # cut off
    [RuntimeError("API down")],                              # API exception
])
def test_notice_on_every_exit_path(fake_model, channel, script):
    fake_model(*script)
    s = {"channel": channel, "patient_id": None, "failed_verifications": 0, "messages": []}
    reply, _ = run_turn(CHEST, s)
    assert safety.emergency_notice(channel) in reply
    assert "**" not in reply and "⚠" not in reply  # plain text on every channel


def test_notice_after_loop_cap(fake_model, monkeypatch):
    monkeypatch.setattr(agent, "MAX_LOOP_ITERATIONS", 3)
    fake_model(*[tool("get_availability", specialty="Primary Care") for _ in range(3)])
    s = {"channel": "web", "patient_id": None, "failed_verifications": 0, "messages": []}
    reply, _ = run_turn(CHEST, s)
    assert "911" in reply and "problem processing" in reply


def test_model_reply_with_911_is_not_doubled(fake_model):
    fake_model(text("Please call 911 now."))
    s = {"channel": "web", "patient_id": None, "failed_verifications": 0, "messages": []}
    reply, _ = run_turn(CHEST, s)
    assert reply == "Please call 911 now."


def test_transcript_stays_valid_after_cutoff(fake_model):
    """A max_tokens turn with a half-written tool call must not leave an unanswered tool_use behind."""
    from conftest import Block
    cut = Response([Block("text", text="Let me"), Block("tool_use", name="list_appointments", id="toolu_x")], "max_tokens")
    fake_model(cut)
    s = verified(*SARAH)
    run_turn("show my appointments", s)
    last = s["messages"][-1]
    assert last["role"] == "assistant" and isinstance(last["content"], str)


def test_card_numbers_never_reach_the_model(fake_model):
    client = fake_model(text("I removed that for your security."))
    s = {"channel": "web", "patient_id": None, "failed_verifications": 0, "messages": []}
    run_turn("my card is 4111 1111 1111 1111 exp 12/29", s)
    sent = str(client.calls[0]["messages"])
    assert "4111" not in sent and safety.CARD_REDACTED in sent


def test_non_card_numbers_survive():
    assert safety.redact_payment_details("call 5553014000 about APT-2002") == "call 5553014000 about APT-2002"
