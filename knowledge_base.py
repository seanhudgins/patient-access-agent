"""Sierra Valley Health policies, injected verbatim into the system prompt on every request.

Grace answers general questions only from this text, so every fact a caller might
ask about (hours, addresses, parking, insurance) has to live here.
"""
KNOWLEDGE_BASE = {
    "emergencies": (
        "For a medical emergency, call 911 or go to the nearest emergency room. For thoughts of suicide or self-harm, "
        "call or text 988 (Suicide & Crisis Lifeline), available 24/7. Grace never queues an emergency."
    ),
    "hours": (
        "Clinics: Monday-Friday 7:30am-6:00pm. Patient Access Center (phone and chat): Monday-Friday 7:00am-7:00pm, "
        "Saturday 8:00am-12:00pm. Nurse line callbacks happen during clinic hours. Closed on major holidays."
    ),
    "locations": (
        "Midtown Clinic, 200 Capitol Avenue (Primary Care with Dr. Chen, Orthopedics with Dr. Reyes, Dermatology with Dr. Shah, lab). "
        "Eastside Clinic, 4150 Folsom Boulevard (Primary Care with Dr. Patel, lab). "
        "Heart & Vascular Center, 5 Riverside Drive (Cardiology with Dr. Reed)."
    ),
    "parking": (
        "Midtown Clinic: free patient parking in the garage on 2nd Street; bring your ticket to the front desk for validation. "
        "Eastside Clinic: free surface lot in front of the building. Heart & Vascular Center: free parking in Lot B. "
        "All locations have accessible spaces next to the entrance and drop-off zones."
    ),
    "visit_preparation": (
        "Arrive 15 minutes early for in-person visits (30 minutes for a first visit with a new provider). Bring a photo ID, "
        "your insurance card, and a list of your current medications. Telehealth: the video link is sent by text and email "
        "1 hour before; join from a quiet, private place. Fasting or other prep instructions come from your provider's office."
    ),
    "appointments": (
        "Book, reschedule or cancel by phone, chat, or the patient portal. Cancel or reschedule at least 24 hours ahead; "
        "later cancellations and no-shows carry a $50 fee. Orthopedics and Cardiology require a referral from a primary "
        "care provider for new patients. Appointment IDs look like APT-2001."
    ),
    "prescription_refills": (
        "Refill requests go to the prescribing provider for review and are answered within 2 business days. A request is "
        "not an approval: the provider may approve it, ask for a visit first, or decline. Approved refills are sent to the "
        "patient's preferred pharmacy. Request refills when you have at least 5 days of medication left. Controlled "
        "substances can't be requested through the assistant; the provider's office handles them."
    ),
    "insurance": (
        "In network with Medicare, Medi-Cal, Blue Horizon PPO, Sierra Select HMO, Aetna, Cigna, and UnitedHealthcare. "
        "HMO members may need a referral for specialists. Coverage for a specific service depends on the patient's plan, "
        "so patients should confirm benefits with their insurer."
    ),
    "patient_portal": (
        "The MySierra patient portal shows visit summaries, test results, and messages, and supports appointment booking. "
        "Password reset: go to mysierra.example.org, choose 'Forgot password', and enter your email; the reset link expires "
        "after 30 minutes. If you no longer have access to that email, or your account is locked after 5 failed attempts, "
        "the Patient Access team can unlock it after verifying your identity."
    ),
    "billing": (
        "Statements are mailed and posted to the portal monthly. Interest-free payment plans are available for balances "
        "over $200. Grace does not handle billing disputes or charge corrections; those go to the billing team."
    ),
}


def get_kb_summaries() -> str:
    lines = []
    for key, value in KNOWLEDGE_BASE.items():
        label = key.replace("_", " ").title()
        lines.append(f"- {label}: {value}")
    return "\n".join(lines)
