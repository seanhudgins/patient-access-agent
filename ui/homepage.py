"""The Sierra Valley Health homepage, as static HTML.

Every clickable entry point carries data-clara-prompt="..."; clara.js turns a click into a Clara
message (one code path for all of them). Prompts are word for word from "Things You Can Try".
"""
from html import escape

from data_store import get_store
from ui.icons import icon
from ui.directory import directory_html
from ui.pages import pages_html

ASSET = "/gradio_api/file=ui/assets"
PHONE = "555-301-4000"


def _prompt(text: str) -> str:
    return f'data-clara-prompt="{escape(text, quote=True)}"'


def _link(label: str, prompt: str) -> str:
    return f'<button type="button" class="svh-link" {_prompt(prompt)}>{escape(label)}</button>'


def _ribbon() -> str:
    return """
<div class="svh-ribbon" role="note"><div class="svh-wrap">
  <span>Sierra Valley Health is a fictional health system. All patient data is synthetic.</span>
  <span class="svh-ribbon-actions">
    <button type="button" class="svh-link svh-presenter-toggle" data-presenter-toggle aria-pressed="false">Behind the scenes</button>
    <button type="button" class="svh-link" data-demo-reset>Reset demo</button>
  </span>
</div></div>"""


def _utility() -> str:
    return f"""
<div class="svh-utility"><div class="svh-wrap">
  <a href="#/portal" class="svh-hide-sm">{icon("user")}Patient portal</a>
  <button type="button" class="svh-link" style="color:#fff;text-decoration:none" {_prompt("I'd like to book an appointment")}>{icon("calendar")}Request appointment</button>
  <a href="#/pay-bill" class="svh-hide-sm">{icon("card")}Pay a bill</a>
  <label class="svh-hide-sm svh-lang">{icon("globe")}<span class="svh-hidden">Language</span>
    <select aria-label="Language (demo only)"><option>English</option><option>Español</option></select></label>
  <a href="tel:{PHONE}">{icon("phone")}{PHONE}</a>
</div></div>"""


def _header() -> str:
    return f"""
<header class="svh-header"><div class="svh-wrap">
  <a class="svh-brand" href="#/" aria-label="Sierra Valley Health home">
    <img src="{ASSET}/mark.svg" alt="" width="40" height="40">
    <span class="svh-brand-name">Sierra Valley<small>Health</small></span>
  </a>
  <nav class="svh-nav" aria-label="Main">
    <a href="#/find-care">Find care</a>
    <a href="#/locations">Locations</a>
    <a href="#/doctors">Doctors</a>
    <a href="#/patients-visitors">Patients &amp; visitors</a>
    <a href="#/providers">For providers</a>
  </nav>
</div></header>"""


def _hero() -> str:
    chips = "".join(
        f'<button type="button" class="svh-chip" {_prompt(p)}>{escape(label)}</button>'
        for label, p in [
            ("Book an appointment", "I'd like to book an appointment"),
            ("Refill a prescription", "I'd like to refill a prescription"),
            ("Parking at Midtown", "How do I get to the Midtown Clinic, and where do I park?"),
        ]
    )
    return f"""
<section class="svh-hero" id="top"><div class="svh-wrap">
  <div class="svh-hero-card">
    <div class="svh-hero-body">
      <h1>Care close to home. Answers right now.</h1>
      <p class="svh-hero-sub">How can we help you today?</p>
      <form class="svh-ask" data-clara-form role="search" aria-label="Ask Clara">
        <label for="svh-ask-input" class="svh-hidden">Ask Clara</label>
        <input id="svh-ask-input" name="q" type="text" autocomplete="off"
               placeholder="Book a visit, request a refill, or ask a question">
        <button type="submit" class="svh-btn primary">Ask Clara</button>
      </form>
      <div class="svh-chips">{chips}</div>
      <div class="svh-hero-links">
        <a class="svh-link" href="#/doctors">Find a doctor</a>
        <a class="svh-link" href="#/locations">Find a location</a>
        <a class="svh-link" href="#/care-now">I need care now</a>
      </div>
    </div>
    <aside class="svh-outreach" aria-label="Example: Clara reaching out first">
      <p class="svh-outreach-label">Clara reaches out first</p>
      <div class="svh-bubble clara"><b>Clara · Sierra Valley Health</b>Hi Sarah, your scale hasn't sent a reading in 3 days. Want to fix it together? It takes about two minutes.</div>
      <button type="button" class="svh-bubble patient" data-clara-prompt="Hi, I'm Sarah Bellum, born June 14 1985. Clara texted me that my scale stopped sending readings. Can you help?">Yes, let's fix it <small>Reply as Sarah</small></button>
    </aside>
    <span class="svh-photo-credit">Illustration placeholder for the hero photograph</span>
  </div>
</div></section>
<div class="svh-emergency" role="note"><div class="svh-wrap">
  {icon("alert")}<span>Medical emergency? Call <a href="tel:911">911</a>. In crisis? Call or text <a href="tel:988">988</a>.</span>
</div></div>"""


