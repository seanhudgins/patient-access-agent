"""Directory pages: find a doctor (with filters) and doctor profiles, locations and location detail,
"I need care now", and one page per specialty. Shown by the hash router like the other inner pages.

Every button that talks to Clara sends a generic request that matches its label.
"""
from html import escape

from constants import PATIENT_ACCESS_PHONE
from data_store import get_store
from ui.icons import icon
from ui.site_data import LOCATIONS, PROVIDER_PROFILES, SPECIALTIES

ASSET = "/gradio_api/file=ui/assets"
PHONE = PATIENT_ACCESS_PHONE


def _prompt(text: str) -> str:
    return f'data-clara-prompt="{escape(text, quote=True)}"'


def _shell(route: str, crumbs: list[tuple[str, str]], eyebrow: str, title: str, lede: str, body: str) -> str:
    trail = " ".join(f'<a href="{h}">{escape(t)}</a> <span aria-hidden="true">›</span>' for t, h in crumbs)
    return f"""
<main class="svh-page" data-route="{escape(route, quote=True)}" hidden>
  <section class="svh-section"><div class="svh-wrap">
    <nav class="svh-crumbs" aria-label="Breadcrumb"><a href="#/">Home</a> <span aria-hidden="true">›</span> {trail} {escape(title)}</nav>
    <p class="svh-eyebrow">{escape(eyebrow)}</p>
    <h1 class="svh-page-title" tabindex="-1">{escape(title)}</h1>
    <p class="svh-lede">{escape(lede)}</p>
    <div class="svh-page-body">{body}</div>
  </div></section>
</main>"""


def _providers() -> list[dict]:
    return sorted(get_store().providers().values(), key=lambda p: p["id"])


def _loc_slug(name: str) -> str:
    return next((loc["slug"] for loc in LOCATIONS if loc["name"] == name), "")


def _spec_slug(name: str) -> str:
    return next((slug for slug, s in SPECIALTIES.items() if s["name"] == name), "")


def _badges(p: dict) -> str:
    prof = PROVIDER_PROFILES.get(p["id"], {})
    out = [('<span class="svh-badge">Accepting new patients</span>' if prof.get("accepting")
            else '<span class="svh-badge off">Not accepting new patients</span>')]
    if p["telehealth"]:
        out.append('<span class="svh-badge">Video visits</span>')
    if p["referral_required_for_new_patients"]:
        out.append('<span class="svh-badge warn">Referral required</span>')
    return "".join(out)


def _doctor_card(p: dict) -> str:
    prof = PROVIDER_PROFILES.get(p["id"], {})
    langs = prof.get("languages", ["English"])
    last = p["name"].replace("Dr. ", "")
    data = (f'data-dir-item data-specialty="{escape(p["specialty"], quote=True)}" '
            f'data-location="{escape(p["location"], quote=True)}" data-languages="{escape("|".join(langs), quote=True)}" '
            f'data-video="{str(p["telehealth"]).lower()}" data-accepting="{str(prof.get("accepting", True)).lower()}"')
    return f"""
  <article class="svh-card svh-doc" {data}>
    <div class="svh-doc-photo" role="img" aria-label="Photo placeholder for {escape(p['name'])}">{escape(last[:1])}</div>
    <div class="svh-card-body">
      <h3><a href="#/doctors/{p['id']}">{escape(p['name'])}</a></h3>
      <span class="svh-doc-meta">{escape(prof.get('title', p['specialty']))}</span>
      <span class="svh-doc-meta">{escape(p['location'])} · {escape(', '.join(langs))}</span>
      <div class="svh-badges">{_badges(p)}</div>
      <div class="svh-actions">
        <button type="button" class="svh-btn ghost" {_prompt(f"I'd like to book with {p['name']}")}>Book with {escape(last)}</button>
        <a class="svh-link" href="#/doctors/{p['id']}">View profile</a>
      </div>
    </div>
  </article>"""


