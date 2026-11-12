import gradio as gr

from agent import chat
from tools import new_session

QUICK_ACTIONS = [
    ("📅  Book an Appointment",   "I'd like to book an appointment."),
    ("🔁  Reschedule / Cancel",   "I need to reschedule or cancel an appointment."),
    ("💊  Prescription Refill",   "I need a refill on my medication."),
    ("📍  Hours & Locations",     "What are your hours and locations?"),
    ("🔑  Portal Password Reset", "I can't log in to the patient portal."),
    ("🩺  Talk to a Nurse",       "I have a question for a nurse."),
]

BRAND_CSS = """
/* ── Sierra Valley Health Global ── */
body, .gradio-container {
    background-color: #f4f8f9 !important;
}

/* ── Logo header ── */
#brand-header {
    background: #ffffff;
    border-bottom: 4px solid #0E7C86;
    padding: 28px 36px 24px 36px;
    margin-bottom: 0;
    text-align: center;
}

/* ── Tagline bar ── */
#brand-tagline {
    background: #0E7C86;
    color: #ffffff;
    text-align: center;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 7px 0;
    margin-bottom: 16px;
}

/* ── Emergency notice ── */
#emergency-banner {
    background: #FDECEC;
    border: 1px solid #E5A0A0;
    color: #8A1C1C;
    border-radius: 8px;
    font-family: Arial, sans-serif;
    font-size: 0.85rem;
    text-align: center;
    padding: 8px 12px;
    margin: 0 8px 12px 8px;
}

/* ── Quick action buttons ── */
#quick-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: center;
    padding: 4px 8px 16px 8px;
}

.quick-btn button {
    background: #ffffff !important;
    border: 2px solid #111111 !important;
    color: #111111 !important;
    border-radius: 24px !important;
    font-family: Arial, sans-serif !important;
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    padding: 8px 18px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
    white-space: nowrap !important;
}

.quick-btn button:hover {
    background: #0E7C86 !important;
    border-color: #0E7C86 !important;
    color: #ffffff !important;
}

/* ── Chat bubbles ── */
.user {
    background: #0E7C86 !important;
    color: #ffffff !important;
    border-radius: 14px 14px 4px 14px !important;
    font-family: Arial, sans-serif !important;
    border: none !important;
}

.bot {
    background: #ffffff !important;
    border: 2px solid #0E7C86 !important;
    color: #111111 !important;
    border-radius: 14px 14px 14px 4px !important;
    font-family: Arial, sans-serif !important;
}

.bot * {
    color: #111111 !important;
}

/* ── Input box ── */
.block textarea,
label textarea {
    background: #ffffff !important;
    border: 2px solid #dddddd !important;
    border-radius: 6px !important;
    color: #111111 !important;
    font-family: Arial, sans-serif !important;
    font-size: 0.97rem !important;
}

.block textarea:focus {
    border-color: #0E7C86 !important;
    box-shadow: 0 0 0 3px rgba(14, 124, 134, 0.15) !important;
}

/* ── Send button ── */
#send-btn button {
    background: #0E7C86 !important;
    border: none !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 6px !important;
    font-family: Arial, sans-serif !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    font-size: 0.85rem !important;
    height: 100% !important;
}

#send-btn button:hover {
    background: #0B656D !important;
}

/* ── Typing indicator dots ── */
.typing-dots {
    display: inline-flex;
    gap: 5px;
    align-items: center;
    height: 22px;
}
.typing-dots span {
    width: 9px;
    height: 9px;
    background: #0E7C86;
    border-radius: 50%;
    display: inline-block;
    animation: typing-bounce 1.2s infinite ease-in-out;
}
.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.18s; }
.typing-dots span:nth-child(3) { animation-delay: 0.36s; }
@keyframes typing-bounce {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.35; }
    30% { transform: translateY(-6px); opacity: 1; }
}

/* ── Chatbot container ── */
.chatbot, div[data-testid="chatbot"], #patient-chat,
.chatbot > div, div[data-testid="chatbot"] > div {
    background: #f4f8f9 !important;
    border: 1px solid #e0e0e0 !important;
    border-radius: 8px !important;
}

/* ── Override Gradio theme CSS variables (beats dark-mode defaults) ── */
.gradio-container, :root {
    --button-secondary-background-fill: #ffffff !important;
    --button-secondary-background-fill-hover: #f5f5f5 !important;
    --button-secondary-text-color: #111111 !important;
    --button-secondary-border-color: #cccccc !important;
    --block-background-fill: #ffffff !important;
    --background-fill-primary: #f4f8f9 !important;
    --background-fill-secondary: #eef3f4 !important;
    --body-background-fill: #f4f8f9 !important;
    --input-background-fill: #ffffff !important;
    --border-color-primary: #dddddd !important;
    --body-text-color: #111111 !important;
    --body-text-color-subdued: #555555 !important;
}

/* ── Force light mode on everything in OS dark mode ── */
@media (prefers-color-scheme: dark) {
    body, .gradio-container, html {
        background-color: #f4f8f9 !important;
        color: #111111 !important;
    }
    .bubble-wrap {
        background: #f4f8f9 !important;
    }
    /* Reinforce bubble colors */
    .bot {
        background: #ffffff !important;
        border: 2px solid #0E7C86 !important;
        color: #111111 !important;
    }
    .bot * { color: #111111 !important; }
    .user {
        background: #0E7C86 !important;
        color: #ffffff !important;
    }
    /* Quick action buttons */
    .quick-btn button {
        background: #ffffff !important;
        border: 2px solid #111111 !important;
        color: #111111 !important;
    }
    .quick-btn button:hover {
        background: #0E7C86 !important;
        border-color: #0E7C86 !important;
        color: #ffffff !important;
    }
    /* Input box */
    textarea, input[type="text"] {
        background: #ffffff !important;
        border-color: #dddddd !important;
        color: #111111 !important;
    }
    .wrap, .wrap-inner {
        background: #ffffff !important;
        border-color: #dddddd !important;
    }
    /* Block / panel backgrounds */
    .block, .panel, .form, .gap {
        background: #f4f8f9 !important;
        border-color: #e0e0e0 !important;
    }
    /* Chatbot toolbar icon buttons */
    .icon-button-wrapper button, .copy-button,
    button.copy, .chatbot button, .tool-button {
        background: #eef3f4 !important;
        border-color: #dddddd !important;
        color: #111111 !important;
    }
}
"""