def _intents() -> str:
    cards = [
        ("I need an appointment", "calendar", "svh-ph-a", [
            "I'd like to book an appointment",
            "I need to reschedule an appointment",
            "I need to cancel an appointment",
        ]),
        ("I need help with a prescription", "pill", "svh-ph-b", [
            "I'd like to refill a prescription",
            "I have a question about my medication",
            "My blood pressure cuff isn't syncing",
        ]),
        ("I have a question", "question", "svh-ph-c", [
            "What are your hours?",
            "Where do I park at the Midtown Clinic?",
            "I have a question about my bill",
        ]),
    ]
    html = ""
    for title, ic, ph, prompts in cards:
        links = "".join(f"<li>{_link(p, p)}</li>" for p in prompts)
        html += f"""
  <article class="svh-card">
    <div class="svh-intent-photo {ph}">{icon(ic)}<span>Photo placeholder</span></div>
    <div class="svh-card-body"><h3>{escape(title)}</h3><ul>{links}</ul></div>
  </article>"""
    return f"""
<section class="svh-section white"><div class="svh-wrap">
  <p class="svh-eyebrow">Care starts here</p>
  <h2>What can we help you with?</h2>
  <div class="svh-grid-3">{html}</div>
</div></section>"""


def _meet_clara() -> str:
    resolves = [("calendar", "Appointments: book, move, cancel"), ("pill", "Refill requests to your doctor"),
                ("question", "Hours, locations, parking, insurance")]
    routes = [("nurse", "Nurse line"), ("building", "Provider office"), ("dollar", "Billing"),
              ("headset", "Patient Access"), ("siren", "911 / 988 for emergencies")]
    li = lambda items: "".join(f"<li>{icon(i)}{escape(t)}</li>" for i, t in items)  # noqa: E731
    return f"""
<section class="svh-section svh-meet"><div class="svh-wrap svh-meet-grid">
  <div>
    <div class="svh-meet-intro">
      <img src="{ASSET}/clara-avatar.svg" alt="" width="64" height="64">
      <div>
        <p class="svh-eyebrow" style="color:#B8C4D3;margin:0 0 6px">Meet Clara</p>
        <h2>Your Patient Access assistant, any hour the center is open.</h2>
      </div>
    </div>
    <p>Clara books, reschedules and cancels visits, sends refill requests to your doctor, and answers everyday
       questions. Anything clinical goes to a nurse, with your details already written down.</p>
    <button type="button" class="svh-btn primary" data-clara-open>Chat with Clara</button>
    <ul class="svh-channels" aria-label="Try Clara on another channel">
      <li><button type="button" data-channel="web">{icon("chat")}<b>Web chat</b><span>This website</span></button></li>
      <li><button type="button" data-channel="voice">{icon("phone")}<b>Phone call</b><span>Talk in your browser</span></button></li>
      <li><button type="button" data-channel="sms">{icon("chat")}<b>Text message</b><span>A reminder thread</span></button></li>
      <li><button type="button" data-channel="portal">{icon("user")}<b>MySierra portal</b><span>Signed-in chat</span></button></li>
    </ul>
    <p class="svh-channels-note">Same agent, same safety rules, different doors. Email follow-ups are next.</p>
  </div>
  <div class="svh-scope" aria-label="What Clara resolves and where she routes">
    <div class="svh-scope-col"><h3>Resolves</h3><ul>{li(resolves)}</ul></div>
    <div class="svh-scope-col"><h3>Routes to</h3><ul>{li(routes)}</ul></div>
  </div>
</div></section>"""


