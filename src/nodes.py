"""
Graph node implementations — each function maps to one node in the LangGraph workflow.
"""

import time
import json
import os
import logging

from google.api_core.exceptions import ResourceExhausted, TooManyRequests
from langchain_google_genai._common import GoogleGenerativeAIError as ChatGoogleGenerativeAIError

from .agents import Agents
from .tools.GmailTools import GmailToolsClass
from .tools.AttachmentParser import extract_text_attachments
from .tools.LogDetector import is_log_content
from .tools.CircuitLookup import lookup_circuit_from_email
# from .tools.GoogleChatTools import send_to_google_chat as chat_send  # enable when switching to Google Chat
from .state import GraphState, Email

logger = logging.getLogger(__name__)

SKIPPED_THREADS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "skipped_threads.json"
)

def load_skipped_threads() -> set:
    """Load the set of thread IDs that have been permanently skipped."""
    if os.path.exists(SKIPPED_THREADS_FILE):
        with open(SKIPPED_THREADS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_skipped_thread(thread_id: str):
    """Append a thread ID to the persistent skipped list."""
    skipped = load_skipped_threads()
    skipped.add(thread_id)
    with open(SKIPPED_THREADS_FILE, "w") as f:
        json.dump(list(skipped), f)


RATE_LIMIT_WAITS = [60, 120, 180, 300]  # seconds to wait on each retry attempt
RATE_LIMIT_EXCEPTIONS = (ResourceExhausted, TooManyRequests, ChatGoogleGenerativeAIError)


def call_with_retry(func, *args, label="Agent", **kwargs):
    """Call an agent function with retry on rate limit errors. Waits 60s+ between attempts."""
    max_retries = len(RATE_LIMIT_WAITS) + 1
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RATE_LIMIT_EXCEPTIONS as e:
            err_str = str(e)
            # Daily quota exhausted — no point retrying, raise immediately
            if "PerDay" in err_str or "per_day" in err_str or "limit: 20" in err_str:
                logger.error(f"[{label}] Daily quota exhausted. Cannot retry until tomorrow.")
                raise
            if attempt < len(RATE_LIMIT_WAITS):
                wait = RATE_LIMIT_WAITS[attempt]
                logger.warning(
                    f"[{label}] Rate limit hit. "
                    f"Waiting {wait}s before retry {attempt+1}/{len(RATE_LIMIT_WAITS)}..."
                )
                time.sleep(wait)
            else:
                logger.error(f"[{label}] Rate limit - max retries reached. Skipping.")
                raise


class Nodes:
    def __init__(self):
        self.agents = Agents()
        self.gmail_tools = GmailToolsClass()

    def load_new_emails(self, state: GraphState) -> GraphState:
        """Loads new emails from Gmail and updates the state."""
        logger.info("Loading new emails from Gmail inbox...")
        skipped_threads = load_skipped_threads()
        recent_emails = self.gmail_tools.fetch_unanswered_emails()

        emails = []
        for email in recent_emails:
            if email["threadId"] in skipped_threads:
                logger.debug(f"Skipping thread (in skip list): {email['threadId']}")
                continue
            # Extract .txt/.log attachments
            attachments = extract_text_attachments(self.gmail_tools.service, email["id"])
            email["attachments"] = attachments
            emails.append(Email(**email))

        logger.info(f"Loaded {len(emails)} new email(s) to process.")
        return {"emails": emails}

    def check_new_emails(self, state: GraphState) -> str:
        """Checks if there are new emails to process."""
        if len(state['emails']) == 0:
            logger.info("Inbox empty - no new emails to process.")
            return "empty"
        else:
            logger.info(f"Found {len(state['emails'])} email(s) to process.")
            return "process"

    def is_email_inbox_empty(self, state: GraphState) -> GraphState:
        return state

    def categorize_email(self, state: GraphState) -> GraphState:
        """Categorizes the current email. Forces log_analysis only for thread replies with logs."""
        logger.info("Categorizing current email...")

        current_email = state["emails"][-1]

        # Only force log_analysis for replies in threads that already have a draft
        if current_email.force_log_analysis:
            logger.info(
                "Email category: log_analysis "
                "(forced — reply in existing thread with log content)"
            )
            return {"email_category": "log_analysis", "current_email": current_email}

        # For all other emails — use LLM to categorize
        try:
            result = call_with_retry(
                self.agents.categorize_email.invoke,
                {"email": current_email.body},
                label="Categorize"
            )
        except RATE_LIMIT_EXCEPTIONS:
            logger.error("Categorization failed due to quota. Skipping email.")
            state["emails"].pop()
            return {"email_category": "unrelated", "current_email": current_email}

        category = result.category.value

        # If sender is from @evolutionwellness and not fortitoken, force general_inquiry
        sender = current_email.sender.lower()
        if "@evolutionwellness" in sender and category != "ewh_fortitoken":
            logger.info(
                f"Overriding category '{category}' → 'general_inquiry' "
                f"(evolutionwellness sender)"
            )
            category = "general_inquiry"
        else:
            logger.info(f"Email category: {category}")

        return {
            "email_category": category,
            "current_email": current_email
        }

    def route_email_based_on_category(self, state: GraphState) -> str:
        """Routes the email based on its category."""
        category = state["email_category"]
        logger.info(f"Routing email | category={category}")
        if category == "unrelated":
            return "unrelated"
        elif category == "log_analysis":
            return "log analysis"
        elif category == "circuit_down":
            return "circuit down"
        elif category == "link_flapping":
            return "link flapping"
        elif category == "packet_loss":
            return "packet loss"
        elif category == "maintenance_notification":
            return "maintenance notification"
        elif category == "general_inquiry":
            return "general inquiry"
        elif category == "ewh_fortitoken":
            return "ewh fortitoken"
        else:
            return "general inquiry"

    def construct_rag_queries(self, state: GraphState) -> GraphState:
        """Retrieves SOP docs from vectorstore and circuit details from CSV lookup."""
        logger.info("Retrieving information from internal knowledge base (RAG)...")
        email = state["current_email"]
        email_category = state["email_category"]

        # --- RAG: vectorstore search ---
        search_query = f"{email_category}: {email.body}"
        docs = self.agents.retriever.invoke(search_query)
        rag_text = "\n\n".join([doc.page_content for doc in docs])
        logger.info(f"RAG retrieved {len(docs)} document(s).")

        # --- Direct CSV lookup: no LLM, no embedding ---
        circuit_info = lookup_circuit_from_email(email.body, email.subject)
        if circuit_info:
            retrieved = f"{circuit_info}\n\n{rag_text}"
        else:
            retrieved = rag_text

        return {
            "rag_queries": [search_query],
            "retrieved_documents": retrieved
        }

    def retrieve_from_rag(self, state: GraphState) -> GraphState:
        """Placeholder — retrieval is now done in construct_rag_queries."""
        return state

    def write_draft_email(self, state: GraphState) -> GraphState:
        """Writes a draft NOC action procedure based on the current email and retrieved information."""
        logger.info("Writing NOC action procedure (draft email)...")

        # Format input to the writer agent
        email = state["current_email"]

        # Analyze attachments or log body content if present
        log_analysis = ""
        log_content = email.attachments or ""

        # Also check body for pasted logs (even if no attachment)
        if not log_content and is_log_content(email.body):
            log_content = email.body

        if log_content:
            logger.info("Log content detected - running log analysis...")
            try:
                log_analysis = call_with_retry(
                    self.agents.log_analyzer.invoke,
                    {"log_content": log_content, "email_category": state["email_category"]},
                    label="LogAnalyzer"
                )
            except Exception as e:
                logger.error(f"Log analysis failed: {e}", exc_info=True)

        attachment_section = (
            f'\n\n# **LOG CONTENT:**\n{log_content}'
            f'\n\n# **LOG ANALYSIS:**\n{log_analysis}'
            if log_content else ""
        )
        inputs = (
            f'# **EMAIL CATEGORY:** {state["email_category"]}\n\n'
            f'# **EMAIL CONTENT:**\n{email.body}'
            f'{attachment_section}\n\n'
            f'# **INFORMATION:**\n{state["retrieved_documents"]}'
        )

        writer_messages = state.get('writer_messages', [])

        category = state["email_category"]
        writer = self.agents.email_writers.get(category, self.agents.email_writers["general_inquiry"])

        draft_result = call_with_retry(
            writer.invoke,
            {"email_information": inputs, "category": category},
            label="Writer"
        )

        email = draft_result.email
        state["emails"].pop()

        logger.info("Draft email written successfully.")
        return {
            "generated_email": email,
            "trials": 0,
            "writer_messages": []
        }

    def write_log_analysis(self, state: GraphState) -> GraphState:
        """Runs log analysis directly — skips RAG, outputs findings only."""
        logger.info("Running direct log analysis (no RAG)...")

        email = state["current_email"]
        log_content = email.attachments or email.body

        analysis = call_with_retry(
            self.agents.log_analyzer.invoke,
            {"log_content": log_content, "email_category": "log_analysis"},
            label="LogAnalysis"
        )

        state["emails"].pop()
        logger.info("Log analysis complete.")
        return {
            "generated_email": analysis,
            "trials": 0,
            "writer_messages": []
        }

    def create_draft_response(self, state: GraphState) -> GraphState:
        """Creates a draft response in Gmail."""
        logger.info("Creating Gmail draft reply...")
        self.gmail_tools.create_draft_reply(state["current_email"], state["generated_email"])
        logger.info("Gmail draft created successfully.")
        return {"retrieved_documents": "", "trials": 0}

    # --- Google Chat (disabled) ---
    # REMOVE 'create_draft_response' above when enabling Google Chat 
    #
    # def send_to_google_chat(self, state: GraphState) -> GraphState:
    #     email = state["current_email"]
    #     logger.info(f"Sending procedure to Google Chat | subject={email.subject!r}")
    #     from .tools.GoogleChatTools import send_to_google_chat as chat_send
    #     success = chat_send(
    #         subject=email.subject,
    #         message_id=email.id,
    #         procedure=state["generated_email"],
    #     )
    #     if success:
    #         logger.info("Procedure sent to Google Chat successfully.")
    #     else:
    #         logger.error("Failed to send procedure to Google Chat.")
    #     return {"retrieved_documents": "", "trials": 0}

    def skip_unrelated_email(self, state):
        """Skip unrelated email permanently and remove from emails list."""
        email = state["emails"][-1]
        logger.info(f"Skipping unrelated email permanently | threadId={email.threadId}")
        save_skipped_thread(email.threadId)
        state["emails"].pop()
        return state