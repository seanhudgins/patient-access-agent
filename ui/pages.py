"""Inner pages for every header, utility and footer link. Shown by the hash router in clara.js
(#/find-care and so on); the header, footer, ribbon and Clara drawer stay on screen.

Facts come from knowledge_base.py so the pages and Clara never disagree. Pages for systems
outside the demo (portal, bill pay, careers) say so plainly and offer Clara instead.
"""
from html import escape

from knowledge_base import KNOWLEDGE_BASE as KB
from ui.icons import icon

ROUTES = {
    "find-care": "Find care",
    "patients-visitors": "Patients & visitors",
    "providers": "For providers",
    "portal": "Patient portal",
    "pay-bill": "Pay a bill",
    "insurance": "Insurance we accept",
    "privacy": "Notice of privacy practices",
    "careers": "Careers",
}


def _ask(label: str, prompt: str, primary: bool = True) -> str:
    cls = "primary" if primary else "ghost"
    return f'<button type="button" class="svh-btn {cls}" data-clara-prompt="{escape(prompt, quote=True)}">{escape(label)}</button>'


def _page(slug: str, eyebrow: str, lede: str, body: str) -> str:
    return f"""
<main class="svh-page" data-route="{slug}" hidden>
  <section class="svh-section"><div class="svh-wrap">
    <nav class="svh-crumbs" aria-label="Breadcrumb"><a href="#/">Home</a> <span aria-hidden="true">›</span> {escape(ROUTES[slug])}</nav>
    <p class="svh-eyebrow">{escape(eyebrow)}</p>
    <h1 class="svh-page-title" tabindex="-1">{escape(ROUTES[slug])}</h1>
    <p class="svh-lede">{escape(lede)}</p>
    <div class="svh-page-body">{body}</div>
  </div></section>
</main>"""


def _panel(title: str, text: str, actions: str = "", ic: str | None = None) -> str:
    head = f"{icon(ic)} " if ic else ""
    return f'<article class="svh-card svh-panel"><div class="svh-card-body"><h3>{head}{escape(title)}</h3><p>{escape(text)}</p>{f"<div class=svh-actions>{actions}</div>" if actions else ""}</div></article>'


def _demo_note(what: str) -> str:
    return f'<p class="svh-demo-note">{icon("eye")} {escape(what)} isn\'t part of this demo. Clara can help with the same tasks.</p>'


