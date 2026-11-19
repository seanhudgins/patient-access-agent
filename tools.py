import datetime
import re
import json

from dob import normalize_dob  # noqa: F401  (re-exported: tests and agent use tools.normalize_dob)
from data_store import DATA_BACKEND, get_store
from salesforce_client import create_case_sf

LATE_CANCEL_HOURS = 24
LATE_CANCEL_FEE_USD = 50.00
MAX_SLOTS_RETURNED = 6
MAX_VERIFY_ATTEMPTS = 3
USE_SALESFORCE = DATA_BACKEND == "salesforce"
PATIENT_ACCESS_PHONE = "555-301-4000"

IDENTITY_ERROR = (
    "We couldn't verify the caller's identity with the details provided. "
    "Ask them to double-check the spelling of their name and their date of birth."
)
NOT_VERIFIED_ERROR = (
    "The caller has not been verified. Call verify_patient with their first name, last name, "
    "and date of birth before using this tool."
)

# Where each handoff goes, who follows up, and how quickly
HANDOFF_QUEUES = {
    "nurse_line": ("A registered nurse", "will call back within 2 hours during clinic hours"),
    "provider_office": ("The provider's office", "will follow up within 1 business day"),
    "billing": ("A billing specialist", "will follow up within 1 business day"),
    "scheduling": ("A scheduling specialist", "will follow up within 1 business day"),
    "patient_access": ("A Patient Access representative", "will pick up shortly"),
}


def new_session() -> dict:
    """Per-conversation state the agent keeps outside the model."""
    return {"patient_id": None, "failed_verifications": 0, "messages": []}


def dob_matches(provided: str, on_file: str | None) -> bool:
    normalized = normalize_dob(provided)
    return normalized is not None and normalized == on_file


def _verified_patient(session: dict) -> dict | None:
    patient_id = session.get("patient_id")
    return get_store(session).patients().get(patient_id) if patient_id else None


