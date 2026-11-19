"""Synthetic demo data for Sierra Valley Health. No real patient information.

Dates are generated relative to today so the demo never goes stale. This is the
"mock" data backend (see data_store.py), and seed_sheet.py copies it into the
Google Sheet for the "sheets" backend.
"""
import datetime

_TODAY = datetime.date.today()


def _at(days: int, time: str) -> str:
    return f"{(_TODAY + datetime.timedelta(days=days)).isoformat()}T{time}"


def _inside_24h(slot: int = 0) -> str:
    """A clinic-hours start time less than 24 hours away, whatever time the demo starts, so the
    late-cancel scenario always applies: tomorrow from 8:00am, or today from 3:00pm before 8:30am.
    `slot` staggers patients by half an hour."""
    now = datetime.datetime.now()
    minutes = slot * 30
    if now.hour * 60 + now.minute >= 8 * 60 + 30 + minutes:
        return _at(1, f"{8 + minutes // 60:02d}:{minutes % 60:02d}")
    return _at(0, f"{15 + minutes // 60:02d}:{minutes % 60:02d}")


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
    "APT-2002": _appointment("APT-2002", "P1001", "PRV-04", "Blood pressure follow-up", "in_person", _inside_24h(), "scheduled"),
    "APT-2003": _appointment("APT-2003", "P1002", "PRV-02", "Follow-up visit", "in_person", _at(-20, "10:30"), "completed"),
    "APT-2004": _appointment("APT-2004", "P1002", "PRV-02", "Follow-up visit", "telehealth", _weekday_at(7, "10:00"), "scheduled"),
    "APT-2005": _appointment("APT-2005", "P1004", "PRV-05", "Annual skin check", "in_person", _at(-14, "10:00"), "completed"),
    "APT-2006": _appointment("APT-2006", "P1004", "PRV-02", "Annual physical", "in_person", _weekday_at(9, "16:00"), "scheduled"),
    "APT-2007": _appointment("APT-2007", "P1002", "PRV-04", "Heart check-up", "in_person", _inside_24h(1), "scheduled"),
    "APT-2008": _appointment("APT-2008", "P1003", "PRV-01", "Follow-up visit", "telehealth", _weekday_at(6, "11:30"), "scheduled"),
    "APT-2009": _appointment("APT-2009", "P1003", "PRV-05", "Skin check", "in_person", _inside_24h(2), "scheduled"),
    "APT-2010": _appointment("APT-2010", "P1004", "PRV-04", "Blood pressure follow-up", "in_person", _inside_24h(3), "scheduled"),
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
    "RX-3006": {
        "id": "RX-3006", "patient_id": "P1004", "medication": "Lisinopril 20 mg", "prescriber": "Dr. Patel",
        "refills_remaining": 1, "controlled": False, "last_filled": _on(-27),
    },
    "RX-3007": {
        "id": "RX-3007", "patient_id": "P1001", "medication": "Zolpidem 5 mg", "prescriber": "Dr. Chen",
        "refills_remaining": 0, "controlled": True, "last_filled": _on(-25),
    },
    "RX-3008": {
        "id": "RX-3008", "patient_id": "P1002", "medication": "Tramadol 50 mg", "prescriber": "Dr. Patel",
        "refills_remaining": 0, "controlled": True, "last_filled": _on(-22),
    },
    "RX-3009": {
        "id": "RX-3009", "patient_id": "P1003", "medication": "Albuterol inhaler", "prescriber": "Dr. Chen",
        "refills_remaining": 2, "controlled": False, "last_filled": _on(-40),
    },
    "RX-3010": {
        "id": "RX-3010", "patient_id": "P1003", "medication": "Methylphenidate 10 mg", "prescriber": "Dr. Chen",
        "refills_remaining": 0, "controlled": True, "last_filled": _on(-29),
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


# Heart Health at Home: the remote blood-pressure program (modelled on real-world
# remote-monitoring programs). Readings are synthetic. "flagged" is set by the program's
# care-team alert range, not by Clara: she never interprets a reading.
def _device(kind: str, connection: str, last_sync_days: int, reading: dict, flagged: bool) -> dict:
    last = _at(last_sync_days, "07:40")
    return {"program": "Heart Health at Home", "device": kind, "connection": connection, "last_sync": last,
            "last_reading": {"taken": last, **reading}, "flagged": flagged}


_CUFF, _SCALE = "Bluetooth blood pressure cuff", "Bluetooth scale"
HOME_DEVICES = {
    "P1001": [_device(_CUFF, "not_syncing", -3, {"systolic": 128, "diastolic": 82}, False),
              _device(_SCALE, "ok", 0, {"weight_lb": 163.4, "change_2_days_lb": 4.2}, True)],
    "P1002": [_device(_CUFF, "not_syncing", -3, {"systolic": 134, "diastolic": 84}, False),
              _device(_SCALE, "ok", 0, {"weight_lb": 201.8, "change_2_days_lb": 4.6}, True)],
    "P1003": [_device(_CUFF, "ok", 0, {"systolic": 168, "diastolic": 104}, True),
              _device(_SCALE, "not_syncing", -3, {"weight_lb": 172.0, "change_2_days_lb": 0.2}, False)],
    "P1004": [_device(_CUFF, "ok", 0, {"systolic": 172, "diastolic": 106}, True),
              _device(_SCALE, "not_syncing", -3, {"weight_lb": 141.6, "change_2_days_lb": 0.4}, False)],
}

# Billing statements. Amounts are synthetic; Clara explains them but never takes payment details.
def _statement(sid, days_ago, provider, location, facility, professional, paid, copay, deductible, due_in):
    return {"statement_id": sid, "visit_date": _on(-days_ago), "provider_name": provider, "location": location,
            "charges": [{"type": "Facility charge (the clinic)", "amount": facility},
                        {"type": "Professional charge (the doctor's services)", "amount": professional}],
            "insurance_paid": paid, "patient_responsibility": {"copay": copay, "deductible": deductible},
            "balance_due": round(copay + deductible, 2), "due_date": _on(due_in),
            "payment_plan_eligible": copay + deductible > 200}


BILLING_STATEMENTS = {
    "P1001": [_statement("ST-55120", 21, "Dr. Chen", "Midtown Clinic", 640.00, 560.00, 900.00, 40.00, 260.00, 9)],
    "P1002": [_statement("ST-55121", 20, "Dr. Patel", "Eastside Clinic", 410.00, 290.00, 560.00, 0.00, 140.00, 12)],
    "P1003": [_statement("ST-55122", 30, "Dr. Chen", "Midtown Clinic", 380.00, 260.00, 400.00, 25.00, 215.00, 6)],
    "P1004": [_statement("ST-55123", 14, "Dr. Shah", "Midtown Clinic", 520.00, 430.00, 610.00, 50.00, 290.00, 10)],
}
