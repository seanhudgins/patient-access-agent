"""Behind the scenes: the presenter-only column that shows what Clara did on each turn.

Decision badge (Answer, Ask, Act, Hand off), tool timeline with timings, the record row Clara
wrote, and guardrail tags. Built from the same events as the patient cards.
"""
import json
from html import escape

from constants import LATE_CANCEL_FEE_TEXT, LATE_CANCEL_HOURS
from ui.cards import QUEUE_LABELS, WRITE_TOOLS

MAX_VERIFY_ATTEMPTS = 3


def _args(d: dict) -> str:
    keep = {k: v for k, v in (d or {}).items() if k not in ("summary",)}
    text = ", ".join(f"{k}={json.dumps(v)}" for k, v in keep.items())
    return text if len(text) <= 70 else text[:67] + "…"


def _outcome(e: dict) -> tuple[str, bool]:
    r = e.get("result") or {}
    if r.get("success"):
        if e["name"] == "get_availability":
            return f"{len(r.get('slots', []))} slots", True
        if e["name"] == "list_appointments":
            return f"{len(r.get('appointments', []))} appts", True
        if e["name"] == "verify_patient":
            return "ok", True
        if e["name"] == "get_home_device_status":
            devs = r.get("devices", [])
            parts = (["flagged reading"] if any(d.get("flagged") for d in devs) else []) + \
                    [f"{d['device'].replace('Bluetooth ', '')} not syncing" for d in devs if d.get("connection") != "ok"]
            return (", ".join(parts) or "all ok"), True
        if e["name"] == "get_billing_statement":
            return f"{len(r.get('statements', []))} statements", True
        if e["name"] == "list_prescriptions":
            return f"{len(r.get('prescriptions', []))} meds", True
        return "written", True
    if r.get("requires_referral"):
        return "refused: no referral", False
    if r.get("requires_acknowledgement"):
        return "held: late fee needs OK", False
    if "controlled substance" in (r.get("error") or ""):
        return "refused: controlled", False
    return "failed", False


def _records(results: list[dict]) -> list[tuple[str, dict]]:
    rows = []
    for e in results:
        r = e["result"]
        if not r.get("success") or e["name"] not in WRITE_TOOLS:
            continue
        if e["name"] == "book_appointment":
            a = r["appointment"]
            rows.append(("Appointments", {"id": a["id"], "provider": a["provider_name"], "start": a["start_time"], "status": a["status"]}))
        elif e["name"] == "cancel_appointment":
            rows.append(("Appointments", {"id": r["appointment_id"], "status": "cancelled", "late_fee": f"${r.get('late_cancellation_fee_usd', 0):.2f}"}))
        elif e["name"] == "submit_refill_request":
            rows.append(("RefillRequests", {"id": r["request_id"], "medication": r["medication"], "status": r["status"]}))
        elif e["name"] == "handoff_to_staff":
            rows.append(("Handoffs", {"id": r["handoff_id"], "queue": r["queue"], "priority": e["input"].get("priority", "normal"), "status": "waiting"}))
    return rows


def _guardrails(results: list[dict], emergency: bool) -> list[str]:
    tags = ["Emergency language detected"] if emergency else []
    for e in results:
        r = e["result"]
        if e["name"] == "verify_patient" and not r.get("success"):
            if r.get("locked"):
                tags.append("Verification locked after 3 tries")
            else:
                used = MAX_VERIFY_ATTEMPTS - r.get("attempts_remaining", MAX_VERIFY_ATTEMPTS)
                tags.append(f"Verification failed {used} of {MAX_VERIFY_ATTEMPTS}")
        summary = (e["input"].get("summary") or "").lower() if e["name"] == "handoff_to_staff" else ""
        if "controlled substance" in (r.get("error") or "") or "controlled" in summary:
            tags.append("Controlled substance, routed")
        if r.get("requires_referral"):
            tags.append("Authorization check: referral required")
        if r.get("requires_acknowledgement"):
            tags.append("Late-cancel fee disclosed")
        if e["name"] == "get_home_device_status" and any(d.get("flagged") for d in r.get("devices", [])):
            tags.append("Flagged reading: not interpreted, sent to a nurse")
        if e["name"] == "get_billing_statement" and r.get("success"):
            tags.append("Explained only: no payment details taken")
        if e["name"] == "handoff_to_staff" and e["input"].get("queue") == "patient_access" and r.get("success"):
            tags.append("Human escalation, no repeat needed")
        if e["name"] == "handoff_to_staff" and e["input"].get("queue") == "nurse_line" and r.get("success"):
            tags.append("Clinical question, no advice given")
    return tags


