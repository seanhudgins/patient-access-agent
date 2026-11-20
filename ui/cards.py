"""Turn Clara's tool events into patient-facing chat cards and plain-English status lines.

Input is the list of events agent.chat() reports through on_event. Output is HTML the server
writes (never user text without escaping), so the chatbot can render it with sanitize_html=False.
"""
import datetime
from html import escape

from constants import LATE_CANCEL_FEE_TEXT, LATE_CANCEL_FEE_USD, LATE_CANCEL_HOURS
from data_store import get_store
from tools import clock
from ui.icons import icon

QUEUE_LABELS = {
    "nurse_line": ("Nurse line", "nurse"),
    "provider_office": ("Provider office", "building"),
    "billing": ("Billing", "dollar"),
    "scheduling": ("Scheduling", "calendar"),
    "patient_access": ("Patient Access", "headset"),
}
WRITE_TOOLS = {"book_appointment", "cancel_appointment", "submit_refill_request", "handoff_to_staff"}


def _when(iso: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return escape(str(iso))
    return f"{dt:%a} {dt.day} {dt:%b} · {clock(dt)}"  # portable: %-d / %-I fail on Windows


def _provider_name(provider_id: str | None) -> str | None:
    if not provider_id:
        return None
    p = get_store().providers().get(provider_id)
    return p["name"] if p else None


def status_title(event: dict) -> str:
    """Plain-English status for a tool call. Tool names never appear in the patient view."""
    name, args = event["name"], event.get("input") or {}
    if name == "verify_patient":
        return "Verifying your identity…"
    if name == "list_appointments":
        return "Looking up your appointments…"
    if name == "get_availability":
        who = args.get("provider_name") or args.get("specialty")
        return f"Checking {who}'s schedule…" if args.get("provider_name") else f"Checking {who or 'provider'} availability…"
    if name == "book_appointment":
        who = _provider_name(args.get("provider_id"))
        return f"Booking with {who}…" if who else "Booking your appointment…"
    if name == "cancel_appointment":
        return "Processing your cancellation…"
    if name == "submit_refill_request":
        med = args.get("medication")
        return f"Sending a refill request for {med}…" if med else "Sending your refill request…"
    if name == "list_prescriptions":
        return "Looking up your prescriptions…"
    if name == "get_home_device_status":
        return "Checking your home monitoring devices…"
    if name == "get_billing_statement":
        return "Pulling up your statement…"
    if name == "handoff_to_staff":
        label = QUEUE_LABELS.get(args.get("queue"), ("our team", ""))[0]
        return f"Connecting you with {label}…"
    return "Working on it…"


_TICK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12.5l4 4 8-9"/></svg>'


def steps_html(calls: list[dict], results: list[dict]) -> str:
    """The turn's tool calls as a checklist (done, failed, or in progress)."""
    items = []
    for i, call in enumerate(calls):
        title = status_title(call).rstrip("…")
        if i < len(results):
            ok = bool((results[i].get("result") or {}).get("success"))
            state, mark = ("done", _TICK) if ok else ("held", "!")
            detail = f'<span class="step-detail">{escape(status_detail(results[i]))}</span>'
        else:
            state, mark, detail = "pending", "", ""
            title += "…"
        items.append(f'<li class="{state}"><span class="step-mark" aria-hidden="true">{mark}</span>'
                     f'<span class="step-title">{escape(title)}</span>{detail}</li>')
    return f'<ol class="clara-steps" aria-label="What Clara is doing">{"".join(items)}</ol>'


def status_detail(event: dict) -> str:
    """One short line under a finished status, from the tool result."""
    r = event.get("result") or {}
    name = event["name"]
    if not r.get("success"):
        if r.get("requires_referral"):
            return "A referral is needed first."
        if r.get("requires_acknowledgement"):
            return "Needs your OK on the late-cancellation fee."
        if name == "verify_patient":
            return "Those details didn't match our records."
        return "Couldn't complete that step."
    if name == "verify_patient":
        return "Identity verified."
    if name == "get_availability":
        return f"{len(r.get('slots', []))} open times found."
    if name == "list_appointments":
        return f"{len(r.get('appointments', []))} appointments on file."
    if name == "get_home_device_status":
        bad = [d["device"].replace("Bluetooth ", "") for d in r.get("devices", []) if d.get("connection") != "ok"]
        return f"{', '.join(bad).capitalize()} not syncing." if bad else "All devices syncing."
    if name == "submit_refill_request":
        return "Sent for provider review."
    if name == "book_appointment":
        return "Booked."
    if name == "cancel_appointment":
        return "Cancelled."
    if name == "handoff_to_staff":
        return "Summary sent to the team."
    if name == "list_prescriptions":
        n = len(r.get("prescriptions", []))
        return f"{n} prescription{'s' if n != 1 else ''} on file."
    if name == "get_billing_statement":
        n = len(r.get("statements", []))
        return f"{n} open statement{'s' if n != 1 else ''}."
    return "Done."


# ---------- cards ----------

def _card(kind: str, title: str, ic: str, body: str) -> str:
    return f'<div class="clara-card {kind}"><h4>{icon(ic)}{escape(title)}</h4>{body}</div>'


def slot_picker(result: dict) -> str:
    buttons = ""
    for s in result.get("slots", [])[:3]:
        when = _when(s["start_time"])
        reply = f"I'll take {when.replace(' · ', ' at ')} with {s['provider_name']}"
        buttons += (
            f'<button type="button" class="clara-slot" data-clara-prompt="{escape(reply, quote=True)}">'
            f'{escape(when)}<small>{escape(s["provider_name"])} · {escape(s["location"])}</small></button>'
        )
    if not buttons:
        return ""
    return _card("slots", "Open times", "calendar", f'<div class="clara-slots">{buttons}</div>')


def _appointment(appt_id: str, session: dict | None = None) -> dict | None:
    return get_store(session).appointments().get((appt_id or "").strip().upper())


def readback_cancel(event: dict, session: dict | None = None) -> str:
    args, result = event.get("input") or {}, event.get("result") or {}
    a = _appointment(args.get("appointment_id"), session)
    rows = ""
    if a:
        rows = (f"<dt>Visit</dt><dd>{escape(a['provider_name'])} · {escape(a['specialty'])}</dd>"
                f"<dt>When</dt><dd>{_when(a['start_time'])}</dd><dt>Where</dt><dd>{escape(a['location'])}</dd>")
    if result.get("requires_acknowledgement"):
        rows += (f'<dt>Late fee</dt><dd><span class="fee">${LATE_CANCEL_FEE_USD:.2f} '
                 f'(less than {LATE_CANCEL_HOURS} hours away)</span></dd>')
    actions = (
        '<div class="row-actions">'
        f'<button type="button" class="svh-btn primary" data-clara-prompt="Yes, I accept the {LATE_CANCEL_FEE_TEXT} fee. Please cancel it.">Confirm cancellation</button>'
        '<button type="button" class="svh-btn ghost" data-clara-prompt="Never mind, keep my appointment.">Keep it</button></div>'
    )
    return _card("readback", "Before I cancel", "calendar", f'<dl class="clara-kv">{rows}</dl>{actions}')


def readback_from_list(result: dict, reply: str) -> str:
    """Before any cancel: the appointment Clara is asking about, with the late fee if it applies.

    Shown whenever Clara lists appointments and asks a question, so the fee is on screen before
    anything changes, whether or not her text mentions it.
    """
    now = datetime.datetime.now()
    upcoming = [a for a in result.get("appointments", []) if a.get("status") == "scheduled"]
    named = [a for a in upcoming if a.get("provider_name") and a["provider_name"] in reply]
    picks = named or upcoming[:1]
    out = ""
    for a in picks[:2]:
        try:
            hours = (datetime.datetime.fromisoformat(a["start_time"]) - now).total_seconds() / 3600
        except (TypeError, ValueError):
            hours = 999
        fee = (f'<dt>Late fee</dt><dd><span class="fee">${LATE_CANCEL_FEE_USD:.2f} if cancelled now (less than '
               f'{LATE_CANCEL_HOURS} hours away)</span></dd>'
               if 0 < hours < LATE_CANCEL_HOURS else
               f'<dt>Late fee</dt><dd>None (more than {LATE_CANCEL_HOURS} hours away)</dd>')
        rows = (f"<dt>Visit</dt><dd>{escape(a['provider_name'])} · {escape(a['specialty'])}</dd>"
                f"<dt>When</dt><dd>{_when(a['start_time'])}</dd><dt>Where</dt><dd>{escape(a['location'])}</dd>{fee}"
                f'<dt>ID</dt><dd class="record-id">{escape(a["id"])}</dd>')
        out += _card("readback", "Your appointment", "calendar", f'<dl class="clara-kv">{rows}</dl>')
    return out


def receipt(event: dict) -> str:
    name, args, r = event["name"], event.get("input") or {}, event.get("result") or {}
    if name == "book_appointment":
        a = r.get("appointment", {})
        body = (f'<dl class="clara-kv"><dt>Visit</dt><dd>{escape(a.get("provider_name", ""))} · {escape(a.get("specialty", ""))}</dd>'
                f'<dt>When</dt><dd>{_when(a.get("start_time"))}</dd><dt>Where</dt><dd>{escape(a.get("location", ""))}</dd></dl>'
                f'<p class="muted" style="margin-top:8px">{escape(r.get("instructions", ""))}</p>'
                f'<p class="record-id">{escape(a.get("id", ""))}</p>')
        return _card("receipt", "Booked", "check", body)
    if name == "cancel_appointment":
        fee = r.get("late_cancellation_fee_usd") or 0
        fee_row = f'<dt>Late fee</dt><dd><span class="fee">${fee:.2f}</span></dd>' if fee else ""
        body = f'<dl class="clara-kv"><dt>Status</dt><dd>Cancelled</dd>{fee_row}</dl><p class="record-id">{escape(r.get("appointment_id", ""))}</p>'
        return _card("receipt", "Cancelled", "check", body)
    if name == "submit_refill_request":
        body = (f'<p><b>{escape(r.get("medication", args.get("medication", "")))}</b></p>'
                '<p class="muted">Pending provider review. This is a request, not an approval.</p>'
                f'<p class="record-id">{escape(r.get("request_id", ""))}</p>')
        return _card("receipt", "Refill request sent", "check", body)
    return ""


def rx_picker(result: dict) -> str:
    """One tap per medication: each button sends the refill request for that medication."""
    buttons = ""
    for rx in result.get("prescriptions", []):
        if rx.get("controlled"):
            note = "Your doctor's office handles this one"
        elif rx.get("refills_remaining", 0) > 0:
            n = rx["refills_remaining"]
            note = f"{rx.get('prescriber', '')} · {n} refill{'s' if n != 1 else ''} left"
        else:
            note = f"{rx.get('prescriber', '')} · no refills left, needs review"
        prompt = f"Please refill my {rx['medication']}."
        buttons += (f'<button type="button" class="clara-slot" data-clara-prompt="{escape(prompt, quote=True)}">'
                    f'{escape(rx["medication"])}<small>{escape(note)}</small></button>')
    if not buttons:
        return ""
    return _card("slots", "Which one should I send?", "pill", f'<div class="clara-slots">{buttons}</div>')


def device_card(result: dict) -> str:
    """The patient's devices: connection and last sync. Readings are shown as recorded, never interpreted."""
    rows = f'<dt>Program</dt><dd>{escape(result.get("program", ""))}</dd>'
    for d in result.get("devices", []):
        rd = d.get("last_reading") or {}
        if "systolic" in rd:
            value = f'{rd["systolic"]}/{rd["diastolic"]}'
        else:
            value = f'{rd.get("weight_lb", "–")} lb ({rd.get("change_2_days_lb", 0):+} lb in 2 days)'
        status = ("Syncing" if d.get("connection") == "ok"
                  else f"Not syncing: last reading {d.get('days_since_sync', '?')} days ago")
        name = d.get("device", "").replace("Bluetooth ", "").capitalize()
        rows += f'<dt>{escape(name)}</dt><dd>{escape(status)}<br><small>Last: {escape(value)} · {_when(rd.get("taken"))}</small></dd>'
        if d.get("flagged"):
            rows += '<dt></dt><dd><span class="fee">Outside your alert range: a nurse will call you today</span></dd>'
    return _card("readback", "Your home monitoring devices", "heart", f'<dl class="clara-kv">{rows}</dl>')


def bill_card(result: dict) -> str:
    """How the balance adds up: charges, insurance, copay and deductible. Explain only, no payment."""
    out = ""
    for st in result.get("statements", [])[:1]:
        rows = "".join(f"<dt>{escape(c['type'])}</dt><dd>${c['amount']:,.2f}</dd>" for c in st.get("charges", []))
        pr = st.get("patient_responsibility", {})
        rows += (f"<dt>Insurance paid</dt><dd>−${st.get('insurance_paid', 0):,.2f}</dd>"
                 f"<dt>Your copay</dt><dd>${pr.get('copay', 0):,.2f}</dd><dt>Toward your deductible</dt><dd>${pr.get('deductible', 0):,.2f}</dd>"
                 f"<dt><b>Balance due</b></dt><dd><b>${st.get('balance_due', 0):,.2f}</b> by {escape(st.get('due_date', ''))}</dd>")
        plan = ('<div class="row-actions"><button type="button" class="svh-btn ghost" '
                'data-clara-prompt="Can I set up a payment plan?">Ask about a payment plan</button></div>'
                if st.get("payment_plan_eligible") else "")
        out += _card("readback", f"Statement · visit {st.get('visit_date', '')} with {st.get('provider_name', '')}", "dollar",
                     f'<dl class="clara-kv">{rows}</dl><p class="muted" style="margin-top:8px">Clara never takes card details. '
                     f'Pay in MySierra or with our billing team.</p>{plan}<p class="record-id">{escape(st.get("statement_id", ""))}</p>')
    return out


def quick_replies(options: list[str]) -> str:
    """One-tap answers to Clara's last question. Each button sends its label as the patient's reply."""
    buttons = "".join(f'<button type="button" class="clara-quick-btn" data-clara-prompt="{escape(o, quote=True)}">{escape(o)}</button>'
                      for o in options)
    return f'<div class="clara-quick" role="group" aria-label="Quick replies">{buttons}</div>'


def card_removed_notice() -> str:
    return _card("route", "Card number removed", "lock",
                 "<p>For your security, Clara removed the card number from this chat. It was never sent or stored. "
                 "Pay in MySierra or with our billing team.</p>")


def explain_route(event: dict) -> str:
    r = event.get("result") or {}
    name = event["name"]
    if name == "book_appointment" and r.get("requires_referral"):
        who = _provider_name((event.get("input") or {}).get("provider_id")) or "This specialist"
        body = (f"<p>{escape(who)} needs a referral for new patients, and there isn't one on file.</p>"
                '<div class="row-actions">'
                '<button type="button" class="svh-btn primary" data-clara-prompt="I\'ll see my primary care provider first to get a referral.">See my primary care provider</button>'
                '<button type="button" class="svh-btn ghost" data-clara-prompt="Please connect me with scheduling.">Talk to scheduling</button></div>')
        return _card("route", "A referral comes first", "route", body)
    if name == "submit_refill_request" and "controlled substance" in (r.get("error") or ""):
        body = ("<p>This medication is a controlled substance, so the prescriber's office handles refills directly.</p>"
                '<div class="row-actions"><button type="button" class="svh-btn primary" '
                'data-clara-prompt="Please have the provider office follow up with me.">Have the office follow up</button></div>')
        return _card("route", "Your doctor's office handles this one", "route", body)
    return ""


def handoff(event: dict) -> str:
    args, r = event.get("input") or {}, event.get("result") or {}
    label, ic = QUEUE_LABELS.get(r.get("queue") or args.get("queue"), ("Our team", "headset"))
    body = (f'<p class="muted">What they\'ll see, so you won\'t have to repeat yourself:</p>'
            f'<p style="margin:6px 0 8px">“{escape(args.get("summary", ""))}”</p>'
            f'<p><b>{escape(r.get("message", "").split(". They will")[0])}.</b></p>'
            f'<p class="record-id">{escape(r.get("handoff_id", ""))}</p>')
    return _card("handoff", f"Handed to {label}", ic, body)


def emergency_alert() -> str:
    return (
        '<div class="clara-alert" role="alert">'
        f'<h4>{icon("alert")} If this is an emergency, get help now</h4>'
        "<p>Call 911 or go to the nearest emergency room. For thoughts of suicide or self-harm, call or text 988.</p>"
        '<div class="row-actions"><a href="tel:911">911<small>Emergency</small></a><a href="tel:988">988<small>Crisis line</small></a></div>'
        "</div>"
    )


def cards_for_turn(events: list[dict], emergency: bool, reply: str = "", session: dict | None = None) -> list[str]:
    """The cards to show after Clara's reply. An emergency shows the alert banner and nothing else."""
    if emergency:
        return [emergency_alert()]
    results = [e for e in events if e["type"] == "tool_result"]
    out: list[str] = []
    booked = any(e["name"] == "book_appointment" and e["result"].get("success") for e in results)
    handed_off = any(e["name"] == "handoff_to_staff" and e["result"].get("success") for e in results)
    last_slots = next((e for e in reversed(results) if e["name"] == "get_availability" and e["result"].get("success")), None)
    for e in results:
        r = e["result"]
        if e["name"] in ("book_appointment", "cancel_appointment", "submit_refill_request") and r.get("success"):
            out.append(receipt(e))
        elif e["name"] == "cancel_appointment" and r.get("requires_acknowledgement"):
            out.append(readback_cancel(e, session))
        elif e["name"] == "book_appointment" and r.get("requires_referral") and not booked and not handed_off:
            out.append(explain_route(e))
        elif e["name"] == "submit_refill_request" and not r.get("success") and not handed_off:
            card = explain_route(e)
            if card:
                out.append(card)
        elif e["name"] == "handoff_to_staff" and r.get("success"):
            out.append(handoff(e))
        elif e["name"] == "list_prescriptions" and r.get("success") and not any(
                x["name"] == "submit_refill_request" for x in results):
            out.append(rx_picker(r))
        elif e["name"] == "get_home_device_status" and r.get("success"):
            out.append(device_card(r))
        elif e["name"] == "get_billing_statement" and r.get("success") and r.get("statements"):
            out.append(bill_card(r))
    wrote = any(e["name"] in WRITE_TOOLS and e["result"].get("success") for e in results)
    listed = next((e for e in reversed(results) if e["name"] == "list_appointments" and e["result"].get("success")), None)
    if listed and not wrote and reply.rstrip().endswith("?") and not any("readback" in c for c in out):
        out.append(readback_from_list(listed["result"], reply))
    if last_slots and not booked:
        out.insert(0, slot_picker(last_slots["result"]))
    return [c for c in out if c]


def verified_chip(session: dict) -> str:
    patient = get_store(session).patients().get(session.get("patient_id")) if session.get("patient_id") else None
    presenter = '<span class="svh-pres-only svh-tag">Presenter view</span>'
    channel = session.get("channel", "web")
    if patient:
        name = f"{patient['first_name']} {patient['last_name'][:1]}."
        how = "Signed in to MySierra as" if channel == "portal" else "Verified as"
        return f'<div class="clara-verified yes">{icon("lock")}{how} {escape(name)}{presenter}</div>'
    return f'<div class="clara-verified no">{icon("lock")}Not yet verified{presenter}</div>'
