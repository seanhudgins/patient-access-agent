"""One command to run the demo: `uv run start_demo.py`

Resets the Google Sheet to fresh demo data (when DATA_BACKEND=sheets), then
launches the app at http://localhost:7860.
"""
from dotenv import load_dotenv

load_dotenv()

import main  # noqa: E402
import seed_sheet  # noqa: E402
from data_store import DATA_BACKEND  # noqa: E402

if __name__ == "__main__":
    if DATA_BACKEND == "sheets":
        print("Resetting the Google Sheet to fresh demo data...")
        seed_sheet.main()
    print(f"Starting the app ({DATA_BACKEND} backend) at http://localhost:7860")
    main.main()
