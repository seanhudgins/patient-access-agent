"""Where the patient assistant's data lives.

DATA_BACKEND selects the backend:
  mock        in-memory data from mock_data.py (default; resets when the app restarts)
  sheets      a Google Sheet, read and written through a service account
  salesforce  in-memory data, with staff handoffs created as Salesforce Cases

The tools in tools.py only talk to the store returned by get_store(), so switching
backends needs no tool changes.
"""
import json
import os

import mock_data

DATA_BACKEND = os.environ.get("DATA_BACKEND", "mock").strip().lower()

# One tab per record type. Column order is the order written by seed_sheet.py.
TABS: dict[str, list[str]] = {
    "Patients": [
        "id", "first_name", "last_name", "date_of_birth", "phone", "primary_provider",
        "preferred_pharmacy", "insurance", "referrals",
    ],
    "Providers": ["id", "name", "specialty", "location", "telehealth", "referral_required_for_new_patients"],
    "Appointments": [
        "id", "patient_id", "provider_id", "provider_name", "specialty", "reason",
        "visit_type", "location", "start_time", "duration_min", "status",
    ],
    "Slots": ["provider_id", "start_time"],
    "Prescriptions": ["id", "patient_id", "medication", "prescriber", "refills_remaining", "controlled", "last_filled"],
    "RefillRequests": ["id", "patient_id", "medication", "prescriber", "pharmacy", "status", "created"],
    "Handoffs": ["id", "created", "queue", "priority", "patient_id", "caller", "callback_phone", "summary", "status"],
}

_BOOL_FIELDS = {"telehealth", "referral_required_for_new_patients", "controlled"}
_INT_FIELDS = {"duration_min", "refills_remaining"}


class MemoryStore:
    """Reads and mutates the in-memory data in mock_data.py."""

    def patients(self) -> dict:
        return mock_data.PATIENTS

    def providers(self) -> dict:
        return mock_data.PROVIDERS

    def appointments(self) -> dict:
        return mock_data.MOCK_APPOINTMENTS

    def add_appointment(self, appt: dict) -> None:
        mock_data.MOCK_APPOINTMENTS[appt["id"]] = appt

    def set_appointment_status(self, appt_id: str, status: str) -> None:
        mock_data.MOCK_APPOINTMENTS[appt_id]["status"] = status

    def open_slots(self) -> dict[str, list[str]]:
        return mock_data.AVAILABLE_SLOTS

    def take_slot(self, provider_id: str, start_time: str) -> bool:
        slots = mock_data.AVAILABLE_SLOTS.get(provider_id, [])
        if start_time not in slots:
            return False
        slots.remove(start_time)
        return True

    def release_slot(self, provider_id: str, start_time: str) -> None:
        slots = mock_data.AVAILABLE_SLOTS.setdefault(provider_id, [])
        slots.append(start_time)
        slots.sort()

    def prescriptions(self) -> dict:
        return mock_data.MOCK_PRESCRIPTIONS

    def refill_requests(self) -> list[dict]:
        return mock_data.MOCK_REFILL_REQUESTS

    def add_refill_request(self, request: dict) -> None:
        mock_data.MOCK_REFILL_REQUESTS.append(request)

    def handoffs(self) -> list[dict]:
        return mock_data.MOCK_HANDOFFS

    def add_handoff(self, handoff: dict) -> None:
        mock_data.MOCK_HANDOFFS.append(handoff)


# ── Google Sheets ─────────────────────────────────────────────────────────────
def _parse(field: str, value: str):
    if field in _BOOL_FIELDS:
        return value.strip().upper() == "TRUE"
    if value == "":
        return None
    if field in _INT_FIELDS:
        return int(float(value))
    return value


def _cell(value):
    return "" if value is None else value


def seed_rows() -> dict[str, list[list]]:
    """The demo data from mock_data.py as rows for each tab (header row first)."""
    records = {
        "Patients": list(mock_data.PATIENTS.values()),
        "Providers": list(mock_data.PROVIDERS.values()),
        "Appointments": list(mock_data.MOCK_APPOINTMENTS.values()),
        "Slots": [
            {"provider_id": provider_id, "start_time": start}
            for provider_id, starts in mock_data.AVAILABLE_SLOTS.items()
            for start in starts
        ],
        "Prescriptions": list(mock_data.MOCK_PRESCRIPTIONS.values()),
        "RefillRequests": mock_data.MOCK_REFILL_REQUESTS,
        "Handoffs": mock_data.MOCK_HANDOFFS,
    }
    return {
        tab: [fields] + [[_cell(r.get(f)) for f in fields] for r in records[tab]]
        for tab, fields in TABS.items()
    }


