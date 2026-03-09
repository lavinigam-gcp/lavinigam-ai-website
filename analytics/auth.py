"""OAuth2 authentication for GA4 and Search Console APIs.

First run opens a browser for consent and saves the token locally.
Subsequent runs reuse the saved token, refreshing automatically.
"""

import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

# Credentials stored alongside the script (gitignored)
_CREDS_DIR = os.path.join(os.path.dirname(__file__), ".credentials")
_TOKEN_PATH = os.path.join(_CREDS_DIR, "token.json")
_CLIENT_SECRET_PATH = os.path.expanduser(
    "~/.config/gcloud/analytics-client-secret.json"
)


def get_credentials() -> Credentials:
    """Return valid OAuth2 credentials, prompting for login if needed."""
    creds = None

    # Load existing token
    if os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)

    # Refresh or run new OAuth flow
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not os.path.exists(_CLIENT_SECRET_PATH):
            raise FileNotFoundError(
                f"OAuth client secret not found at {_CLIENT_SECRET_PATH}\n"
                "Download it from: https://console.cloud.google.com/apis/credentials"
                f"?project=kaggle-on-gcp\n"
                f"Save as: {_CLIENT_SECRET_PATH}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            _CLIENT_SECRET_PATH, SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save for next run
        os.makedirs(_CREDS_DIR, exist_ok=True)
        with open(_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds
