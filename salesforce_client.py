"""Salesforce integration (DATA_BACKEND=salesforce): staff handoffs become Cases.

Cases are created through the AssistantActionService Apex REST class in salesforce/,
so every case the assistant opens is stamped with its source.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

from credentials import get_secret

SF_API_VERSION = "v59.0"
# URL mapping of the Apex REST class that creates cases (/services/apexrest/<mapping>/)
SF_CASE_ENDPOINT = os.environ.get("SALESFORCE_CASE_ENDPOINT", "AssistantActions")
_token_cache: dict = {}


# ── OAuth ─────────────────────────────────────────────────────────────────────
def _get_access_token() -> str:
    """Fetch a Salesforce OAuth token using client credentials, with in-process caching."""
    if _token_cache.get("access_token") and _token_cache.get("expires_at", 0) > time.time() + 60:
        return _token_cache["access_token"]

    instance = os.environ["SALESFORCE_INSTANCE_URL"]
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ["SALESFORCE_CLIENT_ID"],
        "client_secret": get_secret("salesforce-client-secret", "SALESFORCE_CLIENT_SECRET") or "",
    }).encode()
    req = urllib.request.Request(
        f"{instance}/services/oauth2/token", data=data, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read())

    _token_cache.update({
        "access_token": body["access_token"],
        "expires_at": time.time() + 3500,  # SF default session = 1 hour
    })
    return body["access_token"]


def _sf_apex_post(url_suffix: str, payload: dict) -> str:
    """POST to a custom Apex REST endpoint. Returns the response body as a string."""
    instance = os.environ["SALESFORCE_INSTANCE_URL"]
    token = _get_access_token()
    url = f"{instance}/services/apexrest/{url_suffix}/"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ── Public API ────────────────────────────────────────────────────────────────
def create_case_sf(subject: str, description: str, priority: str = "Medium") -> dict:
    """Create a Salesforce Case through the Apex REST class. Returns the new case number."""
    try:
        apex_payload = {
            "actionType": "CREATE_CASE",
            "params": {"subject": subject, "description": description, "priority": priority},
        }
        result_str = _sf_apex_post(SF_CASE_ENDPOINT, apex_payload)
        if result_str.startswith("SUCCESS"):
            match = re.search(r"Created Case (\S+)", result_str)
            case_number = match.group(1) if match else "unknown"
            return {"success": True, "case_number": case_number}
        return {"success": False, "error": result_str}

    except Exception as e:
        return {"success": False, "error": str(e)}
