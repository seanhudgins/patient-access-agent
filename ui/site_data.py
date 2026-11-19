"""Display-only directory data for the website: provider profiles, locations and specialty pages.

Everything here is fictional and only drives page content. Facts Clara acts on (who sees what
specialty, referral rules, video visits) stay in mock_data.py / the data store, and facts Clara
states (hours, addresses, parking) stay in knowledge_base.py. Keep the three in agreement.
"""

PROVIDER_PROFILES = {
    "PRV-01": {"title": "MD · Family Medicine", "languages": ["English", "Mandarin"], "accepting": True,
               "bio": "Dr. Chen focuses on preventive care, chronic conditions like high blood pressure and diabetes, "
                      "and helping patients make a plan they can stick with."},
    "PRV-02": {"title": "MD · Internal Medicine", "languages": ["English", "Hindi", "Gujarati"], "accepting": True,
               "bio": "Dr. Patel cares for adults with complex and long-term conditions and leads the Eastside "
                      "Clinic's Heart Health at Home program."},
    "PRV-03": {"title": "MD · Orthopedic Surgery", "languages": ["English", "Spanish"], "accepting": True,
               "bio": "Dr. Reyes treats knee, shoulder and sports injuries, from physical therapy plans to surgery "
                      "when it's needed."},
    "PRV-04": {"title": "MD · Cardiology", "languages": ["English"], "accepting": True,
               "bio": "Dr. Reed treats high blood pressure, heart rhythm problems and heart failure, and reviews "
                      "home blood pressure readings with the care team."},
    "PRV-05": {"title": "MD · Dermatology", "languages": ["English", "Spanish"], "accepting": False,
               "bio": "Dr. Shah treats skin, hair and nail conditions and does annual skin checks. Currently seeing "
                      "established patients only."},
}

LOCATIONS = [
    {"slug": "midtown", "name": "Midtown Clinic", "address": "200 Capitol Avenue", "phone": "555-301-4100",
     "hours": "Monday–Friday 7:30 am–6:00 pm", "services": ["Primary care", "Orthopedics", "Dermatology", "Lab", "X-ray and imaging"],
     "parking": "Free garage on 2nd Street; validate your ticket at the front desk.",
     "transit": "Light rail: Capitol Station, two blocks east.", "accessible": "Step-free entrance on Capitol Avenue; elevators to all floors."},
    {"slug": "eastside", "name": "Eastside Clinic", "address": "4150 Folsom Boulevard", "phone": "555-301-4200",
     "hours": "Monday–Friday 7:30 am–6:00 pm", "services": ["Primary care", "Lab", "Heart Health at Home program"],
     "parking": "Free surface lot in front of the building, with accessible spaces by the entrance.",
     "transit": "Bus 30 stops at Folsom and 41st.", "accessible": "Single-story building with automatic doors."},
    {"slug": "heart-vascular", "name": "Heart & Vascular Center", "address": "5 Riverside Drive", "phone": "555-301-4300",
     "hours": "Monday–Friday 7:30 am–6:00 pm", "services": ["Cardiology", "Heart testing (EKG, echo, stress tests)"],
     "parking": "Free parking in Lot B.", "transit": "Bus 6 stops at Riverside and 5th.",
     "accessible": "Drop-off zone at the main entrance; wheelchairs available in the lobby."},
]

SPECIALTIES = {
    "primary-care": {"name": "Primary Care", "icon": "stethoscope",
                     "lede": "Your first stop for checkups, everyday illness and long-term conditions.",
                     "treats": ["Annual physicals and preventive care", "High blood pressure, diabetes and cholesterol",
                                "Colds, infections and minor injuries", "Referrals to specialists"],
                     "note": "No referral needed. Most providers also offer video visits."},
    "orthopedics": {"name": "Orthopedics", "icon": "bone",
                    "lede": "Care for bones, joints, muscles and sports injuries.",
                    "treats": ["Knee, hip and shoulder pain", "Sports injuries and sprains", "Arthritis", "Fractures (follow-up care)"],
                    "note": "New patients need a referral from a primary care provider. Clara checks this before booking."},
    "cardiology": {"name": "Cardiology", "icon": "heart",
                   "lede": "Heart and vascular care, including help managing blood pressure at home.",
                   "treats": ["High blood pressure", "Heart rhythm problems", "Heart failure", "Heart testing (EKG, echo, stress tests)"],
                   "note": "New patients need a referral from a primary care provider."},
    "dermatology": {"name": "Dermatology", "icon": "sun",
                    "lede": "Skin, hair and nail care, including annual skin checks.",
                    "treats": ["Rashes, acne and eczema", "Moles and skin checks", "Hair and nail conditions"],
                    "note": "No referral needed. Video visits available for many skin concerns."},
}