def _doctors_page() -> str:
    providers = _providers()
    specs = sorted({p["specialty"] for p in providers})
    locs = sorted({p["location"] for p in providers})
    langs = sorted({lang for p in providers for lang in PROVIDER_PROFILES.get(p["id"], {}).get("languages", ["English"])})
    opt = lambda vals: "".join(f'<option value="{escape(v, quote=True)}">{escape(v)}</option>' for v in vals)  # noqa: E731
    filters = f"""
<form class="svh-filters" data-dir aria-label="Filter doctors" onsubmit="return false">
  <label>Specialty<select data-dir-filter="specialty"><option value="">Any</option>{opt(specs)}</select></label>
  <label>Location<select data-dir-filter="location"><option value="">Any</option>{opt(locs)}</select></label>
  <label>Language<select data-dir-filter="languages"><option value="">Any</option>{opt(langs)}</select></label>
  <label class="svh-check"><input type="checkbox" data-dir-filter="video"> Video visits</label>
  <label class="svh-check"><input type="checkbox" data-dir-filter="accepting"> Accepting new patients</label>
  <p class="svh-dir-count" aria-live="polite" data-dir-count>{len(providers)} doctors</p>
</form>"""
    cards = "".join(_doctor_card(p) for p in providers)
    body = f'{filters}<div class="svh-doc-grid" data-dir-list>{cards}</div><p class="svh-dir-empty" data-dir-empty hidden>No doctors match those filters.</p>'
    return _shell("doctors", [], "Find a doctor", "Find a doctor",
                  "Filter by specialty, location or language. Some specialists see new patients by referral; Clara checks that for you.", body)


def _doctor_profile(p: dict) -> str:
    prof = PROVIDER_PROFILES.get(p["id"], {})
    last = p["name"].replace("Dr. ", "")
    loc_slug = _loc_slug(p["location"])
    spec_slug = _spec_slug(p["specialty"])
    referral = ("New patients need a referral from a primary care provider. Clara checks for one before booking."
                if p["referral_required_for_new_patients"] else "No referral needed.")
    body = f"""
<div class="svh-profile">
  <div class="svh-doc-photo big" role="img" aria-label="Photo placeholder for {escape(p['name'])}">{escape(last[:1])}</div>
  <div>
    <p class="svh-doc-meta">{escape(prof.get('title', ''))}</p>
    <div class="svh-badges">{_badges(p)}</div>
    <p>{escape(prof.get('bio', ''))}</p>
    <dl class="svh-facts">
      <dt>Specialty</dt><dd><a href="#/care/{spec_slug}">{escape(p['specialty'])}</a></dd>
      <dt>Location</dt><dd><a href="#/locations/{loc_slug}">{escape(p['location'])}</a></dd>
      <dt>Languages</dt><dd>{escape(', '.join(prof.get('languages', ['English'])))}</dd>
      <dt>Visit types</dt><dd>In person{' and video' if p['telehealth'] else ''}</dd>
      <dt>New patients</dt><dd>{escape(referral)}</dd>
    </dl>
    <div class="svh-actions">
      <button type="button" class="svh-btn primary" {_prompt(f"I'd like to book with {p['name']}")}>Book with {escape(last)}</button>
      <a class="svh-btn ghost" href="#/doctors">All doctors</a>
    </div>
  </div>
</div>"""
    return _shell(f"doctors/{p['id']}", [("Find a doctor", "#/doctors")], p["specialty"], p["name"], p["location"], body)


def _locations_page() -> str:
    cards = "".join(f"""
  <article class="svh-card svh-loc"><div class="svh-card-body">
    <h3><a href="#/locations/{loc['slug']}">{escape(loc['name'])}</a></h3>
    <p>{escape(loc['address'])} · <a href="tel:{loc['phone']}">{loc['phone']}</a></p>
    <p>{escape(', '.join(loc['services']))}</p>
    <p>{escape(loc['hours'])}</p>
    <a class="svh-link" href="#/locations/{loc['slug']}">Location details</a>
  </div></article>""" for loc in LOCATIONS)
    body = f"""<div class="svh-loc-grid">
  <div class="svh-map"><img src="{ASSET}/map.svg" alt="Stylized map of Sierra Valley showing the three locations" width="600" height="400"></div>
  <div class="svh-loc-list">{cards}</div></div>"""
    return _shell("locations", [], "Locations", "Locations",
                  "Three locations across the valley. Labs are at Midtown and Eastside; imaging is at Midtown.", body)


