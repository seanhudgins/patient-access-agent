"""Reset the Google Sheet to fresh demo data. Run before each demo: `uv run seed_sheet.py`

Needs GOOGLE_SHEET_ID and a service account key (GOOGLE_SERVICE_ACCOUNT_FILE,
default service_account.json) in .env. The sheet must be shared with the
service account's email as an Editor.
"""
from dotenv import load_dotenv

load_dotenv()

from data_store import TABS, SheetsStore  # noqa: E402


def main():
    SheetsStore().reset()
    print(f"Seeded tabs: {', '.join(TABS)}")


if __name__ == "__main__":
    main()
