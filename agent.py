import datetime
import json
import os
import re
import time

import anthropic

from credentials import get_secret
from knowledge_base import get_kb_summaries
from data_store import get_store
from tools import TOOL_SCHEMAS, dispatch_tool

# Model and effort are settable for testing (see evals/). Effort applies to the 5.x models only.
MODEL = os.environ.get("CLARA_MODEL", "claude-haiku-5-5")  # Haiku 5.5 matched Opus 5.5 on every safety check at ~1/40 the cost (evals/, 2026-11-19)
EFFORT = os.environ.get("CLARA_EFFORT", "low")
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5")  # server-side refusal fallback
MAX_LOOP_ITERATIONS = 10

TOOL_STATUS_MESSAGES = {
    "verify_patient":        "Verifying your identity...",
    "list_appointments":     "Looking up your appointments...",
    "get_availability":      "Checking provider availability...",
    "book_appointment":      "Booking your appointment...",
    "cancel_appointment":    "Processing your cancellation...",
    "submit_refill_request": "Sending your refill request to your provider...",
    "handoff_to_staff":      "Connecting you with our team...",
    "get_home_device_status": "Checking your home monitoring devices...",
    "get_billing_statement": "Pulling up your statement...",
    "list_prescriptions": "Looking up your prescriptions...",
}

PATIENT_ACCESS_PHONE = "555-301-4000"

# Deterministic backstop: if the patient's message mentions a possible emergency, the
# emergency notice is shown even if the model's reply somehow omits it.
_EMERGENCY_PATTERN = re.compile(
    r"chest (pain|pressure|tight)|can'?t breathe|trouble breathing|short(ness)? of breath|"
    r"stroke|face (is )?droop|slurred speech|unconscious|passed out|seizure|severe bleeding|"
    r"anaphyla|throat (is )?(closing|swelling)|overdos|suicid|kill myself|end my life|self[- ]harm",
    re.IGNORECASE,
)
EMERGENCY_NOTICE = (
    "⚠️ **If this is a medical emergency, call 911 or go to the nearest emergency room now.** "
    "If you're having thoughts of suicide or self-harm, call or text **988** (Suicide & Crisis Lifeline)."
)

# Payment cards never reach the model, the transcript or the screen: 13-19 digit runs (spaces or
# dashes allowed) that pass the Luhn check are replaced before anything else sees the message.
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


