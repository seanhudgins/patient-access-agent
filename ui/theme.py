"""Gradio theme and page head built from the design doc's tokens."""
from pathlib import Path

import gradio as gr

UI_DIR = Path(__file__).parent

NAVY, NAVY_2, POPPY, STONE, INK, MUTED, LINE = "#0B2545", "#13315C", "#F2B33D", "#F4F3EF", "#1B1F24", "#5B6573", "#DCDFE3"


def build_theme() -> gr.themes.Base:
    return gr.themes.Base(
        font=[gr.themes.GoogleFont("Public Sans"), "system-ui", "sans-serif"],
        radius_size=gr.themes.sizes.radius_md,
    ).set(
        body_background_fill=STONE,
        body_background_fill_dark=STONE,
        body_text_color=INK,
        body_text_color_dark=INK,
        body_text_color_subdued=MUTED,
        background_fill_primary="#FFFFFF",
        background_fill_primary_dark="#FFFFFF",
        background_fill_secondary=STONE,
        background_fill_secondary_dark=STONE,
        block_background_fill="#FFFFFF",
        block_background_fill_dark="#FFFFFF",
        border_color_primary=LINE,
        border_color_primary_dark=LINE,
        input_background_fill="#FFFFFF",
        input_background_fill_dark="#FFFFFF",
        button_primary_background_fill=POPPY,
        button_primary_background_fill_dark=POPPY,
        button_primary_background_fill_hover="#E8A526",
        button_primary_text_color=NAVY,
        button_primary_text_color_dark=NAVY,
        button_secondary_background_fill="#FFFFFF",
        button_secondary_text_color=NAVY,
        color_accent=NAVY_2,
        link_text_color=NAVY,
        link_text_color_dark=NAVY,
        link_text_color_hover=NAVY_2,
        link_text_color_hover_dark=NAVY_2,
        link_text_color_visited=NAVY,
        link_text_color_visited_dark=NAVY,
        link_text_color_active=NAVY,
        link_text_color_active_dark=NAVY,
    )


def head_html() -> str:
    script = (UI_DIR / "clara.js").read_text(encoding="utf-8")
    return (
        '<meta name="description" content="Sierra Valley Health (fictional) demo homepage with Clara, a Patient Access assistant.">'
        '<link rel="icon" type="image/svg+xml" href="/gradio_api/file=ui/assets/favicon.svg">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700&family=Public+Sans:wght@400;600;700&display=swap" rel="stylesheet">'
        # Body-state rules only; the main stylesheet goes through css= (see states.css).
        f"<style>{(UI_DIR / 'states.css').read_text(encoding='utf-8')}</style>"
        f"<script>{script}</script>"
    )


def css() -> str:
    return (UI_DIR / "styles.css").read_text(encoding="utf-8")
