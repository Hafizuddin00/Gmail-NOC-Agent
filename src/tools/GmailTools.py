import os
import re
import uuid
import base64
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

class GmailToolsClass:
    def __init__(self):
        self.service = self._get_gmail_service()
        self._label_cache = {}  # cache label ID → name
        
    def fetch_unanswered_emails(self, max_results=50):
        """
        Fetches all emails included in unanswered threads.
        Also includes threads with existing drafts if the latest message
        contains .txt/.log attachments or pasted log content in the body.
        """
        try:
            from .LogDetector import is_log_content

            recent_emails = self.fetch_recent_emails(max_results)
            if not recent_emails: return []

            drafts = self.fetch_draft_replies()
            threads_with_drafts = {draft['threadId'] for draft in drafts}

            seen_threads = set()
            unanswered_emails = []
            for email in recent_emails:
                thread_id = email['threadId']
                if thread_id in seen_threads:
                    continue
                seen_threads.add(thread_id)

                email_info = self._get_email_info(email['id'])
                if self._should_skip_email(email_info):
                    continue

                if thread_id in threads_with_drafts:
                    # Only allow through if the message has attachments or log body
                    has_attachments = self._has_text_attachments(email['id'])
                    has_log_body = is_log_content(email_info.get('body', ''))
                    if not has_attachments and not has_log_body:
                        continue
                    email_info['force_log_analysis'] = True

                unanswered_emails.append(email_info)
            return unanswered_emails

        except Exception as e:
            print(f"An error occurred: {e}")
            return []

    def fetch_recent_emails(self, max_results=50):
        try:
            # Set delay of 5 minutes
            now = datetime.now()
            delay = now - timedelta(minutes=5)

            # Format for Gmail query
            after_timestamp = int(delay.timestamp())
            before_timestamp = int(now.timestamp())

            # Query to get emails from the last 5 minutes addressed to the NOC inbox
            query = f"after:{after_timestamp} before:{before_timestamp} "
            results = self.service.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
            messages = results.get("messages", [])
            
            return messages
        
        except Exception as error:
            print(f"An error occurred while fetching emails: {error}")
            return []
        
    def fetch_draft_replies(self):
        """
        Fetches all draft email replies from Gmail.
        """
        try:
            drafts = self.service.users().drafts().list(userId="me").execute()
            draft_list = drafts.get("drafts", [])
            return [
                {
                    "draft_id": draft["id"],
                    "threadId": draft["message"]["threadId"],
                    "id": draft["message"]["id"],
                }
                for draft in draft_list
            ]

        except Exception as error:
            print(f"An error occurred while fetching drafts: {error}")
            return []

    def create_draft_reply(self, initial_email, reply_text):
        try:
            # Create the reply message
            message = self._create_reply_message(initial_email, reply_text)

            # Create draft with thread information
            draft = self.service.users().drafts().create(
                userId="me", body={"message": message}
            ).execute()

            return draft
        except Exception as error:
            print(f"An error occurred while creating draft: {error}")
            return None

    def send_reply(self, initial_email, reply_text):
        try:
            # Create the reply message
            message = self._create_reply_message(initial_email, reply_text, send=True)

            # Send the message with thread ID
            sent_message = self.service.users().messages().send(
                userId="me", body=message
            ).execute()
            
            return sent_message

        except Exception as error:
            print(f"An error occurred while sending reply: {error}")
            return None
        
    def _create_reply_message(self, email, reply_text, send=False):
        # Create message with proper headers
        # Always address draft to the NOC inbox — never to the external sender
        message = self._create_html_email_message(
            recipient=os.environ.get("NOC_EMAIL", os.environ["MY_EMAIL"]),
            subject=email.subject,
            reply_text=reply_text
        )

        # Set threading headers
        if email.messageId:
            message["In-Reply-To"] = email.messageId
            # Combine existing references with the original message ID
            message["References"] = f"{email.references} {email.messageId}".strip()
            
            if send:
                # Generate a new Message-ID for this reply
                message["Message-ID"] = f"<{uuid.uuid4()}@gmail.com>"
                
        # Construct email body
        body = {
            "raw": base64.urlsafe_b64encode(message.as_bytes()).decode(),
            "threadId": email.threadId
        }

        return body

        
    def _get_gmail_service(self):
        # Resolve config/ relative to this file so the agent works regardless of cwd
        config_dir       = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
        token_path       = os.path.join(config_dir, "token.json")
        credentials_path = os.path.join(config_dir, "credentials.json")

        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow  = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)
    
    def _should_skip_email(self, email_info):
        sender = email_info['sender']

        # Skip own emails
        if os.environ['MY_EMAIL'] in sender:
            return True

        # Skip emails labelled "Provisioning Emails"
        if 'Provisioning Emails' in email_info.get('labels', []):
            print(f"  Skipping email with 'Provisioning Emails' label: {email_info['subject']}")
            return True

        # Skip emails from blocked senders listed in skipped_senders.txt
        skipped = self._load_skipped_senders()
        sender_lower = sender.lower()
        for blocked in skipped:
            if blocked in sender_lower:
                print(f"  Skipping email from blocked sender: {sender}")
                return True

        return False

    def _load_skipped_senders(self) -> list:
        """Load blocked sender list from config/skipped_senders.txt."""
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "skipped_senders.txt")
        if not os.path.exists(path):
            return []
        with open(path, "r") as f:
            return [
                line.strip().lower()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]

    def _resolve_label_names(self, label_ids: list) -> list:
        """Convert Gmail label IDs to human-readable label names, using a cache."""
        try:
            if not self._label_cache:
                result = self.service.users().labels().list(userId="me").execute()
                self._label_cache = {l["id"]: l["name"] for l in result.get("labels", [])}
            return [self._label_cache.get(lid, lid) for lid in label_ids]
        except Exception:
            return []

    def _has_text_attachments(self, msg_id: str) -> bool:
        """Check if a message has any .txt or .log attachments."""
        try:
            message = self.service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
            parts = message.get('payload', {}).get('parts', [])
            return self._check_parts_for_attachments(parts)
        except Exception:
            return False

    def _check_parts_for_attachments(self, parts: list) -> bool:
        """Recursively check parts for .txt/.log attachments."""
        for part in parts:
            filename = part.get('filename', '')
            if filename:
                ext = ('.' + filename.rsplit('.', 1)[-1].lower()) if '.' in filename else ''
                if ext in {'.txt', '.log'}:
                    return True
            if 'parts' in part:
                if self._check_parts_for_attachments(part['parts']):
                    return True
        return False

    def _get_email_info(self, msg_id):
        message = self.service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        payload = message.get('payload', {})
        headers = {header["name"].lower(): header["value"] for header in payload.get("headers", [])}

        # Resolve label IDs to label names
        label_ids = message.get("labelIds", [])
        label_names = self._resolve_label_names(label_ids)

        return {
            "id": msg_id,
            "threadId": message.get("threadId"),
            "messageId": headers.get("message-id"),
            "references": headers.get("references", ""),
            "sender": headers.get("from", "Unknown"),
            "subject": headers.get("subject", "No Subject"),
            "labels": label_names,
            "body": self._get_email_body(payload),
        }
    
    def _get_email_body(self, payload):
        """
        Extract the email body, prioritizing text/plain over text/html.
        Handles multipart messages, avoids duplicating content, and strips HTML if necessary.
        """
        def decode_data(data):
            """Decode base64-encoded data."""
            return base64.urlsafe_b64decode(data).decode('utf-8').strip() if data else ""

        def extract_body(parts):
            """Recursively extract text content from parts."""
            for part in parts:
                mime_type = part.get('mimeType', '')
                data = part['body'].get('data', '')
                if mime_type == 'text/plain':
                    return decode_data(data)
                if mime_type == 'text/html':
                    html_content = decode_data(data)
                    return self._extract_main_content_from_html(html_content)
                if 'parts' in part:
                    result = extract_body(part['parts'])
                    if result:
                        return result
            return ""

        # Process single or multipart payload
        if 'parts' in payload:
            body = extract_body(payload['parts'])
        else:
            data = payload['body'].get('data', '')
            body = decode_data(data)
            if payload.get('mimeType') == 'text/html':
                body = self._extract_main_content_from_html(body)

        return self._clean_body_text(body)

    def _extract_main_content_from_html(self, html_content):
        """
        Extract main visible content from HTML.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'head', 'meta', 'title']):
            tag.decompose()
        return soup.get_text(separator='\n', strip=True)

    def _clean_body_text(self, text):
        """
        Clean up the email body text by removing extra spaces and newlines.
        """
        return re.sub(r'\s+', ' ', text.replace('\r', '').replace('\n', '')).strip()
    
    def _create_html_email_message(self, recipient, subject, reply_text):
        """
        Creates a simple HTML email message with proper formatting and plaintext fallback.
        """
        message = MIMEMultipart("alternative")
        message["to"] = recipient
        base_subject = subject.removeprefix("Re: ").removeprefix("[DO NOT SEND] ")
        message["subject"] = f"[DO NOT SEND] Re: {base_subject}"

        # Simplified HTML Template
        html_text = reply_text.replace("\n", "<br>").replace("\\n", "<br>")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>{html_text}</body>
        </html>
        """

        html_part = MIMEText(html_content, "html")

        # message.attach(text_part)
        message.attach(html_part)

        return message