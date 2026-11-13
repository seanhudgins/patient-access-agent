"""Read secrets from the OS keychain first, then from environment variables.

Keys live in macOS Keychain or Windows Credential Manager under the service "patient-access", so they
never sit in a file. Store one with (prompts for the value, so it stays out of shell history):

    uv run keyring set patient-access anthropic
    uv run keyring set patient-access salesforce-client-secret

The environment variable is a fallback for machines without a keychain entry (for example CI).
"""

import os

import keyring
from keyring.errors import KeyringError

SERVICE = "patient-access"


def get_secret(account: str, env_var: str) -> str | None:
    """The secret stored under (SERVICE, account), else the env_var value, else None."""
    try:
        value = keyring.get_password(SERVICE, account)
    except KeyringError:
        value = None
    return value or os.environ.get(env_var) or None
