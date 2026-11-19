# Architecture review: April 2026 build vs. what's available in November 2026

## The build today
- **UI:** Gradio 6 app. Hand-written homepage HTML/JS sits in `gr.HTML`, and the Clara drawer is a `gr.Chatbot`.
- **Agent:** a hand-written tool loop on the Messages API (`agent.py`), 9 local Python tools (`tools.py`), and a system prompt with the knowledge base inlined. Nothing streams. The model was `claude-opus-4-6`.
- **Data:** in-memory mock data (now one copy per browser tab) or Google Sheets as a visible system of record. Handoffs can also go to Salesforce.
- **Guardrails:** split across the prompt, tool-side rules (verification, referral, controlled substances, late-fee disclosure), and deterministic code (the emergency regex, card redaction).

The core design still holds up: a single agent with narrow, rule-enforcing tools, and safety checks in code rather than only in the prompt. That's also what commercial patient-access agents emphasize. The changes worth making are mostly underneath that design.

## What changed since April 2026
- **Models:** Opus 4.7, 4.8, 5 and 5.5; Sonnet 5 and 5.5; Haiku 5.5; Fable 5 and 5.1.
  - Opus 5.5 is cheaper than Opus 4.6 ($4/$20 per M tokens vs $5/$25).
  - Haiku 5.5 costs $0.10/$0.50 per M tokens.
  - On the 5.x models, thinking is always on and **effort** is the control knob.
  - Forced `tool_choice` was removed, and **transcripts must be append-only**: earlier turns can't be edited, thinking blocks included. `agent.py` now complies.
- **Server-side refusal fallback:** `fallbacks: "default"` re-routes a refused request to another model. Now on for Opus and Sonnet 5.5.
- **SDK Tool Runner:** a beta helper in the regular Anthropic SDK that runs the tool loop for you, with per-turn hooks.
- **Strict tool use:** `strict: true` guarantees tool arguments match the schema.
- **Mid-conversation system messages:** you can append per-turn state, such as "the caller is verified as…", without rewriting the system prompt, which keeps the prompt cache valid. Works on Opus 5.5, Sonnet 5.5 and Haiku 5.5.
- **Message threads (beta):** the API holds the conversation, so each request sends only new messages. Smaller requests and a faster first token.
- **Managed Agents:** Anthropic runs the loop and hosts sessions. Also scheduled deployments, outcomes (graded deliverables), and multi-agent workflows.
- **Fast mode:** Opus 5.5 at up to 2.5× output speed, for 2× the price.
- **Evals tooling:** guides for building evals and hill-climbing against them. `evals/model_eval.py` is a first version of that for Clara.

## Recommendations (ranked by payoff for the demo)

### 1. Model: switch to Claude Opus 5.5 at low effort (done)
`evals/model_eval.py` runs Clara through 15 scripted scenarios: booking, the referral rule, late cancel, a controlled refill, the cuff, a flagged reading, emergencies, the bill, a card number, human escalation, a medication question, prompt injection, another patient's data, and Spanish. Claude Opus 5.5 grades each transcript against the scenario's criteria. After fixing two harness bugs (the judge wasn't shown tool results or the policies), the results were:

| Model | Criteria passed | Median / p90 turn | Cost for 15 scenarios | Style (1–5) | Real misses |
|---|---|---|---|---|---|
| **Opus 5.5 (low)** | **44/44** | 3.0 s / 5.5 s | $1.16 | 4.1 | none |
| Opus 4.6 (April build) | 42/44 | 6.4 s / 10.5 s | $1.14 | 3.4 | characterized a BP reading; long bill reply |
| Haiku 5.5 (low) | 42/44 | 2.0 s / 3.5 s | $0.03 | 4.1 | missed "closed Saturday" in Spanish; long bill reply |
| Sonnet 5.5 (low) | 41/44 | 2.4 s / 4.2 s | $0.58 | 4.3 | **said a controlled-substance refill was "sent"**; characterized a reading; long bill reply |

- **Recommendation:** Opus 5.5. It's twice as fast as the April model at the same cost, with the best accuracy and no safety misses.
- **Haiku 5.5:** the credible budget option at about 1/40th the cost. It's also the right model for the safety pre-check in #5.
- **Sonnet 5.5:** its misstatement about a controlled-substance refill rules it out for this agent without prompt work.
- **Caveat:** each scenario was run once per model. Re-run before any final call, and add repeat runs for variance.
- **Common miss:** every model except Opus 5.5 ran past the 3-sentence target on the bill explanation. That's a prompt issue, not a model issue.

### 2. Stream Clara's replies
Every turn currently waits for the full response. With `messages.stream`, the first words appear in about a second, even when the whole turn takes 6–10 seconds. Of all the changes here, this does the most for how fast the demo feels.

### 3. Make the prompt cacheable
`_build_system_prompt` puts the verification status and today's date into the system prompt, so it changes at every step and **nothing gets cached**. Freeze the system prompt and tools. Send the verification status as a mid-conversation system message, and enable prompt caching. Expect lower cost and a faster first token on every tool step. A turn takes 2–4 steps.

### 4. Tighten tools
- Add `strict: true` to every tool schema, with `additionalProperties: false`. Booking and cancel arguments then always match the schema.
- Optionally move the loop to the Tool Runner, which removes about 60 lines. Keep `on_event` as a hook.

### 5. A cheap safety pre-check
The emergency regex misses paraphrases like "my heart is racing and I feel faint". Run a Haiku 5.5 classifier on each patient message, in parallel with the main call (fractions of a cent each). Use it for emergency, self-harm and "wants a human". Keep the regex as the floor. Like the card redaction, this enforces in code what the prompt only asks for.

### 6. Leave Gradio before the next round of UI work
Gradio has caused most of this project's UI bugs:
- CSS that `prefix_css` overrides
- a renderer freeze from its dark-mode class
- the chat input pushed off screen
- generator steps on different threads, which is why per-session data had to go through the session object

The homepage is already plain HTML and JS. A small FastAPI backend with server-sent events for streaming, plus the existing page, would give full control of layout, real streaming, per-session state without workarounds, and a simpler deploy.
- **Cost:** about a day of work.
- **Recommendation:** do it after the demo date, not before.

### 7. Proactive outreach on Managed Agents (optional, for the story)
A scheduled deployment could check each night for cuffs that haven't synced and draft Clara's opening message. The hero bubble would then come from a real job. This is the clearest fit for Managed Agents. The live chat agent itself doesn't need it, because its tools are local Python.

### 8. Voice
Commercial patient-access agents lead with voice. The cheapest credible version is the browser's built-in Web Speech API: speech-to-text for the patient and text-to-speech for Clara's replies, in the existing page. It needs no new vendor or dependency. It's good enough to say "same agent, by phone" in a demo. A real phone line would need a telephony and speech provider.

### 9. Process and Claude Code skills
- **Project skill `/demo-check`:** runs `tests/`, a quick version of the eval, and the browser link check before each demo or publish.
- **CI:** run `tests/` and the eval's safety scenarios on any change to `agent.py`, `tools.py` or `knowledge_base.py`. Prompt edits caused most of the regressions found in this session.
- **Publish step:** `publish/publish.py` already scans the public copy. Add `evals/results/` to its exclude list.

## Not recommended
- **Multi-agent orchestration or model cascades.** The task is narrow, and one model with the right effort level is simpler and keeps one prompt cache.
- **Fable 5.1 for the agent.** Overkill for patient access, with longer turns and higher cost.
- **Moving tools to MCP.** Nothing else consumes them.
