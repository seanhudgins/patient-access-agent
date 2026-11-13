"""Read secrets from the OS keychain first, then from environment variables.

Secrets live in macOS Keychain or Windows Credential Manager under the service "patient-access", so they
never sit in a file. Store one with (prompts for the value, so it stays out of shell history):

    uv run keyring set patient-access anthropic                  Claude API key
    uv run keyring set patient-access salesforce-client-id       Salesforce consumer key
    uv run keyring set patient-access salesforce-client-secret   Salesforce consumer secret
    uv run credentials.py store-google PATH/TO/key.json          Google service-account key (then delete the file)

The environment variable is a fallback for machines without a keychain entry (for example CI).
"""

import json
import os
import sys
from pathlib import Path

import keyring
from keyring.errors import KeyringError

SERVICE = "patient-access"
GOOGLE_ACCOUNT = "google-service-account"


def get_secret(account: str, env_var: str) -> str | None:
    """The secret stored under (SERVICE, account), else the env_var value, else None."""
    try:
        value = keyring.get_password(SERVICE, account)
    except KeyringError:
        value = None
    return value or os.environ.get(env_var) or None


def store_google(path: Path) -> str:
    """Validate a Google service-account key file and store its contents in the keychain."""
    info = json.loads(path.read_text(encoding="utf-8"))
    if info.get("type") != "service_account" or "private_key" not in info:
        raise ValueError(f"{path} is not a Google service-account key (expected type service_account)")
    keyring.set_password(SERVICE, GOOGLE_ACCOUNT, json.dumps(info, separators=(",", ":")))
    return info.get("client_email", "?")


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "store-google":
        try:
            email = store_google(Path(argv[2]).expanduser())
        except (OSError, ValueError, KeyringError) as e:
            print(f"Not stored: {e}", file=sys.stderr)
            return 1
        print(f"Stored the key for {email} in the keychain ({SERVICE} / {GOOGLE_ACCOUNT}).")
        print(f"Now delete the file: rm {argv[2]}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
