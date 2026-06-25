"""
src/tools/GoogleSheetsFortiToken.py
-----------------------------------
Automates FortiToken provisioning workflow by:
1. Validating user data in "All Users" sheet
2. Appending validated tasks to "Actions Queue" sheet

Requires Google Sheets API enabled on the same OAuth project as Gmail.
"""

import os
import logging
from typing import Optional, Dict
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

logger = logging.getLogger(__name__)

# Sheet ID loaded from .env
SHEET_ID = os.getenv("FORTITOKEN_SHEET_ID", "")

# Sheet names
ALL_USERS_SHEET = "All Users"
ACTIONS_QUEUE_SHEET = "Actions Queue"

# OAuth scopes (reuses same token.json as Gmail if Sheets scope is added)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/spreadsheets'
]


def _get_sheets_service():
    """Get authenticated Google Sheets API service using existing Gmail OAuth token."""
    config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
    token_path = os.path.join(config_dir, "token.json")
    credentials_path = os.path.join(config_dir, "credentials.json")

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If credentials expired or missing Sheets scope, re-authorize
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)


def _read_all_users(service) -> Dict[str, Dict[str, str]]:
    """
    Read "All Users" sheet and return a dict keyed by lowercase username.
    Returns: {username_lower: {"email": "...", "group": "..."}}
    """
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{ALL_USERS_SHEET}!A:C"
    ).execute()

    rows = result.get("values", [])
    if not rows or len(rows) < 2:
        return {}

    users = {}
    for row in rows[1:]:  # skip header
        if len(row) < 3:
            continue
        username, group, email = row[0].strip(), row[1].strip(), row[2].strip()
        if username:
            users[username.lower()] = {"email": email.lower(), "group": group}

    return users


def validate_and_queue_fortitoken(
    username: str,
    email: str,
    action: str
) -> tuple[bool, str]:
    """
    Validate FortiToken request against "All Users" sheet and append to "Actions Queue".

    Parameters
    ----------
    username : User's username (case-insensitive)
    email    : User's email address (case-insensitive)
    action   : Action keyword: "add", "resend", or "offboard-delete"

    Returns (success: bool, message: str)
    """
    try:
        service = _get_sheets_service()
        logger.info(f"FortiToken: validating {username} / {email} / {action}")

        # Normalize inputs
        username_lower = username.strip().lower()
        email_lower = email.strip().lower()
        action_lower = action.strip().lower()

        # Normalize action aliases
        if action_lower in ("delete", "offboard"):
            action_lower = "offboard-delete"

        # Read All Users database
        users = _read_all_users(service)

        # Step 1: Check if username exists
        if username_lower not in users:
            msg = f"Username '{username}' not found in 'All Users' sheet."
            logger.error(f"FortiToken validation failed: {msg}")
            return False, msg

        user_data = users[username_lower]

        # Step 2: Validate email match
        if user_data["email"] != email_lower:
            msg = f"Email mismatch for '{username}': expected '{user_data['email']}', got '{email}'."
            logger.error(f"FortiToken validation failed: {msg}")
            return False, msg

        # Step 3: Validate group naming convention
        group = user_data["group"]
        if not group:
            msg = f"Group is blank for user '{username}'."
            logger.error(f"FortiToken validation failed: {msg}")
            return False, msg

        # Valid groups — whatever the sheet says must be one of these two
        VALID_GROUPS = {"EWH-LOCAL-FTK", "EWH-VENDOR-FTK"}
        if group not in VALID_GROUPS:
            msg = f"Group '{group}' for user '{username}' is not a recognised FortiToken group (expected one of {VALID_GROUPS})."
            logger.error(f"FortiToken validation failed: {msg}")
            return False, msg

        # Step 4: Append to Actions Queue
        values = [[action_lower, username, email, group]]
        body = {"values": values}

        service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=f"{ACTIONS_QUEUE_SHEET}!A:D",
            valueInputOption="RAW",
            body=body
        ).execute()

        logger.info(
            f"FortiToken: successfully queued {action_lower} for {username} (group: {group})"
        )
        return True, f"Validated and queued: {action_lower} for {username} ({email}), group {group}"

    except Exception as e:
        msg = f"FortiToken workflow error: {e}"
        logger.error(msg, exc_info=True)
        return False, msg
