from dotenv import load_dotenv

load_dotenv()

from ui.app import build_interface, launch_kwargs  # noqa: E402


def main():
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True, **launch_kwargs())


if __name__ == "__main__":
    main()