def _decision(results: list[dict], reply: str, emergency: bool) -> tuple[str, str, str]:
    """(css class, label, one-line reason) for Clara's move this turn."""
    if emergency:
        return "handoff", "Hand off", "Possible emergency: directed to 911 or 988 before anything else"
    for e in results:
        if e["name"] == "handoff_to_staff" and e["result"].get("success"):
            if e["result"].get("queue") == "patient_access":
                return "handoff", "Hand off", "Escalated to a live Patient Access rep, with the whole conversation summarized"
            label = QUEUE_LABELS.get(e["result"].get("queue"), ("staff",))[0]
            return "handoff", "Hand off", f"Out of scope for Clara: routed to {label} with a summary"
    writes = [e for e in results if e["name"] in WRITE_TOOLS and e["result"].get("success")]
    if writes:
        what = {"book_appointment": "booked the visit", "cancel_appointment": "cancelled the visit",
                "submit_refill_request": "sent the refill request"}.get(writes[-1]["name"], "updated the record")
        return "act", "Act", f"Had what it needed and a confirmation, so it {what}"
    if reply.rstrip().endswith("?"):
        if any(e["result"].get("requires_referral") for e in results):
            return "ask", "Ask", "Authorization check: no referral on file, so no wasted specialist visit. Offering the ways forward"
        if any(e["result"].get("requires_acknowledgement") for e in results):
            return "ask", "Ask", f"Late cancellation: needs the patient's own yes to the {LATE_CANCEL_FEE_TEXT} fee (recorded by code, not the model)"
        if results:
            return "ask", "Ask", "Looked things up; needs one choice or detail from the patient"
        return "ask", "Ask", "Request is ambiguous or needs identity: one question at a time"
    if results:
        return "act", "Act", "Looked up the patient's information to answer"
    return "answer", "Answer", "Covered by Sierra Valley policy (hours, locations, parking, insurance)"


def _outcome_line(cls: str, results: list[dict], emergency: bool) -> tuple[str, str]:
    """(kind, text): what the turn achieved, in outcome terms."""
    if emergency:
        return "escalated", "Escalated: patient sent to 911 or 988"
    if cls == "handoff":
        return "handoff", "Handed off with a summary, so the patient won't repeat themselves"
    done = {"book_appointment": "Resolved: visit booked", "cancel_appointment": "Resolved: visit cancelled",
            "submit_refill_request": "Resolved: refill request sent"}
    writes = [e["name"] for e in results if e["name"] in WRITE_TOOLS and e["result"].get("success")]
    if writes:
        return "resolved", done.get(writes[-1], "Resolved")
    if cls == "answer":
        return "resolved", "Resolved: answered from policy, no staff needed"
    if cls == "act":
        return "resolved", "Resolved: answered from the patient's record"
    return "open", "In progress: waiting on the patient"


CHANNEL_LABELS = {"web": "Web chat", "sms": "Text message", "voice": "Phone call", "portal": "MySierra portal"}


def build_turn(message: str, events: list[dict], reply: str, emergency: bool, channel: str = "web") -> dict:
    results = [e for e in events if e["type"] == "tool_result"]
    cls, label, reason = _decision(results, reply, emergency)
    return {
        "ask": message,
        "channel": channel,
        "decision": (cls, label, reason),
        "outcome": _outcome_line(cls, results, emergency),
        "timeline": [(e["name"], _args(e["input"]), *_outcome(e), e.get("ms", 0)) for e in results],
        "records": _records(results),
        "guardrails": _guardrails(results, emergency),
    }


