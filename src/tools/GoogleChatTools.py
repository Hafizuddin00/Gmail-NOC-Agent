"""
src/tools/GoogleChatTools.py
-----------------------------
Sends formatted NOC procedure messages to a Google Chat space
via an Incoming Webhook.

Set GOOGLE_CHAT_WEBHOOK_URL in your .env file.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

# Gmail base URL for direct email links
GMAIL_LINK_BASE = "https://mail.google.com/mail/u/0/#all/{message_id}"


def build_gmail_link(message_id: str) -> str:
    """Return a direct link to the email in Gmail."""
    return GMAIL_LINK_BASE.format(message_id=message_id)


def send_to_google_chat(subject: str, message_id: str, procedure: str) -> bool:
    """
    Send a formatted NOC procedure card to Google Chat.

    Parameters
    ----------
    subject    : Email subject line
    message_id : Gmail message ID (used to build the direct link)
    procedure  : The generated NOC action procedure text

    Returns True on success, False on failure.
    """
    webhook_url = os.getenv("GOOGLE_CHAT_WEBHOOK_URL")
    if not webhook_url:
        logger.error("GOOGLE_CHAT_WEBHOOK_URL is not set in .env — cannot send to Google Chat.")
        return False

    email_link = build_gmail_link(message_id)

    # Truncate procedure if extremely long to stay under Chat API limits (~4000 chars)
    max_procedure_len = 3800
    if len(procedure) > max_procedure_len:
        procedure = procedure[:max_procedure_len] + "\n\n... (truncated)"

    # Build the message payload using Google Chat card format (v2 cards)
    payload = {
        "cardsV2": [
            {
                "cardId": f"noc-procedure-{message_id}",
                "card": {
                    "header": {
                        "title": "NOC Procedure",
                        "subtitle": subject,
                        "imageUrl": "https://fonts.gstatic.com/s/i/googlematerialicons/mail/v6/white-24dp/1x/gm_mail_white_24dp.png",
                        "imageType": "CIRCLE"
                    },
                    "sections": [
                        {
                            "header": "Email",
                            "widgets": [
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "Open Email in Gmail",
                                                "onClick": {
                                                    "openLink": {
                                                        "url": email_link
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        },
                        {
                            "header": "Procedure",
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": procedure.replace("\n", "<br>")
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Procedure sent to Google Chat for email: {subject!r}")
        return True
    except requests.exceptions.HTTPError as e:
        logger.error(f"Google Chat webhook returned an error: {e} | response: {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to reach Google Chat webhook: {e}")
        return False
