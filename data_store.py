"""Where the patient assistant's data lives.

DATA_BACKEND selects the backend:
  mock        in-memory data from mock_data.py (default; resets when the app restarts)
  sheets      a Google Sheet, read and written through a service account
  salesforce  in-memory data, with staff handoffs created as Salesforce Cases

The tools in tools.py only talk to the store returned by get_store(), so switching
backends needs no tool changes.
"""
import copy
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
    "Devices": ["patient_id", "program", "device", "connection", "last_sync", "systolic", "diastolic",
                "weight_lb", "change_2_days_lb", "flagged"],
    "Statements": ["statement_id", "patient_id", "visit_date", "provider_name", "location", "facility_charge",
                   "professional_charge", "insurance_paid", "copay", "deductible", "balance_due", "due_date",
                   "payment_plan_eligible"],
}

_BOOL_FIELDS = {"telehealth", "referral_required_for_new_patients", "controlled", "flagged", "payment_plan_eligible"}
_INT_FIELDS = {"duration_min", "refills_remaining", "systolic", "diastolic"}
_FLOAT_FIELDS = {"weight_lb", "change_2_days_lb", "facility_charge", "professional_charge", "insurance_paid",
                 "copay", "deductible", "balance_due"}


# Devices and statements are nested in mock_data.py and flat (one row each) in the Sheet.
def _device_rows() -> list[dict]:
    return [{"patient_id": pid, "program": d["program"], "device": d["device"], "connection": d["connection"],
             "last_sync": d["last_sync"], "flagged": d["flagged"],
             **{k: d["last_reading"].get(k) for k in ("systolic", "diastolic", "weight_lb", "change_2_days_lb")}}
            for pid, devs in mock_data.HOME_DEVICES.items() for d in devs]


def _device_from_row(r: dict) -> dict:
    reading = {k: r[k] for k in ("systolic", "diastolic", "weight_lb", "change_2_days_lb") if r.get(k) is not None}
    return {"program": r["program"], "device": r["device"], "connection": r["connection"], "last_sync": r["last_sync"],
            "last_reading": {"taken": r["last_sync"], **reading}, "flagged": r["flagged"]}


def _statement_rows() -> list[dict]:
    rows = []
    for pid, sts in mock_data.BILLING_STATEMENTS.items():
        for st in sts:
            rows.append({"statement_id": st["statement_id"], "patient_id": pid, "visit_date": st["visit_date"],
                         "provider_name": st["provider_name"], "location": st["location"],
                         "facility_charge": st["charges"][0]["amount"], "professional_charge": st["charges"][1]["amount"],
                         "insurance_paid": st["insurance_paid"], "copay": st["patient_responsibility"]["copay"],
                         "deductible": st["patient_responsibility"]["deductible"], "balance_due": st["balance_due"],
                         "due_date": st["due_date"], "payment_plan_eligible": st["payment_plan_eligible"]})
    return rows


def _statement_from_row(r: dict) -> dict:
    return {"statement_id": r["statement_id"], "visit_date": r["visit_date"], "provider_name": r["provider_name"],
            "location": r["location"],
            "charges": [{"type": "Facility charge (the clinic)", "amount": r["facility_charge"]},
                        {"type": "Professional charge (the doctor's services)", "amount": r["professional_charge"]}],
            "insurance_paid": r["insurance_paid"],
            "patient_responsibility": {"copay": r["copay"], "deductible": r["deductible"]},
            "balance_due": r["balance_due"], "due_date": r["due_date"], "payment_plan_eligible": r["payment_plan_eligible"]}


_MEMORY_TABLES = ("PATIENTS", "PROVIDERS", "MOCK_APPOINTMENTS", "AVAILABLE_SLOTS",
                  "MOCK_PRESCRIPTIONS", "MOCK_REFILL_REQUESTS", "MOCK_HANDOFFS", "HOME_DEVICES", "BILLING_STATEMENTS")


class MemoryStore:
    """Reads and mutates the in-memory data in mock_data.py.

    With a session, get_store() gives each browser tab its own copy, so two people running the
    demo at once (or a Reset in another tab) never change each other's data.
    """

    def __init__(self, private: bool = False):
        self._own = None
        if private:
            self._own = {name: copy.deepcopy(getattr(mock_data, name)) for name in _MEMORY_TABLES}

    def _t(self, name: str):
        return self._own[name] if self._own is not None else getattr(mock_data, name)

    def patients(self) -> dict:
        return self._t("PATIENTS")

    def providers(self) -> dict:
        return self._t("PROVIDERS")

    def appointments(self) -> dict:
        return self._t("MOCK_APPOINTMENTS")

    def add_appointment(self, appt: dict) -> None:
        self._t("MOCK_APPOINTMENTS")[appt["id"]] = appt

    def set_appointment_status(self, appt_id: str, status: str) -> None:
        self._t("MOCK_APPOINTMENTS")[appt_id]["status"] = status

    def open_slots(self) -> dict[str, list[str]]:
        return self._t("AVAILABLE_SLOTS")

    def take_slot(self, provider_id: str, start_time: str) -> bool:
        slots = self._t("AVAILABLE_SLOTS").get(provider_id, [])
        if start_time not in slots:
            return False
        slots.remove(start_time)
        return True

    def release_slot(self, provider_id: str, start_time: str) -> None:
        slots = self._t("AVAILABLE_SLOTS").setdefault(provider_id, [])
        slots.append(start_time)
        slots.sort()

    def prescriptions(self) -> dict:
        return self._t("MOCK_PRESCRIPTIONS")

    def refill_requests(self) -> list[dict]:
        return self._t("MOCK_REFILL_REQUESTS")

    def add_refill_request(self, request: dict) -> None:
        self._t("MOCK_REFILL_REQUESTS").append(request)

    def handoffs(self) -> list[dict]:
        return self._t("MOCK_HANDOFFS")

    def add_handoff(self, handoff: dict) -> None:
        self._t("MOCK_HANDOFFS").append(handoff)

    def home_devices(self, patient_id: str) -> list[dict]:
        return self._t("HOME_DEVICES").get(patient_id, [])

    def billing_statements(self, patient_id: str) -> list[dict]:
        return self._t("BILLING_STATEMENTS").get(patient_id, [])


# ── Google Sheets ─────────────────────────────────────────────────────────────
def _parse(field: str, value: str):
    if field in _BOOL_FIELDS:
        return value.strip().upper() == "TRUE"
    if value == "":
        return None
    if field in _INT_FIELDS:
        return int(float(value))
    if field in _FLOAT_FIELDS:
        return float(value)
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
        "Devices": _device_rows(),
        "Statements": _statement_rows(),
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

    def home_devices(self, patient_id: str) -> list[dict]:
        return [_device_from_row(r) for r in self._records("Devices") if r["patient_id"] == patient_id]

    def billing_statements(self, patient_id: str) -> list[dict]:
        return [_statement_from_row(r) for r in self._records("Statements") if r["patient_id"] == patient_id]

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


def get_store(session: dict | None = None):
    """The data store. With the mock backend and a session, each session gets its own copy."""
    if session is not None and DATA_BACKEND != "sheets":
        if "store" not in session:
            session["store"] = MemoryStore(private=True)
        return session["store"]
    global _store
    if _store is None:
        _store = SheetsStore() if DATA_BACKEND == "sheets" else MemoryStore()
    return _store