LOGO_HTML = """
<div id="brand-header">
  <div style="display:inline-flex; align-items:center; gap:14px; line-height:1;">
    <span style="display:inline-flex; align-items:center; justify-content:center;
                 width:3.4rem; height:3.4rem; background:#0E7C86; border-radius:50%;
                 color:#ffffff; font-family:'Arial Black',Arial,sans-serif;
                 font-size:2.6rem; font-weight:900;">+</span>
    <span style="font-family:'Arial Black',Arial,sans-serif; font-weight:900;
                 font-size:3.4rem; color:#111111; letter-spacing:-0.01em;">Sierra Valley</span>
  </div>
  <div style="font-family:Arial,sans-serif; font-size:0.78rem; color:#888888;
              letter-spacing:0.25em; text-transform:uppercase; margin-top:8px;">
    Health
  </div>
</div>
<div id="brand-tagline">
  Chat with Clara &nbsp;&mdash;&nbsp; Sierra Valley Health Patient Access Center
</div>
"""

EMERGENCY_HTML = """
<div id="emergency-banner">
  <strong>Medical emergency? Call 911.</strong> &nbsp;Thoughts of suicide or self-harm? Call or text <strong>988</strong>.
  &nbsp;Patient Access: 555-301-4000. &nbsp;Clara can't give medical advice.
</div>
"""

WELCOME_MSG = (
    "Hi, I'm Clara with the Sierra Valley Health Patient Access Center. I can help you book, reschedule, "
    "or cancel an appointment, request a prescription refill, or answer questions about hours, locations, "
    "parking, and more. How can I help you today?"
)


TYPING_HTML = '<span class="typing-dots"><span></span><span></span><span></span></span>'


def prep_chat(message, history):
    """Sync: instantly adds user bubble + typing dots, clears input, stores message."""
    if not message or not message.strip():
        return history, "", ""
    history = list(history) if history else []
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": TYPING_HTML})
    return history, "", message  # → chatbot, msg_box, stored_msg


def stream_response(message, history, session):
    """Generator: replaces typing dots with the streamed agent response."""
    if not message or not message.strip():
        yield history
        return
    history_with_user = list(history[:-1])   # drop typing indicator
    prior_history = history_with_user[:-1]    # drop current user turn

    partial = ""
    for chunk in chat(message, prior_history, session):
        partial = chunk
        yield history_with_user + [{"role": "assistant", "content": partial}]

    if not partial:
        partial = "Sorry, I wasn't able to generate a response. Please try again."
    yield history_with_user + [{"role": "assistant", "content": partial}]


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="Sierra Valley Health — Patient Access") as demo:
        gr.HTML(LOGO_HTML)
        gr.HTML(EMERGENCY_HTML)

        stored_msg = gr.State("")
        session = gr.State(new_session)  # who is verified; one per browser tab, never sent to the model

        # ── Quick action buttons ──────────────────────────────────────
        with gr.Row(elem_id="quick-actions"):
            buttons = []
            for label, _ in QUICK_ACTIONS:
                btn = gr.Button(label, elem_classes=["quick-btn"])
                buttons.append(btn)

        # ── Chat area ─────────────────────────────────────────────────
        chatbot = gr.Chatbot(
            value=[{"role": "assistant", "content": WELCOME_MSG}],
            elem_id="patient-chat",
            height=480,
            sanitize_html=False,
        )

        # ── Input row ─────────────────────────────────────────────────
        with gr.Row():
            msg_box = gr.Textbox(
                placeholder="Type your message here and press Enter...",
                show_label=False,
                scale=5,
            )
            send_btn = gr.Button("Send →", variant="primary", scale=1, elem_id="send-btn")

        # ── Wire: textbox submit + send button ────────────────────────
        # Step 1 (sync, instant): add user bubble + typing dots, clear input
        # Step 2 (streaming): replace typing dots with agent response
        for trigger in (msg_box.submit, send_btn.click):
            trigger(
                prep_chat,
                [msg_box, chatbot],
                [chatbot, msg_box, stored_msg],
                show_progress="hidden",
            ).then(
                stream_response,
                [stored_msg, chatbot, session],
                [chatbot],
                show_progress="hidden",
            )

        # ── Wire: quick action buttons ────────────────────────────────
        for btn, (_, message) in zip(buttons, QUICK_ACTIONS):
            btn.click(
                fn=lambda m=message: (m, m),
                outputs=[msg_box, stored_msg],
                show_progress="hidden",
            ).then(
                prep_chat,
                [msg_box, chatbot],
                [chatbot, msg_box, stored_msg],
                show_progress="hidden",
            ).then(
                stream_response,
                [stored_msg, chatbot, session],
                [chatbot],
                show_progress="hidden",
            )

    return demo