class SheetsStore:
    """Reads and writes the tabs of one Google Sheet. Every call hits the Sheets API, so the sheet is the source of truth."""

    def __init__(self):
        import gspread  # only needed for this backend

        from credentials import GOOGLE_ACCOUNT, get_secret

        # Keychain first (credentials.py store-google); a key file is the fallback.
        key_json = get_secret(GOOGLE_ACCOUNT, "GOOGLE_SERVICE_ACCOUNT_JSON")
        if key_json:
            client = gspread.service_account_from_dict(json.loads(key_json))
        else:
            client = gspread.service_account(
                filename=os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
            )
        self._book = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])

    def _records(self, tab: str) -> list[dict]:
        rows = self._book.worksheet(tab).get_all_values()
        if not rows:
            return []
        header, *body = rows
        return [
            {field: _parse(field, value) for field, value in zip(header, row)}
            for row in body if any(row)
        ]

    def _append(self, tab: str, record: dict) -> None:
        self._book.worksheet(tab).append_row(
            [_cell(record.get(f)) for f in TABS[tab]], value_input_option="RAW"
        )

    def _find_row(self, tab: str, **match) -> int | None:
        """1-based sheet row of the first record matching every field in match."""
        for i, record in enumerate(self._records(tab), start=2):
            if all(record.get(k) == v for k, v in match.items()):
                return i
        return None

    def _update(self, tab: str, row: int, field: str, value) -> None:
        self._book.worksheet(tab).update_cell(row, TABS[tab].index(field) + 1, value)

    def patients(self) -> dict:
        return {p["id"]: p for p in self._records("Patients")}

    def providers(self) -> dict:
        return {p["id"]: p for p in self._records("Providers")}

    def appointments(self) -> dict:
        return {a["id"]: a for a in self._records("Appointments")}

    def add_appointment(self, appt: dict) -> None:
        self._append("Appointments", appt)

    def set_appointment_status(self, appt_id: str, status: str) -> None:
        row = self._find_row("Appointments", id=appt_id)
        if row:
            self._update("Appointments", row, "status", status)

    def open_slots(self) -> dict[str, list[str]]:
        slots: dict[str, list[str]] = {}
        for s in self._records("Slots"):
            slots.setdefault(s["provider_id"], []).append(s["start_time"])
        return {provider_id: sorted(starts) for provider_id, starts in slots.items()}

    def take_slot(self, provider_id: str, start_time: str) -> bool:
        row = self._find_row("Slots", provider_id=provider_id, start_time=start_time)
        if row is None:
            return False
        self._book.worksheet("Slots").delete_rows(row)
        return True

    def release_slot(self, provider_id: str, start_time: str) -> None:
        self._append("Slots", {"provider_id": provider_id, "start_time": start_time})

    def prescriptions(self) -> dict:
        return {r["id"]: r for r in self._records("Prescriptions")}

    def refill_requests(self) -> list[dict]:
        return self._records("RefillRequests")

    def add_refill_request(self, request: dict) -> None:
        self._append("RefillRequests", request)

    def handoffs(self) -> list[dict]:
        return self._records("Handoffs")

    def add_handoff(self, handoff: dict) -> None:
        self._append("Handoffs", handoff)

    def reset(self) -> None:
        """Replace every tab's contents with fresh demo data (dates relative to today)."""
        existing = {ws.title: ws for ws in self._book.worksheets()}
        for tab, rows in seed_rows().items():
            ws = existing.get(tab) or self._book.add_worksheet(tab, rows=len(rows) + 50, cols=len(rows[0]))
            ws.clear()
            ws.update(range_name="A1", values=rows, value_input_option="RAW")
            ws.freeze(rows=1)
            ws.format("1:1", {"textFormat": {"bold": True}})
        # Drop tabs this version no longer uses (and the default tab a new spreadsheet starts with)
        for title, ws in existing.items():
            if title not in TABS:
                self._book.del_worksheet(ws)


_store = None


def get_store():
    global _store
    if _store is None:
        _store = SheetsStore() if DATA_BACKEND == "sheets" else MemoryStore()
    return _store
