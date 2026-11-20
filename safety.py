"""Guardrails enforced in code, shared by the agent loop and the UI.

Nothing here depends on the model behaving: each check reads the patient's message or Clara's final
reply and changes what the patient sees, whatever the model did.

- Emergencies: a keyword floor (English and Spanish), checked before the model runs. When it fires, the
  code-owned notice is put first in the reply on every exit path and every channel. It is a floor, not a
  classifier: it catches common phrasings, and the prompt handles the rest.
- Payment cards: Luhn-valid card numbers are removed before anything else sees the message.
- Late-cancel fee: code always adds its own fee sentence (naming the appointment) to the reply the patient
  sees, and records agreement only from the patient's next message, if it is a plain yes. The model can't
  assert consent.
- Markdown links and images in Clara's replies are flattened to text, so a reply can't carry a link or a
  tracking image.
"""
from __future__ import annotations

import re
import unicodedata

from constants import LATE_CANCEL_FEE_USD, LATE_CANCEL_HOURS, PATIENT_ACCESS_PHONE


def normalize(text: str) -> str:
    """Lower case, straight apostrophes, no accents: so "I can’t", "I can't" and "Sí" / "si" compare equal."""
    text = (text or "").replace("’", "'").replace("‘", "'").replace("ʼ", "'")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


# --- Emergencies -------------------------------------------------------------------------------

# Matched against normalize(message): lower case, no accents, straight apostrophes.
_EMERGENCY_EN = re.compile(
    r"chest (pain|pressure|tight|hurts)|my chest (hurts|is hurting)|heart attack|"
    r"can'?t breathe|cannot breathe|can not breathe|trouble breathing|short(ness)? of breath|"
    r"stroke|face (is )?droop|slurred speech|unconscious|passed out|faint(ed|ing)?\b|seizure|"
    r"severe bleeding|coughing (up )?blood|anaphyla|throat (is )?(closing|swelling)|overdos|"
    r"suicid|kill myself|end my life|want to die|wanna die|hurt(ing)? myself|self[- ]harm"
)
_EMERGENCY_ES = re.compile(
    r"dolor (de|en el) pecho|me duele el pecho|presion en el pecho|infarto|ataque (al|del) corazon|"
    r"no puedo respirar|no respiro|dificultad para respirar|falta de aire|derrame cerebral|cara caida|"
    r"desmay|inconsciente|convulsi|sangrado (grave|abundante|fuerte)|tosiendo sangre|sobredosis|"
    r"suicid|quitarme la vida|matarme|(me )?quiero morir|hacerme dano"
)

EMERGENCY_NOTICES = {
    "web": ("If this is a medical emergency, call 911 or go to the nearest emergency room now. "
            "If you're having thoughts of suicide or self-harm, call or text 988 (Suicide & Crisis Lifeline)."),
    "sms": "If this is an emergency, call 911 now. For thoughts of suicide or self-harm, call or text 988.",
    "voice": ("If this is a medical emergency, hang up and call nine one one now. "
              "For thoughts of suicide or self-harm, call or text nine eight eight."),
}
EMERGENCY_NOTICES_ES = {
    "web": ("Si es una emergencia médica, llame al 911 o vaya a la sala de emergencias más cercana ahora. "
            "Si tiene pensamientos de suicidio o de hacerse daño, llame o envíe un mensaje al 988 "
            "(Línea de Prevención del Suicidio y Crisis)."),
    "sms": "Si es una emergencia, llame al 911 ahora. Si piensa en suicidarse o hacerse daño, llame o escriba al 988.",
    "voice": ("Si es una emergencia médica, cuelgue y llame al nueve uno uno ahora. "
              "Si piensa en suicidarse o hacerse daño, llame al nueve ocho ocho."),
}
for _notices in (EMERGENCY_NOTICES, EMERGENCY_NOTICES_ES):
    _notices["portal"] = _notices["web"]


def is_emergency(message: str) -> bool:
    m = normalize(message)
    return bool(_EMERGENCY_EN.search(m) or _EMERGENCY_ES.search(m))


def emergency_notice(channel: str | None, message: str = "") -> str:
    """The notice for this channel, in Spanish when the message matched only Spanish terms."""
    m = normalize(message)
    spanish = bool(_EMERGENCY_ES.search(m)) and not _EMERGENCY_EN.search(m)
    notices = EMERGENCY_NOTICES_ES if spanish else EMERGENCY_NOTICES
    return notices.get(channel or "web", notices["web"])


def with_emergency_notice(text: str, channel: str | None, message: str = "") -> str:
    """Always put the code-owned notice first (it carries both 911 and 988), whatever the reply says."""
    notice = emergency_notice(channel, message)
    if text.startswith(notice):
        return text
    return f"{notice}\n\n{text}" if text else notice


def trouble_reply(channel: str | None) -> str:
    """What the patient sees when the model call fails or returns nothing."""
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


# --- Markdown in model replies -----------------------------------------------------------------

_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\(\s*([^)\s]*)[^)]*\)")
_MD_REF_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*\S+.*$", re.MULTILINE)
_MD_REF_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")


