from dotenv import load_dotenv

load_dotenv()

import gradio as gr  # noqa: E402
from ui import BRAND_CSS, build_interface  # noqa: E402

# Brand teal (#0E7C86) as a Gradio theme color scale
_brand_teal = gr.themes.Color(
    c50="#e7f5f6", c100="#c3e6e8", c200="#8fd0d4", c300="#57b5bc",
    c400="#2b9aa3", c500="#0E7C86", c600="#0c6c75", c700="#0B656D",
    c800="#084c52", c900="#063a3f", c950="#03272a",
)


def main():
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True, theme=gr.themes.Soft(primary_hue=_brand_teal), css=BRAND_CSS)


if __name__ == "__main__":
    main()