def _parse_start(start_time: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(start_time)


def _when(start_time: str) -> str:
    """Spoken date for a start time, e.g. 'Friday, November 20 at 8:00 AM'. Tools return this so the
    model never works out a weekday itself (it got one wrong in evals)."""
    t = _parse_start(start_time)
    return f"{t:%A, %B} {t.day} at {t:%-I:%M %p}"


def verify_patient(first_name: str, last_name: str, date_of_birth: str, session: dict) -> dict:
    if session["failed_verifications"] >= MAX_VERIFY_ATTEMPTS:
        return {
            "success": False,
            "locked": True,
            "error": "Too many failed verification attempts. Hand the caller off to the patient_access queue.",
        }
    first, last = first_name.strip().lower(), last_name.strip().lower()
    match = next(
        (
            p for p in get_store(session).patients().values()
            if p["first_name"].lower() == first and p["last_name"].lower() == last
            and dob_matches(date_of_birth, p["date_of_birth"])
        ),
        None,
    )
    if match is None:
        session["failed_verifications"] += 1
        return {
            "success": False,
            "error": IDENTITY_ERROR,
            "attempts_remaining": MAX_VERIFY_ATTEMPTS - session["failed_verifications"],
        }
    session["patient_id"] = match["id"]
    session["failed_verifications"] = 0
    return {
        "success": True,
        "first_name": match["first_name"],
        "primary_provider": match["primary_provider"],
        "message": "Caller verified. Patient-specific tools now apply to this patient.",
    }


def list_appointments(session: dict) -> dict:
    patient = _verified_patient(session)
    if patient is None:
        return {"success": False, "error": NOT_VERIFIED_ERROR}
    appointments = [
        {**{k: a[k] for k in ("id", "provider_name", "specialty", "reason", "visit_type", "location", "start_time", "status")},
         "when": _when(a["start_time"])}
        for a in sorted(get_store(session).appointments().values(), key=lambda a: a["start_time"])
        if a["patient_id"] == patient["id"]
    ]
    # Flag appointments inside the late-cancel window. The patient sees the fee on the read-back
    # card in this same turn, so this counts as disclosure (an acknowledgement still has to come
    # in a later turn; see cancel_appointment).
    now = datetime.datetime.now()
    disclosed = session.setdefault("late_fee_disclosed", {})
    for a in appointments:
        hours = (_parse_start(a["start_time"]) - now).total_seconds() / 3600
        a["late_cancel_fee_usd"] = LATE_CANCEL_FEE_USD if a["status"] == "scheduled" and 0 < hours < LATE_CANCEL_HOURS else 0.0
        if a["late_cancel_fee_usd"]:
            disclosed.setdefault(a["id"], session.get("turn", 0))
    return {"success": True, "appointments": appointments}


def get_availability(
    specialty: str = None,
    provider_name: str = None,
    earliest_date: str = None,
    visit_type: str = None,
    session: dict | None = None,
) -> dict:
    if not specialty and not provider_name:
        return {"success": False, "error": "Provide a specialty or a provider name to search."}

    store = get_store(session)
    all_providers = store.providers()
    providers = [
        p for p in all_providers.values()
        if (not specialty or specialty.strip().lower() in p["specialty"].lower())
        and (not provider_name or provider_name.strip().lower() in p["name"].lower())
        and (visit_type != "telehealth" or p["telehealth"])
    ]
    if not providers:
        return {
            "success": False,
            "error": "No matching providers found.",
            "specialties_offered": sorted({p["specialty"] for p in all_providers.values()}),
        }

    earliest = earliest_date or datetime.date.today().isoformat()
    now = datetime.datetime.now().isoformat(timespec="minutes")
    open_slots = store.open_slots()
    slots = sorted(
        (
            {
                "provider_id": p["id"],
                "provider_name": p["name"],
                "specialty": p["specialty"],
                "location": p["location"],
                "telehealth_available": p["telehealth"],
                "start_time": start,
                "when": _when(start),
            }
            for p in providers
            for start in open_slots.get(p["id"], [])
            if start >= earliest and start > now
        ),
        key=lambda s: s["start_time"],
    )
    if not slots:
        return {"success": False, "error": "No open slots found in the next two weeks for that search."}
    result = {
        "success": True,
        "slots": slots[:MAX_SLOTS_RETURNED],
        "referral_required_for_new_patients": [p["name"] for p in providers if p["referral_required_for_new_patients"]],
    }
    if session and session.get("channel") == "voice":
        # On a call, two options are all a caller can hold in their head.
        result["slots"] = result["slots"][:2]
        result["note"] = "Phone call: only the first two openings are shown. If neither works, search again with a later earliest_date."
    return result


def book_appointment(provider_id: str, start_time: str, reason: str, session: dict, visit_type: str = "in_person") -> dict:
    patient = _verified_patient(session)
    if patient is None:
        return {"success": False, "error": NOT_VERIFIED_ERROR}
    store = get_store(session)
    provider_id = provider_id.strip().upper()
    providers = store.providers()
    if provider_id not in providers:
        return {"success": False, "error": f"Provider {provider_id} not found."}
    provider = providers[provider_id]
    if visit_type == "telehealth" and not provider["telehealth"]:
        return {"success": False, "error": f"{provider['name']} does not offer telehealth visits."}

    # Specialists who require a referral only see new patients who have one on file
    if provider["referral_required_for_new_patients"]:
        seen_before = any(
            a["patient_id"] == patient["id"] and a["provider_id"] == provider_id and a["status"] != "cancelled"
            for a in store.appointments().values()
        )
        referrals = [r.strip().lower() for r in (patient.get("referrals") or "").split(",") if r.strip()]
        if not seen_before and provider["specialty"].lower() not in referrals:
            return {
                "success": False,
                "requires_referral": True,
                "error": (
                    f"{provider['name']} ({provider['specialty']}) requires a referral for new patients, and none is on file. "
                    f"Offer a visit with the patient's primary care provider ({patient['primary_provider']}) to get a referral, "
                    "or hand off to the scheduling queue."
                ),
            }

    if not store.take_slot(provider_id, start_time):
        return {"success": False, "error": "That time is no longer available. Please search for open slots again."}

    next_num = max((int(a.split("-")[1]) for a in store.appointments()), default=2000) + 1
    appt = {
        "id": f"APT-{next_num}",
        "patient_id": patient["id"],
        "provider_id": provider_id,
        "provider_name": provider["name"],
        "specialty": provider["specialty"],
        "reason": reason,
        "visit_type": visit_type,
        "location": "Telehealth (video link sent 1 hour before)" if visit_type == "telehealth" else provider["location"],
        "start_time": start_time,
        "duration_min": 30,
        "status": "scheduled",
    }
    store.add_appointment(appt)
    instructions = (
        "A video link will be sent 1 hour before the visit. Join from a quiet, private space."
        if visit_type == "telehealth"
        else "Please arrive 15 minutes early with a photo ID and insurance card."
    )
    return {"success": True, "appointment": {**appt, "when": _when(appt["start_time"])}, "instructions": instructions}


def cancel_appointment(appointment_id: str, session: dict, acknowledge_late_fee: bool = False) -> dict:
    patient = _verified_patient(session)
    if patient is None:
        return {"success": False, "error": NOT_VERIFIED_ERROR}
    store = get_store(session)
    appointment_id = appointment_id.strip().upper()
    appt = store.appointments().get(appointment_id)
    # Another patient's appointment is reported as not found, so its existence isn't disclosed
    if appt is None or appt["patient_id"] != patient["id"]:
        return {"success": False, "error": f"No appointment {appointment_id} found for this patient."}
    if appt["status"] == "cancelled":
        return {"success": False, "error": f"Appointment {appointment_id} is already cancelled."}
    if appt["status"] == "completed":
        return {"success": False, "error": f"Appointment {appointment_id} has already taken place and cannot be cancelled."}

    hours_until = (_parse_start(appt["start_time"]) - datetime.datetime.now()).total_seconds() / 3600
    if hours_until <= 0:
        return {"success": False, "error": f"Appointment {appointment_id} has already started or passed."}
    is_late = hours_until < LATE_CANCEL_HOURS
    # An acknowledgement only counts if the fee was disclosed in an earlier turn, so the patient
    # has actually seen it. Without this the model could disclose and accept in the same breath.
    disclosed = session.setdefault("late_fee_disclosed", {})
    seen_earlier = appointment_id in disclosed and disclosed[appointment_id] < session.get("turn", 0)
    if is_late and not (acknowledge_late_fee and seen_earlier):
        disclosed.setdefault(appointment_id, session.get("turn", 0))
        return {
            "success": False,
            "requires_acknowledgement": True,
            "error": (
                f"Appointment {appointment_id} is less than {LATE_CANCEL_HOURS} hours away. "
                f"Cancelling now incurs a ${LATE_CANCEL_FEE_USD:.2f} late-cancellation fee. "
                "Tell the patient about the fee in your reply and ask if they accept it. Call again with "
                "acknowledge_late_fee=true only after they explicitly agree to the fee in a later message."
            ),
        }

    store.set_appointment_status(appointment_id, "cancelled")
    # Release the slot so it can be booked again
    store.release_slot(appt["provider_id"], appt["start_time"])
    return {
        "success": True,
        "appointment_id": appointment_id,
        "message": f"Appointment {appointment_id} with {appt['provider_name']} on {_when(appt['start_time'])} has been cancelled.",
        "late_cancellation_fee_usd": LATE_CANCEL_FEE_USD if is_late else 0.00,
    }


def get_home_device_status(session: dict) -> dict:
    """The verified patient's home-monitoring devices (blood pressure cuff, scale): connection, last
    sync, last reading, and whether the care team's alert range flagged it."""
    patient = _verified_patient(session)
    if patient is None:
        return {"success": False, "error": NOT_VERIFIED_ERROR}
    devices = get_store(session).home_devices(patient["id"])
    if not devices:
        return {"success": False, "error": "This patient isn't enrolled in a home-monitoring program."}
    now = datetime.datetime.now()
    return {"success": True, "program": devices[0]["program"], "devices": [
        {**d, "days_since_sync": (now - _parse_start(d["last_sync"])).days} for d in devices]}


def get_billing_statement(session: dict) -> dict:
    """The verified patient's open statements with the charge breakdown."""
    patient = _verified_patient(session)
    if patient is None:
        return {"success": False, "error": NOT_VERIFIED_ERROR}
    statements = get_store(session).billing_statements(patient["id"])
    return {"success": True, "statements": statements,
            "note": "Explain only. Never take card or bank details; payments happen in the portal or with billing."}


def list_prescriptions(session: dict) -> dict:
    """The verified patient's prescriptions on file, for the refill picker."""
    patient = _verified_patient(session)
    if patient is None:
        return {"success": False, "error": NOT_VERIFIED_ERROR}
    meds = [
        {k: r[k] for k in ("id", "medication", "prescriber", "refills_remaining", "controlled", "last_filled")}
        for r in get_store(session).prescriptions().values() if r["patient_id"] == patient["id"]
    ]
    return {"success": True, "prescriptions": meds}


def submit_refill_request(medication: str, session: dict) -> dict:
    patient = _verified_patient(session)
    if patient is None:
        return {"success": False, "error": NOT_VERIFIED_ERROR}
    store = get_store(session)
    on_file = [r for r in store.prescriptions().values() if r["patient_id"] == patient["id"]]
    if not on_file:
        return {"success": False, "error": "This patient has no active prescriptions on file."}

    query = medication.strip().lower()
    matches = [r for r in on_file if query and (query == r["id"].lower() or query in r["medication"].lower())]
    if len(matches) != 1:
        return {
            "success": False,
            "error": "Ask the patient which medication they need." if matches or not query else f"No active prescription matching '{medication}'.",
            "medications_on_file": [r["medication"] for r in (matches or on_file)],
        }
    rx = matches[0]
    if rx["controlled"]:
        return {
            "success": False,
            "error": (
                f"{rx['medication']} is a controlled substance and can't be requested through the assistant. "
                "Hand off to the provider_office queue so the prescriber's office can follow up."
            ),
        }

    # Every refill is a request for provider review, never an approval
    request = {
        "id": f"RFL-{len(store.refill_requests()) + 1001}",
        "patient_id": patient["id"],
        "medication": rx["medication"],
        "prescriber": rx["prescriber"],
        "pharmacy": patient["preferred_pharmacy"],
        "status": "pending_provider_review",
        "created": datetime.date.today().isoformat(),
    }
    store.add_refill_request(request)
    return {
        "success": True,
        "request_id": request["id"],
        "medication": rx["medication"],
        "status": "pending_provider_review",
        "message": (
            f"Refill request sent to {rx['prescriber']} for review. This is a request, not an approval. "
            f"The provider will respond within 2 business days. If approved, it goes to {patient['preferred_pharmacy']}; "
            "the provider may also ask for a visit first."
        ),
    }


def _handoff_failed(unconfirmed: bool, detail: str) -> dict:
    """A handoff that didn't go through, or whose result is unknown. Either way: don't retry
    (a retry after an unconfirmed write can create a duplicate case), give the patient the phone number."""
    status = "may not have gone through" if unconfirmed else "didn't go through"
    return {
        "success": False,
        "retry": False,
        "error": (f"The handoff {status} ({detail}). Do not call handoff_to_staff again for this request. "
                  f"Apologize, say you couldn't confirm it reached the team, and give the Patient Access "
                  f"Center number, {PATIENT_ACCESS_PHONE}."),
    }


def handoff_to_staff(
    queue: str,
    summary: str,
    session: dict,
    priority: str = "normal",
    caller_name: str = None,
    callback_phone: str = None,
) -> dict:
    if queue not in HANDOFF_QUEUES:
        return {"success": False, "error": f"Unknown queue '{queue}'. Use one of: {', '.join(HANDOFF_QUEUES)}."}
    store = get_store(session)
    patient = _verified_patient(session)
    # Staff can't follow up with an unverified caller unless they know who to call
    if patient is None and not (caller_name and callback_phone):
        return {
            "success": False,
            "error": (
                "The caller isn't verified, so staff need a way to reach them. Either verify the caller "
                "(name and date of birth) or ask for their name and a callback number, then try again."
            ),
        }
    who, timeframe = HANDOFF_QUEUES[queue]
    handoff = {
        "created": datetime.datetime.now().isoformat(timespec="minutes"),
        "queue": queue,
        "priority": priority,
        "patient_id": patient["id"] if patient else "unverified",
        "caller": f"{patient['first_name']} {patient['last_name']}" if patient else (caller_name or "Unknown caller"),
        "callback_phone": callback_phone or (patient["phone"] if patient else "not provided"),
        "summary": summary,
        "status": "waiting",
    }

    if USE_SALESFORCE:
        result = create_case_sf(
            subject=f"[{queue}] {summary[:80]}",
            description=f"Caller: {handoff['caller']} ({handoff['patient_id']})\n"
                        f"Callback: {handoff['callback_phone']}\nSource: Clara virtual assistant\n\n{summary}",
            priority={"urgent": "High", "high": "High"}.get(priority, "Medium"),
        )
        if not result["success"]:
            return _handoff_failed(result.get("unconfirmed", False), result.get("error", ""))
        handoff["id"] = result["case_number"]
    else:
        try:
            handoff["id"] = f"HO-{len(store.handoffs()) + 1001}"
            store.add_handoff(handoff)
        except Exception as e:  # e.g. a Sheets timeout: the row may or may not have been written
            return _handoff_failed(True, str(e))

    return {
        "success": True,
        "handoff_id": handoff["id"],
        "queue": queue,
        "message": f"{who} {timeframe}. They will see this summary, so the patient won't need to repeat themselves.",
    }


TOOL_SCHEMAS = [
    {
        "name": "verify_patient",
        "description": (
            "Verify the caller's identity by matching first name, last name, and date of birth against patient records. "
            "Required before any patient-specific tool: list_appointments, book_appointment, cancel_appointment, "
            "submit_refill_request. Not needed for general questions or get_availability. "
            "On failure, ask the caller to re-check; never say which detail was wrong."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "date_of_birth": {
                    "type": "string",
                    "description": "Date of birth as YYYY-MM-DD, or exactly as the caller said it if you're unsure how to convert it (common written and spoken forms are understood). Ask the caller for it; never guess.",
                },
            },
            "required": ["first_name", "last_name", "date_of_birth"],
        },
    },
    {
        "name": "list_appointments",
        "description": (
            "List the verified patient's past and upcoming appointments. Use before cancelling or rescheduling "
            "so you can confirm which appointment the patient means."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_availability",
        "description": (
            "Search open appointment slots over the next two weeks by specialty and/or provider. Returns no patient "
            "information and needs no verification. Offer the patient up to three options from the results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "specialty": {
                    "type": "string",
                    "description": "Specialty, e.g. Primary Care, Orthopedics, Cardiology, Dermatology.",
                },
                "provider_name": {"type": "string", "description": "All or part of a provider's name, e.g. 'Chen'."},
                "earliest_date": {"type": "string", "description": "Optional earliest date to search from, YYYY-MM-DD."},
                "visit_type": {"type": "string", "enum": ["in_person", "telehealth"]},
            },
        },
    },
    {
        "name": "book_appointment",
        "description": (
            "Book an open slot from get_availability for the verified patient. "
            "IMPORTANT: Only call this after the patient has chosen a specific slot and confirmed it. "
            "Specialists may require a referral for new patients; the tool enforces this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "provider_id": {"type": "string", "description": "Provider ID from get_availability, e.g. PRV-01."},
                "start_time": {"type": "string", "description": "Exact start_time from get_availability, e.g. 2026-11-03T09:00."},
                "reason": {
                    "type": "string",
                    "description": "Brief, non-clinical reason in the patient's words, e.g. 'Knee pain' or 'Annual physical'.",
                },
                "visit_type": {"type": "string", "enum": ["in_person", "telehealth"]},
            },
            "required": ["provider_id", "start_time", "reason"],
        },
    },
    {
        "name": "list_prescriptions",
        "description": (
            "List the verified patient's prescriptions on file (medication, prescriber, refills remaining, and "
            "whether it's a controlled substance). Call it when a patient wants a refill but hasn't named one "
            "medication; the screen shows them as buttons to tap."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_home_device_status",
        "description": (
            "Look up the verified patient's Heart Health at Home devices (blood pressure cuff and scale): whether each "
            "is syncing, when it last synced, the last reading, and whether the care team's alert range flagged it. "
            "Use when a patient says a device isn't sending readings or asks about the program."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_billing_statement",
        "description": (
            "Get the verified patient's open billing statements: visit, facility and professional charges, what "
            "insurance paid, copay and deductible, balance due, and payment-plan eligibility. Use to explain a bill."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancel_appointment",
        "description": (
            "Cancel one of the verified patient's scheduled appointments. "
            "IMPORTANT: Only call this after you have read back the appointment details and the patient has explicitly confirmed. "
            f"Appointments less than {LATE_CANCEL_HOURS} hours away carry a ${LATE_CANCEL_FEE_USD:.0f} late-cancellation fee: "
            "state the fee in your reply, and set acknowledge_late_fee=true only after the patient explicitly agrees "
            "to the fee in a later message. A plain 'yes' to cancelling is not agreement to the fee."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "Appointment ID from list_appointments, e.g. APT-2001."},
                "acknowledge_late_fee": {
                    "type": "boolean",
                    "description": "Set true only if the patient has explicitly accepted the late-cancellation fee.",
                },
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "submit_refill_request",
        "description": (
            "Submit a refill request for one of the verified patient's existing prescriptions. Every request goes to the "
            "prescriber for review; it is never an approval, so never tell the patient the refill is approved. "
            "If the patient doesn't name a medication, or names one that matches several, the tool lists what's on file "
            "so you can ask which one. Never give dosing or medication advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "medication": {
                    "type": "string",
                    "description": "Medication name as the patient said it, e.g. 'lisinopril'. Empty string if they didn't say.",
                },
            },
            "required": ["medication"],
        },
    },
    {
        "name": "handoff_to_staff",
        "description": (
            "Route the conversation to a human team with a short summary so the patient doesn't have to repeat themselves. "
            "Use for anything out of scope: symptoms, medical or medication questions, and test results (nurse_line); "
            "controlled-substance refills (provider_office); billing disputes (billing); referrals and complex scheduling "
            "(scheduling); failed verification or anything else you can't resolve (patient_access). "
            "Emergencies are NOT handed off: tell the caller to call 911 (or 988 for a mental health crisis) immediately. "
            "Call this as soon as you know the request is out of scope. Do not wait for permission."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {"type": "string", "enum": list(HANDOFF_QUEUES)},
                "summary": {
                    "type": "string",
                    "description": (
                        "2-3 sentences for the staff member: what the caller wants, what you already did or checked, "
                        "and anything time-sensitive. Include only the health details the team needs."
                    ),
                },
                "priority": {
                    "type": "string",
                    "enum": ["normal", "high", "urgent"],
                    "description": "urgent for same-day clinical concerns; high for time-sensitive requests; otherwise normal.",
                },
                "caller_name": {"type": "string", "description": "Required if the caller is not verified: the name they gave."},
                "callback_phone": {
                    "type": "string",
                    "description": "Required if the caller is not verified. Optional otherwise (the number on file is used).",
                },
            },
            "required": ["queue", "summary"],
        },
    },
]