def _render_turn(t: dict, latest: bool) -> str:
    cls, label, reason = t["decision"]
    timeline = "".join(
        f'<li class="{"" if ok else "bad"}">{escape(name)}({escape(args)}) → {escape(out)} <span class="ms">{_ms(ms)}</span></li>'
        for name, args, out, ok, ms in t["timeline"]
    ) or '<li>no tools called</li>'
    records = ""
    for table, row in t["records"]:
        head = "".join(f"<th>{escape(k)}</th>" for k in row)
        cells = "".join(f"<td>{escape(str(v))}</td>" for v in row.values())
        records += f'<table class="pres-row"><caption>{escape(table)}</caption><tr>{head}</tr><tr>{cells}</tr></table>'
    tags = "".join(f'<span class="pres-tag">{escape(g)}</span>' for g in t["guardrails"])
    return f"""
<div class="pres-turn {'latest' if latest else 'old'}">
  <div class="pres-ask"><span class="pres-channel">{escape(CHANNEL_LABELS.get(t.get('channel', 'web'), 'Web chat'))}</span>“{escape(t['ask'])}”</div>
  <div class="pres-decision"><span class="pres-badge {cls}">{escape(label)}</span><span class="pres-reason">{escape(reason)}</span></div>
  <div class="pres-outcome {t['outcome'][0]}">{escape(t['outcome'][1])}</div>
  <h5>Tool calls &amp; latency</h5><ul class="pres-timeline">{timeline}</ul>
  {'<h5>System of record</h5>' + records if records else ''}
  {'<h5>Guardrails</h5><div class="pres-tags">' + tags + '</div>' if tags else ''}
</div>"""


# Always-on rules, each enforced in tools.py, agent.py or the UI. Keep this list true.
TRUST = [
    "Patient records stay locked until identity matches the chart",
    "No clinical advice: symptoms and medication questions go to a nurse",
    "Every message gets a keyword check for emergency language (a floor under the model, not a classifier)",
    "Controlled substances are never refilled by the agent",
    f"Cancelling within {LATE_CANCEL_HOURS} hours is blocked until the patient says yes to the {LATE_CANCEL_FEE_TEXT} fee they were shown",
]


def _ms(v: float) -> str:
    return "<1 ms" if v < 1 else f"{round(v)} ms"


def _summary(turns: list[dict]) -> str:
    """The session at a glance: turns, outcomes, handoffs, average tool latency."""
    ms = [row[4] for t in turns for row in t["timeline"]]
    resolved = sum(t["outcome"][0] == "resolved" for t in turns)
    handoffs = sum(t["outcome"][0] in ("handoff", "escalated") for t in turns)
    guards = sum(len(t["guardrails"]) for t in turns)
    stats = [(len(turns), "Turns"), (resolved, "Resolved"), (handoffs, "Handed off"), (guards, "Guardrails"),
             (_ms(sum(ms) / len(ms)) if ms else "–", "Avg tool call")]
    return '<div class="pres-stats">' + "".join(
        f'<div><b>{escape(str(v))}</b><span>{escape(k)}</span></div>' for v, k in stats) + "</div>"


def render(turns: list[dict]) -> str:
    body = "".join(_render_turn(t, i == len(turns) - 1) for i, t in reversed(list(enumerate(turns))))
    if not body:
        body = '<p class="pres-empty">Start a conversation. Each turn shows Clara\'s decision, the tools she called, the record she wrote and any guardrail that fired.</p>'
    return f'<div class="pres"><div class="pres-title"><b>Behind the scenes</b><span class="svh-tag">Presenter only</span></div><p class="pres-sub">Every agent action: decisions, tool calls, records written, guardrails and latency.</p><ul class="pres-trust">{"".join(f"<li>{escape(x)}</li>" for x in TRUST)}</ul>{_summary(turns) if turns else ""}{body}</div>'
