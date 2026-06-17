import base64
from colorama import Fore, Style

SUPPORTED_MIME_TYPES = {
    "text/plain",
    "text/x-log",
    "application/octet-stream",  # sometimes .log files come as this
}

SUPPORTED_EXTENSIONS = {".txt", ".log"}


def extract_text_attachments(service, msg_id: str) -> str:
    """
    Fetches a Gmail message and extracts content from .txt and .log attachments.

    Returns a single string with all attachment contents concatenated,
    or an empty string if no supported attachments are found.
    """
    try:
        message = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        payload = message.get("payload", {})
        parts = payload.get("parts", [])

        extracted = []
        _process_parts(service, msg_id, parts, extracted)

        if extracted:
            print(Fore.CYAN + f"  [Attachments] Found {len(extracted)} text attachment(s)" + Style.RESET_ALL)
            return "\n\n".join(extracted)
        else:
            return ""

    except Exception as e:
        print(Fore.RED + f"  [Attachments] Error reading attachments: {e}" + Style.RESET_ALL)
        return ""


def _process_parts(service, msg_id: str, parts: list, extracted: list):
    """Recursively walk payload parts to find supported attachments."""
    for part in parts:
        filename = part.get("filename", "")
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})

        # Recurse into nested parts
        if "parts" in part:
            _process_parts(service, msg_id, part["parts"], extracted)
            continue

        # Check if this part is a supported attachment
        if not filename:
            continue

        ext = _get_extension(filename)
        is_supported = (
            ext in SUPPORTED_EXTENSIONS or
            mime_type in SUPPORTED_MIME_TYPES
        )

        if not is_supported:
            print(Fore.YELLOW + f"  [Attachments] Skipping unsupported attachment: {filename} ({mime_type})" + Style.RESET_ALL)
            continue

        # Get attachment data
        data = body.get("data")
        attachment_id = body.get("attachmentId")

        if data:
            # Inline data
            content = _decode_base64(data)
        elif attachment_id:
            # Fetch separately
            content = _fetch_attachment(service, msg_id, attachment_id, filename)
        else:
            continue

        if content:
            extracted.append(f"--- Attachment: {filename} ---\n{content}")


def _fetch_attachment(service, msg_id: str, attachment_id: str, filename: str) -> str:
    """Fetch an attachment by ID from Gmail API."""
    try:
        attachment = service.users().messages().attachments().get(
            userId="me", messageId=msg_id, id=attachment_id
        ).execute()
        return _decode_base64(attachment.get("data", ""))
    except Exception as e:
        print(Fore.RED + f"  [Attachments] Failed to fetch {filename}: {e}" + Style.RESET_ALL)
        return ""


def _decode_base64(data: str) -> str:
    """Decode base64url-encoded data to UTF-8 string."""
    try:
        decoded_bytes = base64.urlsafe_b64decode(data + "==")
        return decoded_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _get_extension(filename: str) -> str:
    """Return lowercase file extension including the dot."""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""