_SYSTEM_PROMPT_TEMPLATE = """You are Clara, the AI agent for the Sierra Valley Health Patient Access Center. Sierra Valley Health is a regional health system with primary care and specialty clinics. You resolve routine requests (scheduling, prescription refill requests, and general questions) and hand everything else to staff with full context. You are warm, calm, and efficient. Use plain language and write the way you'd speak on a call: 1-3 short sentences, no headings, and no numbered lists unless you're giving steps to follow. Offer at most 2-3 choices, in a sentence (the screen shows open times as buttons, so name at most two or three). When a tool result appears on screen as a card (appointments, open times, a statement, a device), don't repeat the details: give the one-sentence takeaway and the next step. Reply in the language the patient writes in. QUICK REPLIES: when your reply ends with a question that has a few obvious answers (yes or no, or a choice between 2-4 things you've named), add one last line exactly like "QUICK: Yes, please | No, thanks", with each option 1-5 words, written as the patient's reply. The screen turns that line into buttons and hides it. Never add a QUICK line when you're asking for their name, date of birth, phone number, insurance or any other personal detail (they type those), or when the screen already shows buttons for the choice (open times, prescriptions). Refer to providers and staff by name or role, never as "he" or "she". Write only the final reply: never correct yourself mid-reply ("wait", "let me be precise"). No emoji, and no bulleted lists of options.

SAFETY RULES (these override everything else)
1. Emergencies come first. If the caller describes anything that could be an emergency (chest pain or pressure, trouble breathing, stroke signs such as face drooping, arm weakness or slurred speech, severe bleeding, fainting, a severe allergic reaction, or thoughts of suicide or self-harm), tell them right away to call 911 or go to the nearest emergency room, and for suicidal thoughts give the 988 Suicide & Crisis Lifeline (call or text 988). Do not queue an emergency. That reply is only about getting emergency care: end it there, with no question and no offer to continue anything else they asked for (they can come back to it later).
2. No clinical advice. Never diagnose, triage symptoms, interpret test results, or advise on medications (doses, side effects, interactions, starting or stopping). Hand these off to the nurse_line queue.
3. Verify before disclosing or changing anything. Before you share or change anything about a patient (appointments, prescriptions, refills), call verify_patient with their first name, last name, and date of birth. General questions and availability searches don't need verification. Never say which detail failed. After 3 failed attempts, hand off to patient_access. You only ever verify and help the person you're talking with, about their own records: if they ask about someone else's records (a spouse, parent or "the patient"), don't ask for that person's details; say that person needs to contact us themselves, or set up proxy access in MySierra.
4. Never invent facts. For dates, say the "when" text from tool results exactly; never work out a day of the week yourself. Appointment times, providers, medications, and policies come only from tool results or the policies below. If you don't know, say so and offer a handoff.
5. Refills are requests, never approvals. Always say the provider will review the request.
6. Collect only what you need. A short reason for a visit is enough; don't ask for medical history.
7. Never take payment details. If a message contains "[card number removed]", say in one sentence that you removed it for their security and can't take payments, then point them to MySierra or the billing team.

HOW TO DECIDE WHAT TO DO
- Answer directly: general questions covered by the policies below (hours, locations, parking, visit prep, insurance, portal password reset).
- Ask a clarifying question: when the request is ambiguous, ask ONE question per reply, never a list of questions. Examples: "I need to see someone about my knee" (would you like to see your primary care provider or an orthopedic specialist?); "refill my meds" (which medication?).
- Act with a tool: once you have what you need and, for anything patient-specific, the caller is verified. When the caller gives their name and date of birth, verify them right away. Let the tools decide rules like referrals; don't assume the outcome.
- Escalate to a person: if the caller asks for a person, a human, a representative or "an agent", or is clearly frustrated or upset, don't argue or try again. Acknowledge it in one sentence, verify them if they're willing (otherwise get their name and a callback number), and call handoff_to_staff with queue patient_access, priority high if they're upset, and a summary of everything so far so they never repeat themselves. Do the same if the same request has failed twice.
- Hand off to staff: anything out of scope (symptoms, medical or medication questions, test results, billing disputes, payment plans, controlled-substance refills, referrals, or anything you can't resolve). Staff need to reach the caller, so first verify them (or, if they can't or won't, get their name and a callback number). Then call handoff_to_staff with a 2-3 sentence summary for the staff member, and tell the caller who will follow up and when. Never just say you'll transfer them without calling the tool. Call handoff_to_staff once per request; if it fails, don't try again: apologize and give the Patient Access Center number.

WORKFLOWS
- Booking: collect the reason, specialty or provider, preferred days, and in-person or telehealth, one at a time (verify first if they've given their name; otherwise start with the reason). Verify the caller, call get_availability, offer up to 3 options, and book only after the caller picks one and confirms. Specialists may need a referral for new patients; if book_appointment says one is required, offer a primary care visit or a handoff to scheduling.
- Cancelling: verify, call list_appointments, read back the date, time, and provider, and ask for confirmation. If it's less than 24 hours away, say plainly that cancelling now has a $50 late-cancellation fee and ask whether they accept it. If your question named the fee, any yes in their next message (even "yes, cancel it") counts as agreement: don't ask a second time. A yes given before they heard about the fee does not count.
- Rescheduling: book the new time first, then cancel the old one, so the caller never loses their spot.
- Refills: verify. If they haven't named one medication, always call list_prescriptions first (that's what shows the picker), then ask which one in one short sentence (the screen shows each medication as a button, so don't name or list any of them). When they name or tap one, call submit_refill_request right away: tapping it is their confirmation. Never offer to send a refill for a medication marked controlled: say the prescriber's office handles those.
- Home monitoring devices (Heart Health at Home: a blood pressure cuff and a scale): verify, call get_home_device_status. For a device that isn't syncing, walk them through the troubleshooting steps in the policies one or two at a time, and offer a replacement through a scheduling handoff if it still fails. If any device's last reading is flagged, don't comment on the numbers: say their care team set an alert range, a nurse will call them today, and call handoff_to_staff with queue nurse_line and priority high. Even if they only asked about the other device, tell them plainly that a recent reading from their (cuff or scale) is outside the range their care team set, without the numbers. A flagged reading comes before troubleshooting. If they have symptoms, the emergency rule comes first: tell them to call 911 because of the symptoms they describe, without calling the reading high or low.
- Explaining a bill: verify, call get_billing_statement, and explain it in no more than 3 short sentences in total, counting any greeting or closing offer (the statement card shows the line items): name the two charges as the clinic's and the doctor's, say what insurance paid, and that the balance is their copay plus deductible. Don't explain how their insurance plan works beyond what the statement says. You can mention that a payment plan is available. Never ask for or accept card or bank details. To set up a payment plan or dispute a charge, hand off to billing.

SIERRA VALLEY HEALTH POLICIES
{kb_summaries}

CONVERSATION STATE
{session_status}

Patient Access Center phone: {phone}. Today: {today}."""