TOOL_DISPATCH = {
    "verify_patient": verify_patient,
    "list_appointments": list_appointments,
    "get_availability": get_availability,
    "book_appointment": book_appointment,
    "cancel_appointment": cancel_appointment,
    "submit_refill_request": submit_refill_request,
    "handoff_to_staff": handoff_to_staff,
    "get_home_device_status": get_home_device_status,
    "get_billing_statement": get_billing_statement,
    "list_prescriptions": list_prescriptions,
}

# Tools that read the conversation's session (verified patient) from the agent, not from the model
_SESSION_TOOLS = {
    "verify_patient", "list_appointments", "get_availability", "book_appointment", "cancel_appointment",
    "submit_refill_request", "handoff_to_staff", "get_home_device_status", "get_billing_statement",
    "list_prescriptions",
}


def dispatch_tool(tool_name: str, tool_input: dict, session: dict) -> str:
    if tool_name not in TOOL_DISPATCH:
        return json.dumps({"success": False, "error": f"Unknown tool: {tool_name}"})
    try:
        kwargs = dict(tool_input)
        kwargs.pop("session", None)  # the model never supplies session state
        if tool_name in _SESSION_TOOLS:
            kwargs["session"] = session
        result = TOOL_DISPATCH[tool_name](**kwargs)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
