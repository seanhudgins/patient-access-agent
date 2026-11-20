"""Guardrails enforced in code, shared by the agent loop and the UI.

Nothing here depends on the model behaving: each check reads the patient's message or Clara's final
reply and changes what the patient sees, whatever the model did.

- Emergencies: a deterministic pattern (English and Spanish) decides before the model runs; the
  notice is attached on every exit path and every channel.
- Payment cards: Luhn-valid card numbers are removed before anything else sees the message.
- Late-cancel fee: code makes sure the fee is in the reply the patient sees, and records the
  patient's agreement only from their next message. The model can't assert consent.
"""
from __future__ import annotations

import re

from constants import LATE_CANCEL_FEE_TEXT, LATE_CANCEL_HOURS, PATIENT_ACCESS_PHONE

# --- Emergencies -------------------------------------------------------------------------------

EMERGENCY_PATTERN = re.compile(
    # English
    r"chest (pain|pressure|tight)|can'?t breathe|trouble breathing|short(ness)? of breath|"
    r"stroke|face (is )?droop|slurred speech|unconscious|passed out|seizure|severe bleeding|"
    r"anaphyla|throat (is )?(closing|swelling)|overdos|suicid|kill myself|end my life|self[- ]harm|"
    # Spanish
    r"dolor (de|en el) pecho|presi[oó]n en el pecho|no puedo respirar|dificultad para respirar|falta de aire|"
    r"derrame cerebral|cara ca[ií]da|desmay|inconsciente|convulsi|sangrado (grave|abundante|fuerte)|"
    r"sobredosis|quitarme la vida|matarme|hacerme da[nñ]o",
    re.IGNORECASE,
)

# Plain text on every channel: no markdown or emoji (SMS shows them raw, text-to-speech reads them).
EMERGENCY_NOTICES = {
    "web": ("If this is a medical emergency, call 911 or go to the nearest emergency room now. "
            "If you're having thoughts of suicide or self-harm, call or text 988 (Suicide & Crisis Lifeline)."),
    "sms": "If this is an emergency, call 911 now. For thoughts of suicide or self-harm, call or text 988.",
    "voice": ("If this is a medical emergency, hang up and call nine one one now. "
              "For thoughts of suicide or self-harm, call or text nine eight eight."),
}
EMERGENCY_NOTICES["portal"] = EMERGENCY_NOTICES["web"]
_HAS_911 = re.compile(r"911|9-1-1|9 1 1|nine one one", re.IGNORECASE)


def is_emergency(message: str) -> bool:
    return bool(EMERGENCY_PATTERN.search(message or ""))


def emergency_notice(channel: str | None) -> str:
    return EMERGENCY_NOTICES.get(channel or "web", EMERGENCY_NOTICES["web"])


def with_emergency_notice(text: str, channel: str | None) -> str:
    """Put the notice first unless the reply already sends them to 911."""
    if text and _HAS_911.search(text):
        return text
    notice = emergency_notice(channel)
    return f"{notice}\n\n{text}" if text else notice


def trouble_reply(channel: str | None) -> str:
    """What the patient sees when the model call fails or returns nothing."""
    if channel == "voice":
        return ("Sorry, I'm having trouble right now. Please try again, or call Patient Access at "
                f"{PATIENT_ACCESS_PHONE}.")
    return f"Sorry, I'm having trouble right now. Please try again, or call Patient Access at {PATIENT_ACCESS_PHONE}."


# --- Payment cards -----------------------------------------------------------------------------

# 13-19 digit runs (spaces or dashes allowed) that pass the Luhn check are replaced before the
# model, the transcript or the screen sees the message.
_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
CARD_REDACTED = "[card number removed]"


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def redact_payment_details(text: str) -> str:
    def swap(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group())
        return CARD_REDACTED if _luhn_ok(digits) else m.group()
    return _CARD_PATTERN.sub(swap, text or "")


# --- Late-cancel fee: disclosure and consent owned by code ---------------------------------------
#
# session["pending_fee"] = {"appointment_id": ..., "disclosed_turn": int | None}
#   set by tools.cancel_appointment when a late cancel needs agreement.
# At the end of that turn, ensure_fee_disclosed() makes sure the reply the patient sees names the
# fee (appending a fixed sentence if the model's text doesn't) and records the turn.
# At the start of the next turn, record_fee_consent() sets session["late_fee_consent"] to the
# appointment ID only if the patient's message is a plain yes. The consent lasts for that one turn.

FEE_SENTENCES = {
    "web": (f"Because this visit is less than {LATE_CANCEL_HOURS} hours away, cancelling now has a "
            f"{LATE_CANCEL_FEE_TEXT} late-cancellation fee. Do you accept the fee?"),
    "sms": f"Cancelling now has a {LATE_CANCEL_FEE_TEXT} late fee. Reply YES to accept it or NO to keep the visit.",
    "voice": ("Because this visit is less than twenty-four hours away, cancelling now has a fifty dollar late fee. "
              "Say yes to accept it, or no to keep your appointment."),
}
FEE_SENTENCES["portal"] = FEE_SENTENCES["web"]
_NAMES_FEE = re.compile(r"\$\s?50\b|\b50 dollars?\b|\bfifty[- ]dollars?\b|\b50 d[oó]lares\b|\bcincuenta d[oó]lares\b",
                        re.IGNORECASE)
_YES = re.compile(
    r"^\s*(yes|yeah|yep|yup|sure|ok|okay|i accept|accept|i agree|agreed|confirm|go ahead|that'?s fine|fine|"
    r"s[ií]|claro|de acuerdo|acepto)\b",
    re.IGNORECASE,
)
_NO = re.compile(r"\b(no|nope|not|don'?t|do not|never ?mind|keep|wait|stop|cancel that)\b", re.IGNORECASE)


def names_fee(text: str) -> bool:
    return bool(_NAMES_FEE.search(text or ""))


def is_plain_yes(message: str) -> bool:
    """A deterministic yes: starts with an affirmative and contains no negation."""
    return bool(_YES.search(message or "")) and not _NO.search(message or "")


def record_fee_consent(session: dict, message: str) -> None:
    """Start of a turn: a fee disclosed in the previous turn is accepted only by a plain yes now."""
    session.pop("late_fee_consent", None)
    pending = session.get("pending_fee")
    if not pending:
        return
    if pending.get("disclosed_turn") == session.get("turn", 0) - 1 and is_plain_yes(message):
        session["late_fee_consent"] = pending["appointment_id"]
    session.pop("pending_fee", None)  # one chance: anything else means it has to be asked again


def ensure_fee_disclosed(session: dict, text: str) -> str:
    """End of a turn: if a late cancel is waiting for agreement, the patient must see the fee."""
    pending = session.get("pending_fee")
    if not pending or pending.get("disclosed_turn") is not None:
        return text
    if not names_fee(text):
        sentence = FEE_SENTENCES.get(session.get("channel", "web"), FEE_SENTENCES["web"])
        text = f"{text}\n\n{sentence}" if text else sentence
    pending["disclosed_turn"] = session.get("turn", 0)
    return text


def end_turn(session: dict) -> None:
    """Consent is good for one turn only."""
    session.pop("late_fee_consent", None)