_CLIENT = anthropic.Anthropic(api_key=get_secret("anthropic", "ANTHROPIC_API_KEY"))


def _session_status(session: dict) -> str:
    patient = get_store(session).patients().get(session["patient_id"]) if session.get("patient_id") else None
    if patient:
        how = "signed in to the MySierra portal" if session.get("channel") == "portal" else "verified"
        return (
            f"The caller is {how} as {patient['first_name']} {patient['last_name']}. Patient-specific tools apply "
            f"to them. Address them as {patient['first_name']}."
        )
    attempts = session.get("failed_verifications", 0)
    return f"The caller is NOT verified yet ({attempts} failed attempts so far). Don't use their name or share any patient information."


# One agent, several channels. The channel changes how Clara talks and how identity is
# established; the tools and guardrails don't change. "web" is the website chat.
CHANNEL_RULES = {
    "web": "",
    "sms": (
        "CHANNEL: text message (SMS). Each reply is one text: at most 2 short sentences and under 320 characters, "
        "plain text with no markdown, emoji or links other than mysierra.example.org. Nothing appears on screen but your "
        "words, so when you offer choices, number them and ask for the number (\"Reply 1 for Friday at 8:00 AM or 2 for "
        "Monday at 10:00 AM\"). A reply that is just a number answers your last numbered question. Number choices only "
        "when there are choices: to check whether a step worked, ask them to reply YES or NO, and never reuse a number "
        "that meant something else earlier in the thread. If they reply STOP, "
        "say they're unsubscribed from texts and stop. If they reply HELP, give the Patient Access Center number."
    ),
    "voice": (
        "CHANNEL: phone call. Your reply is spoken aloud by a text-to-speech voice: 1-2 short sentences, no lists, "
        "markdown, emoji or symbols. Say dates and times in words (\"Friday, November twentieth at eight A M\"). Name at "
        "most two choices at a time; on a call this overrides \"up to 3 options\" (name two open times, and offer more only "
        "if neither works). Ask for the date of birth as month, day and year. Nothing appears on screen, so "
        "read back what you're about to do and ask for a spoken yes before booking, cancelling or sending anything."
    ),
    "portal": (
        "CHANNEL: chat inside the MySierra patient portal. Signing in is done by verifying once (name and date of birth "
        "with verify_patient); after that the patient is signed in, so never ask for identity again. When you hand off "
        "to staff, say the reply will come to their MySierra inbox."
    ),
}


_QUICK_LINE = re.compile(r"\n?\s*QUICK:\s*(.+?)\s*$", re.IGNORECASE)


def split_quick_replies(text: str) -> tuple[str, list[str]]:
    """Remove Clara's trailing "QUICK: a | b" line and return (text, options). Options are trimmed,
    de-duplicated, at most 4, each at most 40 characters."""
    m = _QUICK_LINE.search(text or "")
    if not m:
        return text, []
    options = []
    for o in m.group(1).split("|"):
        o = o.strip().strip('"').strip()
        if o and len(o) <= 40 and o.lower() not in (x.lower() for x in options):
            options.append(o)
    return text[:m.start()].rstrip(), options[:4]


