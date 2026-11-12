import datetime
import os
import re

import anthropic

from knowledge_base import get_kb_summaries
from data_store import get_store
from tools import TOOL_SCHEMAS, dispatch_tool

MODEL = "claude-opus-4-6"
MAX_LOOP_ITERATIONS = 10

TOOL_STATUS_MESSAGES = {
    "verify_patient":        "Verifying your identity...",
    "list_appointments":     "Looking up your appointments...",
    "get_availability":      "Checking provider availability...",
    "book_appointment":      "Booking your appointment...",
    "cancel_appointment":    "Processing your cancellation...",
    "submit_refill_request": "Sending your refill request to your provider...",
    "handoff_to_staff":      "Connecting you with our team...",
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

_SYSTEM_PROMPT_TEMPLATE = """You are Clara, the AI agent for the Sierra Valley Health Patient Access Center. Sierra Valley Health is a regional health system with primary care and specialty clinics. You resolve routine requests (scheduling, prescription refill requests, and general questions) and hand everything else to staff with full context. You are warm, calm, and efficient. Use plain language and keep replies short (1-3 sentences): patients may be reading this on a phone or hearing it on a call.

SAFETY RULES (these override everything else)
1. Emergencies come first. If the caller describes anything that could be an emergency (chest pain or pressure, trouble breathing, stroke signs such as face drooping, arm weakness or slurred speech, severe bleeding, fainting, a severe allergic reaction, or thoughts of suicide or self-harm), tell them right away to call 911 or go to the nearest emergency room, and for suicidal thoughts give the 988 Suicide & Crisis Lifeline (call or text 988). Do not queue an emergency and do not continue with other tasks until they have been directed to emergency care.
2. No clinical advice. Never diagnose, triage symptoms, interpret test results, or advise on medications (doses, side effects, interactions, starting or stopping). Hand these off to the nurse_line queue.
3. Verify before disclosing or changing anything. Before you share or change anything about a patient (appointments, prescriptions, refills), call verify_patient with their first name, last name, and date of birth. General questions and availability searches don't need verification. Never say which detail failed. After 3 failed attempts, hand off to patient_access.
4. Never invent facts. Appointment times, providers, medications, and policies come only from tool results or the policies below. If you don't know, say so and offer a handoff.
5. Refills are requests, never approvals. Always say the provider will review the request.
6. Collect only what you need. A short reason for a visit is enough; don't ask for medical history.

HOW TO DECIDE WHAT TO DO
- Answer directly: general questions covered by the policies below (hours, locations, parking, visit prep, insurance, portal password reset).
- Ask a clarifying question: when the request is ambiguous, ask ONE question per reply, never a list of questions. Examples: "I need to see someone about my knee" (would you like to see your primary care provider or an orthopedic specialist?); "refill my meds" (which medication?).
- Act with a tool: once you have what you need and, for anything patient-specific, the caller is verified. When the caller gives their name and date of birth, verify them right away. Let the tools decide rules like referrals; don't assume the outcome.
- Hand off to staff: anything out of scope (symptoms, medical or medication questions, test results, billing disputes, controlled-substance refills, referrals, or anything you can't resolve). Staff need to reach the caller, so first verify them (or, if they can't or won't, get their name and a callback number). Then call handoff_to_staff with a 2-3 sentence summary for the staff member, and tell the caller who will follow up and when. Never just say you'll transfer them without calling the tool.

WORKFLOWS
- Booking: collect the reason, specialty or provider, preferred days, and in-person or telehealth. Verify the caller, call get_availability, offer up to 3 options, and book only after the caller picks one and confirms. Specialists may need a referral for new patients; if book_appointment says one is required, offer a primary care visit or a handoff to scheduling.
- Cancelling: verify, call list_appointments, read back the date, time, and provider, and ask for confirmation. If it's less than 24 hours away, explain the $50 late-cancellation fee and get explicit agreement first.
- Rescheduling: book the new time first, then cancel the old one, so the caller never loses their spot.
- Refills: verify, confirm which medication, then call submit_refill_request.

SIERRA VALLEY HEALTH POLICIES
{kb_summaries}

CONVERSATION STATE
{session_status}

Patient Access Center phone: {phone}. Today: {today}."""


_CLIENT = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _session_status(session: dict) -> str:
    patient = get_store().patients().get(session["patient_id"]) if session.get("patient_id") else None
    if patient:
        return (
            f"The caller is verified as {patient['first_name']} {patient['last_name']}. Patient-specific tools apply "
            f"to them. Address them as {patient['first_name']}."
        )
    attempts = session.get("failed_verifications", 0)
    return f"The caller is NOT verified yet ({attempts} failed attempts so far). Don't use their name or share any patient information."


def _build_system_prompt(session: dict) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        kb_summaries=get_kb_summaries(),
        session_status=_session_status(session),
        phone=PATIENT_ACCESS_PHONE,
        today=datetime.date.today().isoformat(),
    )


def _to_params(content) -> list[dict]:
    """Convert response blocks to plain dicts so the transcript can live in session state."""
    blocks = []
    for block in content:
        if block.type == "text" and block.text.strip():
            blocks.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            blocks.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
    return blocks


def chat(user_message: str, history: list[dict], session: dict):
    """Run one patient turn.

    session holds what the model can't change directly (who is verified) and the full
    transcript, including tool calls and results, so later turns can use IDs that earlier
    tools returned. history is the visible chat and is only used for display.
    """
    messages = session.setdefault("messages", [])
    messages.append({"role": "user", "content": user_message})

    iterations = 0
    while iterations < MAX_LOOP_ITERATIONS:
        iterations += 1

        response = _CLIENT.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_build_system_prompt(session),  # rebuilt each step so verification shows up immediately
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            break

        # Yield a status message for each tool call, then dispatch it
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                status = TOOL_STATUS_MESSAGES.get(block.name, f"Running {block.name}...")
                yield status
                result_json = dispatch_tool(block.name, block.input, session)
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
    if not text:
        text = "Sorry, I wasn't able to generate a response. Please try again."
    elif _EMERGENCY_PATTERN.search(user_message) and "911" not in text:
        text = f"{EMERGENCY_NOTICE}\n\n{text}"
    messages.append({"role": "assistant", "content": text})
    yield text