def pages_html() -> str:
    find_care = "".join([
        _panel("Book a visit", "Primary care, orthopedics, cardiology and dermatology, in person or by video for most providers. "
               + KB["appointments"].split(". ")[1] + ".", _ask("Book with Clara", "I'd like to book an appointment"), "calendar"),
        _panel("Specialist referrals", "Orthopedics and Cardiology see new patients by referral from a primary care provider. "
               "Clara checks this before booking.", _ask("Ask about seeing a specialist", "I'd like to see a specialist", False), "route"),
        _panel("Talk to a nurse", "Symptoms or medication questions go to our nurse line. A registered nurse calls back within 2 hours during clinic hours.",
               _ask("Ask for a nurse callback", "I have a question for a nurse.", False), "nurse"),
        _panel("Emergencies", KB["emergencies"].replace(" Clara never queues an emergency.", ""), '<a class="svh-btn ghost" href="tel:911">Call 911</a>', "siren"),
        _panel("Find a doctor or location", "Search our providers by specialty, location and language, or see each location's hours, services and parking.",
               '<a class="svh-btn ghost" href="#/doctors">Find a doctor</a> <a class="svh-btn ghost" href="#/locations">Locations</a> '
               '<a class="svh-btn ghost" href="#/care-now">I need care now</a>', "map-pin"),
    ])
    patients = "".join([
        _panel("Hours", KB["hours"], _ask("Ask about hours", "What are your hours?", False), "calendar"),
        _panel("Parking", KB["parking"], _ask("Parking at Midtown", "Where do I park at the Midtown Clinic?", False), "map-pin"),
        _panel("Preparing for your visit", KB["visit_preparation"], "", "check"),
        _panel("Prescription refills", KB["prescription_refills"], _ask("Request a refill", "I'd like to refill a prescription", False), "pill"),
    ])
    providers = "".join([
        _panel("Refer a patient", "Referring offices can send referrals to Sierra Valley Patient Access at 555-301-4000. "
               "Orthopedics and Cardiology need a referral for new patients.", '<a class="svh-btn ghost" href="tel:555-301-4000">Call Patient Access</a>', "building"),
        _panel("Our locations", KB["locations"], '<a class="svh-btn ghost" href="#locations">See locations</a>', "map-pin"),
    ]) + _demo_note("A provider portal")
    portal = _demo_note("The MySierra patient portal") + _panel(
        "Try Clara inside the portal",
        "Once you're signed in, Clara knows who you are and won't ask again. For this demo, you sign in by telling Clara your name and date of birth.",
        '<button type="button" class="svh-btn primary" data-channel="portal">Sign in to MySierra (demo)</button>', "user") + "".join([
        _panel("Trouble signing in?", KB["patient_portal"].split("Password reset: ")[1], _ask("I can't log in", "I can't log in to the patient portal."), "lock"),
        _panel("What the portal does", KB["patient_portal"].split(". Password")[0] + ".", "", "user"),
    ])
    pay = _demo_note("Online bill pay") + "".join([
        _panel("Statements and payment plans", KB["billing"].split(" Clara does not")[0], "", "card"),
        _panel("A question about a charge?", "Billing disputes and charge corrections go to our billing team. Clara can pass your details along so you don't have to repeat them.",
               _ask("Ask about a charge", "I have a question about a charge on my bill"), "dollar"),
    ])
    insurance = "".join([
        _panel("Plans we're in network with", KB["insurance"].split(". HMO")[0] + ".", "", "check"),
        _panel("Before your visit", "HMO members may need a referral for specialists. " + KB["insurance"].split("referral for specialists. ")[1],
               _ask("Ask about my coverage", "Is my insurance accepted?", False), "question"),
    ])
    privacy = _demo_note("A full privacy notice") + _panel(
        "This is a demo page",
        "Sierra Valley Health is fictional and every patient record in this demo is synthetic. A real health system would publish its "
        "HIPAA Notice of Privacy Practices here: how health information is used and shared, and your rights to see and correct it.", "", "lock")
    careers = _demo_note("A careers site") + _panel(
        "Work with us", "Sierra Valley Health is fictional, so there are no open roles. This page exists so every link on the site goes somewhere.",
        '<a class="svh-btn ghost" href="#/">Back to home</a>', "building")
    return "".join([
        _page("find-care", "Patients", "Start here to book, see a specialist, or reach a nurse.", f'<div class="svh-panels">{find_care}</div>'),
        _page("patients-visitors", "Plan your visit", "Hours, parking, and how to get ready for your visit.", f'<div class="svh-panels">{patients}</div>'),
        _page("providers", "Clinicians", "Referrals and contacts for clinicians outside Sierra Valley Health.", f'<div class="svh-panels">{providers}</div>'),
        _page("portal", "MySierra", "MySierra keeps your visits, results and messages in one place.", f'<div class="svh-panels">{portal}</div>'),
        _page("pay-bill", "Billing", "Statements, payment plans, and help with a charge.", f'<div class="svh-panels">{pay}</div>'),
        _page("insurance", "Billing", "Sierra Valley Health works with most major plans in the region.", f'<div class="svh-panels">{insurance}</div>'),
        _page("privacy", "About", "How a health system protects your information.", f'<div class="svh-panels">{privacy}</div>'),
        _page("careers", "About", "Join the team.", f'<div class="svh-panels">{careers}</div>'),
    ])
