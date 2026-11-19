"""The Gradio app: the Sierra Valley Health homepage with the Clara drawer built in.

UI only. The agent loop, system prompt and tools are unchanged; agent.chat() reports tool
events through on_event, and this layer turns them into chat cards and the presenter panel.
"""
import importlib
import re
from html import escape

import gradio as gr

import mock_data
from agent import _EMERGENCY_PATTERN, chat, redact_payment_details
from data_store import DATA_BACKEND, get_store
import tools
from tools import new_session
from ui import cards, presenter
from ui.homepage import drawer_head_html, homepage_html
from ui.theme import build_theme, css, head_html

WELCOME_MSG = (
    "Hi, I'm Clara with Sierra Valley Health Patient Access. I can book, move or cancel a visit, "
    "send a refill request to your doctor, or answer questions about hours, locations and parking. "
    "How can I help you today?"
)
TYPING_HTML = '<span class="typing-dots" aria-label="Clara is typing"><span></span><span></span><span></span></span>'


def _welcome() -> list[dict]:
    return [{"role": "assistant", "content": WELCOME_MSG}]


OUTREACH_SMS = ("Sierra Valley Health: Hi, this is Clara. One of your home monitoring devices hasn't sent a reading "
                "in 3 days. Reply 1 to fix it now, 2 to have a nurse call you. Reply STOP to opt out.")

# Every channel starts unverified: the patient gives their name and date of birth, and Clara checks
# them against the data store (the Google Sheet when DATA_BACKEND=sheets).
CHANNEL_WELCOME = {
    "web": WELCOME_MSG,
    "portal": "Welcome to MySierra. To sign in for this demo, tell me your full name and date of birth. After that I "
              "won't ask again.",
    "sms": OUTREACH_SMS,
    "voice": "Thanks for calling Sierra Valley Health. This is Clara, a virtual assistant. How can I help you today?",
}
CHANNELS = ("web", "portal", "sms", "voice")
_ASKS_WHICH_MED = re.compile(r"\b(which|what)\b[^?]*\b(medication|medicine|prescription|refill)", re.IGNORECASE)
# Questions the patient must answer by typing: never offer buttons for personal details.
_ASKS_PERSONAL = re.compile(r"date of birth|\bdob\b|birthday|your (full |first |last )?name|phone number|"
                            r"callback number|member id|insurance (id|card)|address|social security", re.IGNORECASE)
TEXT_ONLY = {"sms", "voice"}  # no cards or step checklist: only words reach the patient


def start_channel(channel: str):
    """Switch the drawer to a channel with a fresh, unverified conversation."""
    channel = channel if channel in CHANNELS else "web"
    session = new_session()
    session["channel"] = channel
    if channel == "sms":
        session["outreach"] = OUTREACH_SMS
    return ([{"role": "assistant", "content": CHANNEL_WELCOME[channel]}], session, [], cards.verified_chip(session),
            presenter.render([]), "")


def _status_messages(events: list[dict]) -> list[dict]:
    """One checklist message for the turn: each tool call is a step that ticks off when its result
    arrives. Pending steps spin; failed steps show what's needed instead."""
    calls = [e for e in events if e["type"] == "tool_call"]
    if not calls:
        return []
    results = [e for e in events if e["type"] == "tool_result"]
    return [{"role": "assistant", "content": cards.steps_html(calls, results)}]


def prep_turn(message: str, history: list[dict]):
    """Instant: show the patient's message and typing dots, clear the box, remember the text."""
    if not message or not message.strip():
        return history, "", ""
    history = list(history or []) + [
        {"role": "user", "content": escape(redact_payment_details(message.strip()))},
        {"role": "assistant", "content": TYPING_HTML},
    ]
    return history, "", message.strip()


