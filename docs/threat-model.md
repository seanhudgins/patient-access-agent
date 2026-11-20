# Threat model

What could go wrong with Clara, who could cause it, and what stops it today. Scope: the demo as built
(synthetic data, one Gradio app, the Claude API, an optional Google Sheet and Salesforce org). "Production"
notes say what a real deployment would add.

## Assets
- Patient records (synthetic here): identity, appointments, prescriptions, device readings, statements.
- The ability to change records: book, cancel (with a fee), request refills, create staff cases.
- Secrets: the Claude API key, the Google service-account key, Salesforce credentials.
- Patient safety: emergency guidance must always reach someone who needs it.

## Actors
| Actor | Can do |
|---|---|
| A caller | Type anything, in any channel, including instructions aimed at the model |
| Someone who can edit the data | In sheets mode, anyone with edit access to the Sheet can put text into records the tools return |
| Anyone on the same network | Reach the demo on port 7860 (deliberate during the demo phase) |
| The model itself | Make mistakes: skip a rule, claim something it didn't do, follow injected text |

## Threats and controls

| Threat | Control today | Test | Production |
|---|---|---|---|
| Caller reads or changes another patient's records | Verified patient ID lives in the server session; tools never take a patient ID from the model; other patients' appointments return "not found" | `tests/test_guardrails.py` | Second identity factor, proxy access, step-up before risky actions |
| Guessing identity | Generic failure message; lockout after 3 failures per conversation | `test_three_failed_verifications_lock` | Per-record and per-client throttling, alerting |
| Direct prompt injection ("ignore your rules") | Rules that matter are in tool code, not the prompt | eval `prompt_injection` | Same, plus a pre-model classifier |
| Indirect injection via records (e.g. a Sheet cell) | Record names are JSON-quoted (with < and > escaped) in a state data block; tool results are data; write tools enforce rules in code | `test_records_names_are_quoted_data_in_the_prompt`, eval `indirect_injection` | Treat every tool result as untrusted; restrict who can edit source systems |
| Model charges a fee without consent | The model can't assert consent; code always adds its own fee sentence naming the appointment and accepts only a plain yes (closed set) in the next message | `tests/test_late_fee.py` (all channels) | Same pattern for every consequential action |
| Missed emergency | Keyword floor (English, Spanish, normalised) before the model runs; when it fires, the code notice (911 and 988) comes first on every exit path and channel. Phrasings it doesn't know rely on the model | `tests/test_safety.py` | Recall-tuned classifier reviewed by clinicians; warm transfer on voice |
| Card numbers in chat | Luhn-valid numbers removed before the model, transcript or screen see them | `test_card_numbers_never_reach_the_model` | PCI scope review; payments only in the portal |
| Script or link injection in the UI | Patient text and Clara's reply are HTML-escaped and markdown links/images in replies are flattened to text; only server-built cards render as HTML | `test_markdown_links_and_images_are_flattened` | CSP header, a UI framework with safe defaults |
| Duplicate writes | Refill dedupe; handoffs never retried after an unconfirmed write | `test_refill_requests_are_deduplicated`, `tests/test_handoff.py` | Idempotency keys on every write |
| Secrets leak | Keychain / Credential Manager, `.env` and key files gitignored, gitleaks in pre-commit and CI | CI | Secret manager, short-lived credentials, key rotation |
| Private details reach the public copy | `publish/publish.py`: tracked files only, written from HEAD (scanned from the index at commit time), DENY patterns incl. generic leaks and terms split across lines, file-name and binary checks, safe targets only | `tests/test_publish.py` (private repo) | n/a |
| Anyone on the LAN uses or resets the demo | Accepted for the demo phase | — | Bind to localhost behind Tailscale serve + ACLs or a proxy with real login, TLS, rate limits, server-side sessions |

## Known gaps (accepted for the demo)
- Booking and normal-cancel confirmation are prompt rules; a code-owned pending-action step is next.
- No server-side audit log or structured trace per turn.
- SMS and voice are simulated in the browser.