def _specialties() -> str:
    tiles = [
        ("stethoscope", "Primary care", "Checkups and everyday care", "I'd like to see someone in Primary Care"),
        ("bone", "Orthopedics", "Joints, bones and sports injuries", "I'd like to see someone in Orthopedics"),
        ("heart", "Cardiology", "Heart and vascular care", "I'd like to see someone in Cardiology"),
        ("sun", "Dermatology", "Skin, hair and nails", "I'd like to see someone in Dermatology"),
        ("video", "Telehealth", "Video visits from home", "Can I do a video visit?"),
        ("flask", "Lab & imaging", "Blood work and scans", "Where can I get lab work done?"),
    ]
    pages = {"Primary care": "#/care/primary-care", "Orthopedics": "#/care/orthopedics",
             "Cardiology": "#/care/cardiology", "Dermatology": "#/care/dermatology"}
    html = "".join(
        (f'<a class="svh-tile" href="{pages[t]}">' if t in pages else f'<button type="button" class="svh-tile" {_prompt(p)}>')
        + f'{icon(ic)}<span>{escape(t)}<small>{escape(s)}</small></span>' + ("</a>" if t in pages else "</button>")
        for ic, t, s, p in tiles
    )
    return f"""
<section class="svh-section"><div class="svh-wrap">
  <p class="svh-eyebrow">Specialties</p>
  <h2>Care for every part of life</h2>
  <div class="svh-spec-grid">{html}</div>
</div></section>"""


def _doctors() -> str:
    cards = ""
    for p in sorted(get_store().providers().values(), key=lambda p: p["id"]):
        last = p["name"].replace("Dr. ", "")
        video = '<span class="svh-badge">Video visits</span>' if p["telehealth"] else '<span class="svh-badge off">Video visits</span>'
        referral = ('<span class="svh-badge warn">Referral required</span>' if p["referral_required_for_new_patients"]
                    else '<span class="svh-badge off">Referral required</span>')
        prompt = f"I'd like to book with {p['name']}"
        cards += f"""
  <article class="svh-card svh-doc">
    <div class="svh-doc-photo" role="img" aria-label="Photo placeholder for {escape(p['name'])}">{escape(last[:1])}</div>
    <div class="svh-card-body">
      <h3>{escape(p['name'])}</h3>
      <span class="svh-doc-meta">{escape(p['specialty'])}</span>
      <span class="svh-doc-meta">{escape(p['location'])}</span>
      <div class="svh-badges">{video}{referral}</div>
      <div class="svh-actions">
        <button type="button" class="svh-btn ghost" {_prompt(prompt)}>Book with {escape(last)}</button>
        <a class="svh-link" href="#/doctors/{p['id']}">View profile</a>
      </div>
    </div>
  </article>"""
    return f"""
<section class="svh-section white" id="doctors"><div class="svh-wrap">
  <p class="svh-eyebrow">Find a doctor</p>
  <h2>Our providers</h2>
  <p class="svh-lede">Some specialists see new patients by referral. Clara checks that for you before booking.</p>
  <div class="svh-doc-grid">{cards}</div>
</div></section>"""


def _story() -> str:
    dots = lambda n: "".join(f'<i class="{"on" if i < n else ""}"></i>' for i in range(5))  # noqa: E731
    return f"""
<section class="svh-section"><div class="svh-wrap">
  <p class="svh-eyebrow">A patient's story</p>
  <h2>Sarah's knee, two ways</h2>
  <p class="svh-lede"><span class="svh-tag">Illustrative scenario</span></p>
  <div class="svh-story">
    <article class="svh-card svh-track">
      <h3>Before</h3>
      <ul class="svh-steps">
        <li><b>Day 1</b>On hold 22 minutes, then told to call the nurse line.</li>
        <li><b>Day 1</b>Explains her knee pain again. Voicemail.</li>
        <li><b>Day 2</b>Callback. Explains it a third time, then gets booked.</li>
      </ul>
      <div class="svh-meter">Effort <span class="svh-dots" aria-label="Effort 5 of 5">{dots(5)}</span> 2 days · 3 retellings</div>
    </article>
    <article class="svh-card svh-track after">
      <h3>With Clara</h3>
      <ul class="svh-steps">
        <li><b>9:02</b>Asks Clara about her knee at 9 pm or 9 am.</li>
        <li><b>9:04</b>Clara verifies her and writes up the details for the nurse.</li>
        <li><b>10:40</b>A nurse calls back, already knowing the story.</li>
      </ul>
      <div class="svh-meter">Effort <span class="svh-dots" aria-label="Effort 1 of 5">{dots(1)}</span> 1 conversation · nurse callback inside 2 hours</div>
    </article>
  </div>
</div></section>"""


