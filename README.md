# Sierra Valley Health — Patient Access Agent

Clara is a first-line AI agent for the Patient Access Center at Sierra Valley Health, a fictional regional health system. She books, reschedules and cancels appointments, takes prescription refill requests, and answers general questions (hours, locations, parking, visit prep, insurance, portal password reset). Everything else, including symptoms, test results, billing disputes and anything she can't resolve, goes to staff with a short summary. Emergencies are handled immediately, never queued.

I built it to learn the Claude API and agent design: tool use, guardrails enforced in code, and clean handoffs to people. Built with the Anthropic Claude API and Gradio. Tools and data are mocked: in memory, or in a Google Sheet so you can watch records change during a demo. The design write-up is in [DESIGN.md](DESIGN.md).

> **Synthetic data only.** No real patient information. Not HIPAA-compliant as built; see *Healthcare considerations* and *Production readiness* in `DESIGN.md`.

## Run it

**1. Install dependencies** (Python 3.14, [uv](https://docs.astral.sh/uv/))

```bash
uv sync
```

**2. Store your API key** in the OS keychain (macOS Keychain or Windows Credential Manager), not in a file.
It prompts for the key, so it never lands in your shell history:

```bash
uv run keyring set patient-access anthropic
```

No keychain (for example in CI)? Set `ANTHROPIC_API_KEY` as an environment variable instead; it's only used
when the keychain has no entry.

**Optional: create `.env`** in the project root for non-secret settings:

```
# Where data lives: mock (default) | sheets | salesforce
DATA_BACKEND=mock
```

**3. Start the demo**

```bash
uv run start_demo.py
```

Open http://localhost:7860. With `DATA_BACKEND=sheets`, this also resets the Google Sheet to fresh demo data first.

---

## Demo patients

Identity is verified by first name, last name and date of birth.

| Patient | Date of birth | Primary care | Notes |
|---|---|---|---|
| Maria Lopez | 1984-03-12 | Dr. Chen | Lisinopril, atorvastatin. Appointment tomorrow at 8:00 AM (late-cancellation fee applies). |
| James Okafor | 1971-11-02 | Dr. Patel | Metformin. Has an orthopedics referral on file. |
| Alex Kim | 1995-07-28 | Dr. Chen | No medications, no referral. |
| Sarah Bellum | 1985-06-14 | Dr. Patel | Levothyroxine, plus alprazolam (controlled). |

| Provider | Specialty | Location | Rule |
|---|---|---|---|
| Dr. Chen | Primary Care | Midtown Clinic | |
| Dr. Patel | Primary Care | Eastside Clinic | |
| Dr. Reyes | Orthopedics | Midtown Clinic | New patients need a referral |
| Dr. Reed | Cardiology | Heart & Vascular Center | New patients need a referral |
| Dr. Shah | Dermatology | Midtown Clinic | |

Open slots are generated for the next two weeks, relative to today, so the demo never goes stale.

## Four core behaviors

| Behavior | Try this | What happens |
|---|---|---|
| **Multi-turn collection** | `I'd like to book an appointment` | Clara collects the reason, specialty, timing and visit type, verifies name + DOB, offers up to three open slots, and books only after you confirm. |
| **Tool use** | `Refill my lisinopril` (as Maria Lopez) | `verify_patient`, then `submit_refill_request`. The request goes to Dr. Chen for review; it is never an approval. |
| **Clarifying question** | `I need to see someone about my knee` / `Can you refill my meds?` | Clara asks whether you want primary care or orthopedics / which medication, one question at a time. As Alex Kim, choosing orthopedics ends in the referral rule: Clara offers a primary care visit or a handoff to scheduling. |
| **Handoff** | `I've had a headache for 3 days and my BP meds aren't working` | No clinical advice. Clara verifies you (or takes a name and callback number) and calls `handoff_to_staff` to the nurse line with a 2-3 sentence summary. |

Also worth trying:

- **Emergency:** `My dad has chest pain and his arm is numb`. Clara directs you to 911 immediately and doesn't queue it. A keyword check in code adds the 911 notice even if the model forgets.
- **Late-cancellation fee:** as Maria, `cancel my appointment tomorrow`. The tool refuses until you accept the $50 fee.
- **Controlled substance:** as Sarah, `refill my alprazolam`. Refused in code and routed to the provider's office.
- **Billing dispute:** `I was charged twice for my last visit`. Handed off to billing.
- **Failed verification:** give a wrong date of birth three times. Clara locks verification and hands off to Patient Access.
- **General questions:** `Where do I park at Midtown?`, `What insurance do you take?`, `I forgot my portal password`.

---

## Project structure

```
start_demo.py            # One command: reset the sheet (if using Sheets) and start the app
main.py                  # Launches the Gradio app on port 7860
ui.py                    # Chat UI: emergency banner, quick actions, typing indicator, per-tab session
agent.py                 # System prompt + tool-use loop (Claude API), emergency backstop
tools.py                 # 7 tools, their JSON schemas, and the code-enforced guardrails
knowledge_base.py        # Sierra Valley Health policies, injected into the system prompt
data_store.py            # Data backends (in-memory or Google Sheets) behind one interface
mock_data.py             # Synthetic patients, providers, appointments, prescriptions, slots
seed_sheet.py            # Resets the Google Sheet to fresh demo data
salesforce_client.py     # Optional: staff handoffs as Salesforce Cases
credentials.py           # Reads secrets from the OS keychain (env var fallback)
salesforce/AssistantActionService.cls  # Apex REST class for case creation
DESIGN.md                # Architecture and design decisions
```

## Data backends

| `DATA_BACKEND` | Data | Staff handoffs | Notes |
|---|---|---|---|
| `mock` (default) | In memory | In memory | No setup. Resets when the app restarts. |
| `sheets` | Google Sheet | Google Sheet | Every booking, cancellation, refill request and handoff appears as a row, live. |
| `salesforce` | In memory | Salesforce Cases | For a contact-center-style queue. Needs an org (below). |

### Google Sheets setup

1. In Google Cloud, enable the **Google Sheets API** and create a **service account** (no project roles needed). Download its JSON key as `service_account.json` in the project root. It's gitignored.
2. Create a Google Sheet and share it with the service account's `client_email` as an **Editor**.
3. In `.env`: `DATA_BACKEND=sheets`, `GOOGLE_SHEET_ID=<the ID from the sheet's URL>`, and optionally `GOOGLE_SERVICE_ACCOUNT_FILE` if the key lives elsewhere.
4. `uv run start_demo.py` creates the tabs (Patients, Providers, Appointments, Slots, Prescriptions, RefillRequests, Handoffs) and seeds them.

### Salesforce setup (optional)

1. Create a Connected App with OAuth scope `api` and **Client Credentials Flow** (Run As an integration user). Store the consumer secret with `uv run keyring set patient-access salesforce-client-secret`, and put `SALESFORCE_CLIENT_ID` and `SALESFORCE_INSTANCE_URL` in `.env`.
2. Deploy `salesforce/AssistantActionService.cls` (Developer Console → File → New → Apex Class). Give the integration user **Create** on Case and access to the class.
3. Set `DATA_BACKEND=salesforce`. Set `SALESFORCE_CASE_ENDPOINT` only if you deploy the class under a different URL mapping.

**Model:** `claude-opus-4-6`. See *Model choice* in `DESIGN.md`.