def flatten_markdown_links(text: str) -> str:
    """Images become their alt text, links become their text (plus the address if it is plain https),
    so a reply can't hide a javascript: link or load a tracking image."""
    text = _MD_IMAGE.sub(lambda m: m.group(1), text or "")
    text = _MD_REF_DEF.sub("", text)
    text = _MD_REF_LINK.sub(lambda m: m.group(1), text)

    def link(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        return f"{label} ({url})" if url.lower().startswith("https://") and url != label else label
    return _MD_LINK.sub(link, text)


# --- Late-cancel fee: disclosure and consent owned by code ---------------------------------------
#
# session["pending_fee"] = {"appointment_id", "provider_name", "when", "disclosed_turn": int | None}
#   set by tools.cancel_appointment when a late cancel needs agreement.
# At the end of that turn, ensure_fee_disclosed() always appends the code-owned fee sentence (naming the
# appointment) to the reply the patient sees, and records the turn. Text the model wrote never counts.
# At the start of the next turn, record_fee_consent() sets session["late_fee_consent"] to the
# appointment ID only if the patient's message is a plain yes. The consent lasts for that one turn.

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
         "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_words(n: int) -> str:
    """0-999 in words, for text-to-speech ("twenty-four", "one hundred fifty")."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + (f"-{_ONES[n % 10]}" if n % 10 else "")
    rest = n % 100
    return f"{_ONES[n // 100]} hundred" + (f" {number_words(rest)}" if rest else "")


FEE_DOLLARS = int(LATE_CANCEL_FEE_USD) if LATE_CANCEL_FEE_USD == int(LATE_CANCEL_FEE_USD) else None
FEE_TEXT = f"${LATE_CANCEL_FEE_USD:.0f}" if FEE_DOLLARS is not None else f"${LATE_CANCEL_FEE_USD:.2f}"


def fee_sentence(channel: str | None, pending: dict) -> str:
    """The code-owned disclosure, naming the appointment, built from constants."""
    when = pending.get("when")
    who = pending.get("provider_name") or "your provider"
    visit = f"your {when} visit with {who}" if when else f"your visit with {who}"
    if channel == "sms":
        return f"Cancelling {visit} now has a {FEE_TEXT} late fee. Reply YES to accept it or NO to keep it."
    if channel == "voice":
        dollars = f"{number_words(FEE_DOLLARS)} dollar" if FEE_DOLLARS is not None else FEE_TEXT
        return (f"Because {visit} is less than {number_words(LATE_CANCEL_HOURS)} hours away, cancelling now has a "
                f"{dollars} late fee. Say yes to accept it, or no to keep your appointment.")
    return (f"Because {visit} is less than {LATE_CANCEL_HOURS} hours away, cancelling now has a {FEE_TEXT} "
            "late-cancellation fee. Do you accept the fee?")


def _yes_phrases() -> tuple[set[str], set[str]]:
    fee = f"the {FEE_DOLLARS} fee" if FEE_DOLLARS is not None else "the fee"
    heads = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed", "i confirm", "agreed",
             "i agree", "i accept", "accept", "fine", "correct", "si", "claro", "de acuerdo", "acepto",
             "i accept the fee", f"i accept {fee}", "accept the fee", f"accept {fee}", "i agree to the fee",
             f"i agree to {fee}", "acepto el cargo"}
    tails = heads | {
        "please", "por favor", "go ahead", "go ahead and cancel it", "cancel it", "please cancel it",
        "cancel the appointment", "please cancel the appointment", "thats fine", "that is fine",
        "the fee is fine", "cancelala", "cancelalo", "cancela la cita",
    }
    return heads, tails


_HEADS, _TAILS = _yes_phrases()


def is_plain_yes(message: str) -> bool:
    """A deterministic yes: after normalising, the whole message must be built only from a closed set
    of affirmative phrases, starting with one. Questions, conditions and anything else are not consent."""
    if "?" in (message or "") or "¿" in (message or ""):
        return False
    words = re.sub(r"[^a-z0-9 ]+", " ", normalize(message).replace("'", "")).split()
    if not words:
        return False

    def parse(i: int, allowed: set[str]) -> bool:
        if i == len(words):
            return True
        for n in range(min(6, len(words) - i), 0, -1):
            if " ".join(words[i:i + n]) in allowed and parse(i + n, _TAILS):
                return True
        return False
    return parse(0, _HEADS)


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
    """End of a turn: if a late cancel is waiting for agreement, append the code-owned fee sentence.
    The model's own words never count as disclosure (they could mention any $50, e.g. a copay)."""
    pending = session.get("pending_fee")
    if not pending or pending.get("disclosed_turn") is not None:
        return text
    sentence = fee_sentence(session.get("channel", "web"), pending)
    pending["disclosed_turn"] = session.get("turn", 0)
    return f"{text}\n\n{sentence}" if text else sentence


def end_turn(session: dict) -> None:
    """Consent is good for one turn only."""
    session.pop("late_fee_consent", None)