def run_turn(message: str, history: list[dict], session: dict, turns: list[dict]):
    """Stream Clara's turn: status lines while tools run, then her reply and the cards."""
    if not message:
        yield history, gr.skip(), gr.skip(), turns
        return
    redacted = redact_payment_details(message)
    card_removed, message = redacted != message, redacted  # nothing downstream sees a card number
    base = list(history[:-1])  # drop the typing dots
    events: list[dict] = []
    reply = ""
    try:
        for chunk in chat(message, [], session, on_event=events.append):
            reply = chunk
            status = [] if session.get("channel") in TEXT_ONLY else _status_messages(events)
            if status:
                yield base + status + [{"role": "assistant", "content": TYPING_HTML}], gr.skip(), gr.skip(), turns
    except Exception as exc:  # API outage, rate limit, network: keep the demo standing
        print(f"chat failed: {exc!r}", flush=True)
        reply = ("Sorry, I'm having trouble connecting right now. Please try again in a moment, "
                 "or call Patient Access at 555-301-4000.")
    emergency = bool(_EMERGENCY_PATTERN.search(message))
    text_only = session.get("channel") in TEXT_ONLY
    # Backstop for the refill picker: if Clara asks which medication without having looked them up,
    # look them up here so the one-tap picker always appears for a verified patient.
    used = {e["name"] for e in events if e["type"] == "tool_result"}
    if (not text_only and session.get("patient_id") and reply.rstrip().endswith("?")
            and _ASKS_WHICH_MED.search(reply) and not used & {"list_prescriptions", "submit_refill_request"}):
        events.append({"type": "tool_result", "name": "list_prescriptions", "input": {},
                       "result": tools.list_prescriptions(session), "ms": 0})
    turn_cards = [] if text_only else [{"role": "assistant", "content": c} for c in cards.cards_for_turn(events, emergency, reply, session)]
    quick = next((e["options"] for e in events if e["type"] == "quick_replies"), [])
    if (quick and not text_only and not emergency and not _ASKS_PERSONAL.search(reply)
            and not any("data-clara-prompt" in c["content"] for c in turn_cards)):
        turn_cards.append({"role": "assistant", "content": cards.quick_replies(quick)})
    if card_removed:
        turn_cards.insert(0, {"role": "assistant", "content": cards.card_removed_notice()})
    text = [{"role": "assistant", "content": reply or "Sorry, I wasn't able to respond. Please try again."}]
    body = turn_cards + text if emergency else text + turn_cards
    turns = turns + [presenter.build_turn(message, events, reply, emergency, session.get("channel", "web"))]
    yield base + ([] if text_only else _status_messages(events)) + body, cards.verified_chip(session), presenter.render(turns), turns


def reset_demo():
    """Same reset as start_demo.py: fresh demo data, a new conversation, an empty presenter panel."""
    if DATA_BACKEND == "sheets":
        get_store().reset()
    else:
        importlib.reload(mock_data)
    session = new_session()
    return _welcome(), session, [], cards.verified_chip(session), presenter.render([]), ""


def build_interface() -> gr.Blocks:
    gr.set_static_paths(["ui/assets"])
    with gr.Blocks(title="Sierra Valley Health — Care close to home", fill_width=True) as demo:
        gr.HTML(homepage_html(), elem_id="svh-home")

        session = gr.State(new_session)  # who is verified; one per browser tab, never sent to the model
        turns = gr.State([])
        stored_msg = gr.State("")

        with gr.Column(elem_id="clara-drawer"):
            gr.HTML(drawer_head_html(), elem_id="clara-head")
            verified = gr.HTML(cards.verified_chip({}), elem_id="clara-verified")
            with gr.Row(elem_id="clara-body", equal_height=False):
                with gr.Column(elem_id="clara-chat-col"):
                    chatbot = gr.Chatbot(
                        value=_welcome(),
                        elem_id="clara-chat",
                        show_label=False,
                        sanitize_html=False,  # only server-written card HTML; user text is escaped in prep_turn
                        avatar_images=(None, "ui/assets/clara-avatar.svg"),
                        buttons=[],
                        layout="bubble",
                        autoscroll=True,
                        height="100%",
                    )
                    with gr.Row(elem_id="clara-input-row"):
                        msg_box = gr.Textbox(
                            placeholder="Message Clara",
                            show_label=False,
                            lines=1,
                            max_lines=4,
                            elem_id="clara-input",
                            container=False,
                        )
                        send_btn = gr.Button("Send", elem_id="clara-send", scale=0)
                    gr.HTML('<p class="clara-fineprint">Clara can\'t give medical advice. Emergency? Call 911.</p>')
                with gr.Column(elem_id="clara-presenter-col"):
                    panel = gr.HTML(presenter.render([]), elem_id="clara-presenter")

        reset_btn = gr.Button("Reset demo", elem_id="clara-reset", elem_classes=["svh-hidden"])
        # Set by clara.js: the channel name goes in the box, then the button starts that channel.
        channel_box = gr.Textbox(elem_id="clara-channel", elem_classes=["svh-hidden"], show_label=False, container=False)
        channel_btn = gr.Button("Switch channel", elem_id="clara-channel-set", elem_classes=["svh-hidden"])

        for trigger in (msg_box.submit, send_btn.click):
            trigger(prep_turn, [msg_box, chatbot], [chatbot, msg_box, stored_msg], show_progress="hidden", queue=False).then(
                run_turn, [stored_msg, chatbot, session, turns], [chatbot, verified, panel, turns], show_progress="hidden"
            )

        channel_btn.click(start_channel, [channel_box], [chatbot, session, turns, verified, panel, stored_msg],
                          show_progress="hidden", queue=False)
        reset_btn.click(reset_demo, None, [chatbot, session, turns, verified, panel, stored_msg], show_progress="hidden").then(
            None, None, None, js="() => { window.location.reload(); }"
        )
    return demo


def launch_kwargs() -> dict:
    return {
        "theme": build_theme(),
        "css": css(),
        "head": head_html(),
        "footer_links": [],
        "favicon_path": "ui/assets/favicon.svg",
        "allowed_paths": ["ui/assets"],
    }