def _locations() -> str:
    locs = [
        ("Midtown Clinic", "200 Capitol Avenue", "Primary care, orthopedics, dermatology, lab",
         "Free garage on 2nd Street; validate at the front desk.", "How do I get to the Midtown Clinic, and where do I park?"),
        ("Eastside Clinic", "4150 Folsom Boulevard", "Primary care, lab",
         "Free surface lot in front of the building.", "How do I get to the Eastside Clinic, and where do I park?"),
        ("Heart & Vascular Center", "5 Riverside Drive", "Cardiology",
         "Free parking in Lot B.", "How do I get to the Heart & Vascular Center, and where do I park?"),
    ]
    cards = "".join(f"""
    <article class="svh-card svh-loc"><div class="svh-card-body">
      <h3>{escape(n)}</h3>
      <p>{escape(a)} · {escape(s)}</p>
      <p>Mon–Fri 7:30 am–6:00 pm · {escape(park)}</p>
      <p style="margin-top:10px">{_link("Ask Clara for directions", prompt)} · <a class="svh-link" href="#/locations/{slug}">Location details</a></p>
    </div></article>""" for (n, a, s, park, prompt), slug in zip(locs, ["midtown", "eastside", "heart-vascular"]))
    return f"""
<section class="svh-section white" id="locations"><div class="svh-wrap">
  <p class="svh-eyebrow">Locations</p>
  <h2>Three locations across the valley</h2>
  <div class="svh-loc-grid">
    <div class="svh-map"><img src="{ASSET}/map.svg" alt="Stylized map of Sierra Valley showing Midtown Clinic, Eastside Clinic and the Heart and Vascular Center" width="600" height="400"></div>
    <div class="svh-loc-list">{cards}</div>
  </div>
</div></section>"""


def _footer() -> str:
    return f"""
<footer class="svh-footer"><div class="svh-wrap">
  <div class="svh-footer-grid">
    <div>
      <a class="svh-brand" href="#/"><img src="{ASSET}/mark-white.svg" alt="" width="40" height="40">
        <span class="svh-brand-name">Sierra Valley<small>Health</small></span></a>
      <p style="margin-top:16px">Patient Access Center: <a href="tel:{PHONE}">{PHONE}</a><br>Mon–Fri 7 am–7 pm · Sat 8 am–noon</p>
    </div>
    <div><h4>Patients</h4><ul><li><a href="#doctors">Find a doctor</a></li><li><a href="#locations">Locations</a></li>
      <li>{_link("Request appointment", "I'd like to book an appointment").replace('svh-link', 'svh-link" style="color:#DCE4EE;text-decoration:none')}</li></ul></div>
    <div><h4>Billing</h4><ul><li><a href="#/pay-bill">Pay a bill</a></li><li><a href="#/insurance">Insurance we accept</a></li></ul></div>
    <div><h4>About</h4><ul><li><a href="#/privacy">Notice of privacy practices (demo page)</a></li><li><a href="#/careers">Careers</a></li></ul></div>
  </div>
  <div class="svh-footer-911">
    <span><strong>Medical emergency? Call 911.</strong> In crisis? Call or text 988.</span>
    <span>© 2026 Sierra Valley Health (fictional).</span>
  </div>
</div></footer>"""


def _launcher() -> str:
    return f"""
<button type="button" class="svh-launcher" data-clara-open aria-label="Ask Clara, online">
  <img src="{ASSET}/clara-avatar.svg" alt="" width="40" height="40"><span class="svh-online"></span>Ask Clara
</button>"""


def homepage_html() -> str:
    home = "".join([_hero(), _intents(), _meet_clara(), _specialties(), _doctors(), _story(), _locations()])
    return '<div class="svh">' + "".join([
        _ribbon(), _utility(), _header(),
        f'<main class="svh-page" data-route="home">{home}</main>', pages_html(), directory_html(),
        _footer(), _launcher(),
    ]) + "</div>"


def drawer_head_html() -> str:
    return f"""
<div class="clara-head">
  <img src="{ASSET}/clara-avatar.svg" alt="" width="40" height="40">
  <div class="clara-head-title"><b>Clara</b><span>Sierra Valley Health Patient Access</span></div>
  <button type="button" class="clara-close" data-clara-close aria-label="Close chat">{icon("x")}</button>
</div>
<div class="clara-channel-bar" aria-live="polite">
  <span class="clara-channel-dot" aria-hidden="true"></span>
  <span data-channel-label>Web chat</span>
  <button type="button" class="clara-mic" data-voice-mic aria-pressed="false">{icon("phone")}<span data-mic-label>Tap to talk</span></button>
  <button type="button" class="svh-link clara-channel-exit" data-channel="web">Back to web chat</button>
</div>"""