def _location_page(loc: dict) -> str:
    docs = [p for p in _providers() if p["location"] == loc["name"]]
    doc_links = ", ".join(f'<a href="#/doctors/{p["id"]}">{escape(p["name"])}</a>' for p in docs) or "–"
    body = f"""
<div class="svh-profile">
  <div class="svh-map"><img src="{ASSET}/map.svg" alt="Map showing {escape(loc['name'], quote=True)}" width="600" height="400"></div>
  <div>
    <dl class="svh-facts">
      <dt>Address</dt><dd>{escape(loc['address'])}</dd>
      <dt>Phone</dt><dd><a href="tel:{loc['phone']}">{loc['phone']}</a></dd>
      <dt>Hours</dt><dd>{escape(loc['hours'])}; closed weekends</dd>
      <dt>Services</dt><dd>{escape(', '.join(loc['services']))}</dd>
      <dt>Doctors here</dt><dd>{doc_links}</dd>
      <dt>Parking</dt><dd>{escape(loc['parking'])}</dd>
      <dt>Transit</dt><dd>{escape(loc['transit'])}</dd>
      <dt>Accessibility</dt><dd>{escape(loc['accessible'])}</dd>
    </dl>
    <div class="svh-actions">
      <button type="button" class="svh-btn primary" {_prompt(f"How do I get to the {loc['name']}, and where do I park?")}>Ask Clara for directions</button>
      <button type="button" class="svh-btn ghost" {_prompt(f"I'd like to book an appointment at the {loc['name']}")}>Book a visit here</button>
    </div>
  </div>
</div>"""
    return _shell(f"locations/{loc['slug']}", [("Locations", "#/locations")], "Location", loc["name"], loc["address"], body)


def _care_now_page() -> str:
    options = [
        ("siren", "Emergency", "Chest pain, trouble breathing, stroke signs, severe bleeding, or a severe allergic reaction.",
         '<a class="svh-btn primary danger" href="tel:911">Call 911</a>', "alert"),
        ("heart", "Crisis support", "Thoughts of suicide or self-harm, or an emotional crisis. Free and available 24/7.",
         '<a class="svh-btn primary danger" href="tel:988">Call or text 988</a>', "alert"),
        ("nurse", "Talk to a nurse", "Not sure where to go, or a question about symptoms or medication. A nurse calls back within 2 hours during clinic hours.",
         f'<button type="button" class="svh-btn primary" {_prompt("I have a question for a nurse.")}>Ask for a nurse callback</button>', ""),
        ("calendar", "Same-day visit", "A minor illness or injury that can't wait for a routine appointment.",
         f'<button type="button" class="svh-btn primary" {_prompt("I need a same-day appointment")}>Find a same-day visit</button>', ""),
        ("video", "Video visit", "Many everyday concerns can be handled from home with a primary care or dermatology provider.",
         f'<button type="button" class="svh-btn ghost" {_prompt("Can I do a video visit?")}>Ask about a video visit</button>', ""),
    ]
    cards = "".join(f"""
  <article class="svh-card svh-panel {cls}"><div class="svh-card-body">
    <h3>{icon(ic)} {escape(t)}</h3><p>{escape(d)}</p><div class="svh-actions">{a}</div>
  </div></article>""" for ic, t, d, a, cls in options)
    return _shell("care-now", [], "I need care now", "Get care now",
                  "Start at the top: if it could be an emergency, call 911 first. Clara never handles emergencies.",
                  f'<div class="svh-panels">{cards}</div>')


def _specialty_page(slug: str, s: dict) -> str:
    docs = [p for p in _providers() if p["specialty"] == s["name"]]
    treats = "".join(f"<li>{escape(t)}</li>" for t in s["treats"])
    body = f"""
<div class="svh-panels">
  <article class="svh-card svh-panel"><div class="svh-card-body"><h3>{icon(s['icon'])} What we treat</h3><ul class="svh-list">{treats}</ul>
    <p class="svh-doc-meta">{escape(s['note'])}</p>
    <div class="svh-actions"><button type="button" class="svh-btn primary" {_prompt(f"I'd like to see someone in {s['name']}")}>Book with Clara</button></div>
  </div></article>
</div>
<h2 class="svh-subhead">Our {escape(s['name'].lower())} providers</h2>
<div class="svh-doc-grid">{''.join(_doctor_card(p) for p in docs)}</div>"""
    return _shell(f"care/{slug}", [("Find care", "#/find-care")], "Specialty", s["name"], s["lede"], body)


def directory_html() -> str:
    pages = [_doctors_page(), _locations_page(), _care_now_page()]
    pages += [_doctor_profile(p) for p in _providers()]
    pages += [_location_page(loc) for loc in LOCATIONS]
    pages += [_specialty_page(slug, s) for slug, s in SPECIALTIES.items()]
    return "".join(pages)