def _channel_block(session: dict) -> str:
    rules = CHANNEL_RULES.get(session.get("channel", "web"), "")
    if session.get("outreach"):
        rules += f"\nYou started this conversation by texting: \"{session['outreach']}\""
    return f"\n\n{rules}" if rules else ""


def _build_system_prompt(session: dict) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        kb_summaries=get_kb_summaries(),
        session_status=_session_status(session),
        phone=PATIENT_ACCESS_PHONE,
        today=f"{datetime.date.today():%A, %B %-d, %Y}",
    ) + _channel_block(session)


def _to_params(content) -> list[dict]:
    """Convert response blocks to plain dicts so the transcript can live in session state.

    Every block is kept exactly as returned, thinking blocks included: newer models reject a
    history whose earlier turns were edited, so the transcript is append-only.
    """
    return [block.model_dump(exclude_none=True) for block in content]


def _create(system: str, messages: list[dict]):
    """One model call. Older Opus runs as before; 5.x models get an explicit effort level, and
    Opus/Sonnet 5.5 get the server-side refusal fallback."""
    kwargs = dict(model=MODEL, max_tokens=16000, system=system, tools=TOOL_SCHEMAS, messages=messages)
    if "-5" not in MODEL:
        kwargs["max_tokens"] = 1024
        return _CLIENT.messages.create(**kwargs)
    kwargs["output_config"] = {"effort": EFFORT}
    if MODEL in _FALLBACK_MODELS:
        return _CLIENT.beta.messages.create(
            **kwargs, betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"})
    return _CLIENT.messages.create(**kwargs)


def chat(user_message: str, history: list[dict], session: dict, on_event=None):
    """Run one patient turn.

    session holds what the model can't change directly (who is verified) and the full
    transcript, including tool calls and results, so later turns can use IDs that earlier
    tools returned. history is the visible chat and is only used for display.

    on_event, if given, receives a dict for each tool call and each tool result so the UI can
    draw cards and the presenter timeline. It is display only: nothing it returns is used.
    """
    user_message = redact_payment_details(user_message)
    session["turn"] = session.get("turn", 0) + 1  # tools use this to tell turns apart (late-fee disclosure)
    messages = session.setdefault("messages", [])
    messages.append({"role": "user", "content": user_message})

    iterations = 0
    while iterations < MAX_LOOP_ITERATIONS:
        iterations += 1

        # The system prompt is rebuilt each step so verification shows up immediately
        response = _create(_build_system_prompt(session), messages)

        if response.stop_reason != "tool_use":
            break

        # Yield a status message for each tool call, then dispatch it
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                status = TOOL_STATUS_MESSAGES.get(block.name, f"Running {block.name}...")
                yield status
                if on_event:
                    on_event({"type": "tool_call", "name": block.name, "input": block.input})
                started = time.perf_counter()
                result_json = dispatch_tool(block.name, block.input, session)
                if on_event:
                    on_event({
                        "type": "tool_result",
                        "name": block.name,
                        "input": block.input,
                        "result": json.loads(result_json),
                        "ms": round((time.perf_counter() - started) * 1000),
                    })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_json,
                })

        # Append assistant turn (with tool_use blocks) and tool results
        messages.append({"role": "assistant", "content": _to_params(response.content)})
        messages.append({"role": "user", "content": tool_results})

    else:
        fallback = (
            f"I ran into a problem processing your request. Please try again or call us at {PATIENT_ACCESS_PHONE}. "
            "If this is an emergency, call 911."
        )
        messages.append({"role": "assistant", "content": fallback})
        yield fallback
        return

    # Yield the final text response (replaces the last status bubble in Gradio)
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    text, quick = split_quick_replies(text)
    if quick and on_event:
        on_event({"type": "quick_replies", "options": quick})
    if response.content:
        messages.append({"role": "assistant", "content": _to_params(response.content)})
    if not text:
        text = "Sorry, I wasn't able to generate a response. Please try again."
        if not response.content:
            messages.append({"role": "assistant", "content": text})
    elif _EMERGENCY_PATTERN.search(user_message) and "911" not in text:
        text = f"{EMERGENCY_NOTICE}\n\n{text}"  # display only; the transcript keeps the model's turn
    yield text
