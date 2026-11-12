"""Synthetic demo data for Sierra Valley Health. No real patient information.

Dates are generated relative to today so the demo never goes stale. This is the
"mock" data backend (see data_store.py), and seed_sheet.py copies it into the
Google Sheet for the "sheets" backend.
"""
import datetime

_TODAY = datetime.date.today()


def _at(days: int, time: str) -> str:
    return f"{(_TODAY + datetime.timedelta(days=days)).isoformat()}T{time}"


def _weekday_at(days: int, time: str) -> str:
    """Like _at, but rolls weekend dates forward to Monday (clinic hours are Mon-Fri)."""
    date = _TODAY + datetime.timedelta(days=days)
    while date.weekday() >= 5:
        date += datetime.timedelta(days=1)
    return f"{date.isoformat()}T{time}"


def _on(days: int) -> str:
    return (_TODAY + datetime.timedelta(days=days)).isoformat()


PATIENTS: dict = {
    "P1001": {
        "id": "P1001", "first_name": "Maria", "last_name": "Lopez", "date_of_birth": "1984-03-12",
        "phone": "555-301-1001", "primary_provider": "Dr. Chen", "preferred_pharmacy": "Riverside Pharmacy",
        "insurance": "Blue Horizon PPO", "referrals": "",
    },
    "P1002": {
        "id": "P1002", "first_name": "James", "last_name": "Okafor", "date_of_birth": "1971-11-02",
        "phone": "555-301-1002", "primary_provider": "Dr. Patel", "preferred_pharmacy": "Main St Pharmacy",
        "insurance": "Medicare", "referrals": "Orthopedics",
    },
    "P1003": {
        "id": "P1003", "first_name": "Alex", "last_name": "Kim", "date_of_birth": "1995-07-28",
        "phone": "555-301-1003", "primary_provider": "Dr. Chen", "preferred_pharmacy": "Riverside Pharmacy",
        "insurance": "Sierra Select HMO", "referrals": "",
    },
    "P1004": {
        "id": "P1004", "first_name": "Sarah", "last_name": "Bellum", "date_of_birth": "1985-06-14",
        "phone": "555-301-1004", "primary_provider": "Dr. Patel", "preferred_pharmacy": "Riverside Pharmacy",
        "insurance": "Blue Horizon PPO", "referrals": "",
    },
}

PROVIDERS: dict = {
    "PRV-01": {
        "id": "PRV-01", "name": "Dr. Chen", "specialty": "Primary Care", "location": "Midtown Clinic",
        "telehealth": True, "referral_required_for_new_patients": False,
    },
    "PRV-02": {
        "id": "PRV-02", "name": "Dr. Patel", "specialty": "Primary Care", "location": "Eastside Clinic",
        "telehealth": True, "referral_required_for_new_patients": False,
    },
    "PRV-03": {
        "id": "PRV-03", "name": "Dr. Reyes", "specialty": "Orthopedics", "location": "Midtown Clinic",
        "telehealth": False, "referral_required_for_new_patients": True,
    },
    "PRV-04": {
        "id": "PRV-04", "name": "Dr. Reed", "specialty": "Cardiology", "location": "Heart & Vascular Center",
        "telehealth": False, "referral_required_for_new_patients": True,
    },
    "PRV-05": {
        "id": "PRV-05", "name": "Dr. Shah", "specialty": "Dermatology", "location": "Midtown Clinic",
        "telehealth": True, "referral_required_for_new_patients": False,
    },
}


def _appointment(appt_id, patient_id, provider_id, reason, visit_type, start_time, status) -> dict:
    provider = PROVIDERS[provider_id]
    return {
        "id": appt_id,
        "patient_id": patient_id,
        "provider_id": provider_id,
        "provider_name": provider["name"],
        "specialty": provider["specialty"],
        "reason": reason,
        "visit_type": visit_type,
        "location": "Telehealth (video link sent 1 hour before)" if visit_type == "telehealth" else provider["location"],
        "start_time": start_time,
        "duration_min": 30,
        "status": status,
    }


MOCK_APPOINTMENTS: dict = {
    "APT-2001": _appointment("APT-2001", "P1001", "PRV-01", "Annual physical", "in_person", _weekday_at(5, "09:30"), "scheduled"),
    "APT-2002": _appointment("APT-2002", "P1001", "PRV-04", "Blood pressure follow-up", "in_person", _at(1, "08:00"), "scheduled"),
    "APT-2003": _appointment("APT-2003", "P1002", "PRV-02", "Follow-up visit", "in_person", _at(-20, "10:30"), "completed"),
    "APT-2004": _appointment("APT-2004", "P1002", "PRV-02", "Follow-up visit", "telehealth", _weekday_at(7, "10:00"), "scheduled"),
    "APT-2005": _appointment("APT-2005", "P1004", "PRV-05", "Annual skin check", "in_person", _at(-14, "10:00"), "completed"),
    "APT-2006": _appointment("APT-2006", "P1004", "PRV-02", "Annual physical", "in_person", _weekday_at(9, "16:00"), "scheduled"),
}

MOCK_PRESCRIPTIONS: dict = {
    "RX-3001": {
        "id": "RX-3001", "patient_id": "P1001", "medication": "Lisinopril 10 mg", "prescriber": "Dr. Chen",
        "refills_remaining": 2, "controlled": False, "last_filled": _on(-26),
    },
    "RX-3002": {
        "id": "RX-3002", "patient_id": "P1001", "medication": "Atorvastatin 20 mg", "prescriber": "Dr. Chen",
        "refills_remaining": 0, "controlled": False, "last_filled": _on(-31),
    },
    "RX-3003": {
        "id": "RX-3003", "patient_id": "P1002", "medication": "Metformin 500 mg", "prescriber": "Dr. Patel",
        "refills_remaining": 1, "controlled": False, "last_filled": _on(-24),
    },
    "RX-3004": {
        "id": "RX-3004", "patient_id": "P1004", "medication": "Levothyroxine 50 mcg", "prescriber": "Dr. Patel",
        "refills_remaining": 3, "controlled": False, "last_filled": _on(-28),
    },
    "RX-3005": {
        "id": "RX-3005", "patient_id": "P1004", "medication": "Alprazolam 0.5 mg", "prescriber": "Dr. Patel",
        "refills_remaining": 0, "controlled": True, "last_filled": _on(-20),
    },
}

_SLOT_TIMES = ["08:30", "10:00", "11:30", "13:30", "15:00", "16:30"]


def _build_slots() -> dict[str, list[str]]:
    """Open slots for the next two weeks (weekdays only); roughly a third of each schedule is open."""
    slots: dict[str, list[str]] = {}
    for i, provider_id in enumerate(PROVIDERS):
        open_slots = []
        for day in range(1, 15):
            if (_TODAY + datetime.timedelta(days=day)).weekday() >= 5:
                continue
            for j, time in enumerate(_SLOT_TIMES):
                if (day + i + j) % 3 == 0:
                    open_slots.append(_at(day, time))
        slots[provider_id] = open_slots
    return slots


AVAILABLE_SLOTS: dict[str, list[str]] = _build_slots()

# Refill requests and staff handoffs start empty; Clara creates them during the demo.
MOCK_REFILL_REQUESTS: list[dict] = []
MOCK_HANDOFFS: list[dict] = []
