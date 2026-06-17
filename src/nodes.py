"""
Graph node implementations — each function maps to one node in the LangGraph workflow.
"""

from colorama import Fore, Style
import time
import json
import os
from google.api_core.exceptions import ResourceExhausted, TooManyRequests
from langchain_google_genai._common import GoogleGenerativeAIError as ChatGoogleGenerativeAIError

from .agents import Agents
from .tools.GmailTools import GmailToolsClass
from .tools.AttachmentParser import extract_text_attachments
from .tools.LogDetector import is_log_content
from .state import GraphState, Email

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
                print(Fore.RED + f"[{label}] Daily quota exhausted. Cannot retry until tomorrow." + Style.RESET_ALL)
                raise
            if attempt < len(RATE_LIMIT_WAITS):
                wait = RATE_LIMIT_WAITS[attempt]
                print(Fore.RED + f"[{label}] Rate limit hit. Waiting {wait}s before retry {attempt+1}/{len(RATE_LIMIT_WAITS)}..." + Style.RESET_ALL)
                time.sleep(wait)
            else:
                print(Fore.RED + f"[{label}] Rate limit — max retries reached. Skipping." + Style.RESET_ALL)
                raise


class Nodes:
    def __init__(self):
        self.agents = Agents()
        self.gmail_tools = GmailToolsClass()

    def load_new_emails(self, state: GraphState) -> GraphState:
        """Loads new emails from Gmail and updates the state."""
        print(Fore.YELLOW + "Loading new emails...\n" + Style.RESET_ALL)
        skipped_threads = load_skipped_threads()
        recent_emails = self.gmail_tools.fetch_unanswered_emails()

        emails = []
        for email in recent_emails:
            if email["threadId"] in skipped_threads:
                continue
            # Extract .txt/.log attachments
            attachments = extract_text_attachments(self.gmail_tools.service, email["id"])
            email["attachments"] = attachments
            emails.append(Email(**email))

        return {"emails": emails}

    def check_new_emails(self, state: GraphState) -> str:
        """Checks if there are new emails to process."""
        if len(state['emails']) == 0:
            print(Fore.RED + "No new emails" + Style.RESET_ALL)
            return "empty"
        else:
            print(Fore.GREEN + "New emails to process" + Style.RESET_ALL)
            return "process"
        
    def is_email_inbox_empty(self, state: GraphState) -> GraphState:
        return state

    def categorize_email(self, state: GraphState) -> GraphState:
        """Categorizes the current email. Forces log_analysis only for thread replies with logs."""
        print(Fore.YELLOW + "Checking email category...\n" + Style.RESET_ALL)

        current_email = state["emails"][-1]

        # Only force log_analysis for replies in threads that already have a draft
        # (i.e. no new issue — just a log follow-up)
        if current_email.force_log_analysis:
            print(Fore.MAGENTA + "Email category: log_analysis (forced — reply in existing thread with log content)" + Style.RESET_ALL)
            return {"email_category": "log_analysis", "current_email": current_email}

        # For all other emails — use LLM to categorize
        try:
            result = call_with_retry(
                self.agents.categorize_email.invoke,
                {"email": current_email.body},
                label="Categorize"
            )
        except RATE_LIMIT_EXCEPTIONS:
            print(Fore.RED + "Categorization failed due to quota. Skipping email.\n" + Style.RESET_ALL)
            state["emails"].pop()
            return {"email_category": "unrelated", "current_email": current_email}

        print(Fore.MAGENTA + f"Email category: {result.category.value}" + Style.RESET_ALL)

        category = result.category.value

        # If sender is from @evolutionwellness and not fortitoken, force general_inquiry
        sender = current_email.sender.lower()
        if "@evolutionwellness" in sender and category != "ewh_fortitoken":
            print(Fore.MAGENTA + "Overriding category to general_inquiry (evolutionwellness sender)" + Style.RESET_ALL)
            category = "general_inquiry"

        return {
            "email_category": category,
            "current_email": current_email
        }

    def route_email_based_on_category(self, state: GraphState) -> str:
        """Routes the email based on its category."""
        print(Fore.YELLOW + "Routing email based on category...\n" + Style.RESET_ALL)
        category = state["email_category"]
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
        """Constructs RAG queries and retrieves information in one step."""
        print(Fore.YELLOW + "Retrieving information from internal knowledge...\n" + Style.RESET_ALL)
        email_content = state["current_email"].body
        email_category = state["email_category"]

        # Use email body + category directly as the search query — no LLM call needed
        search_query = f"{email_category}: {email_content}"
        docs = self.agents.retriever.invoke(search_query)
        retrieved = "\n\n".join([doc.page_content for doc in docs])

        return {
            "rag_queries": [search_query],
            "retrieved_documents": retrieved
        }

    def retrieve_from_rag(self, state: GraphState) -> GraphState:
        """Placeholder — retrieval is now done in construct_rag_queries."""
        return state

    def write_draft_email(self, state: GraphState) -> GraphState:
        """Writes a draft NOC action procedure based on the current email and retrieved information."""
        print(Fore.YELLOW + "Writing NOC action procedure...\n" + Style.RESET_ALL)
        
        # Format input to the writer agent
        email = state["current_email"]

        # Analyze attachments or log body content if present
        log_analysis = ""
        log_content = email.attachments or ""

        # Also check body for pasted logs (even if no attachment)
        if not log_content and is_log_content(email.body):
            log_content = email.body

        if log_content:
            print(Fore.CYAN + "Analyzing log content...\n" + Style.RESET_ALL)
            try:
                log_analysis = call_with_retry(
                    self.agents.log_analyzer.invoke,
                    {"log_content": log_content, "email_category": state["email_category"]},
                    label="LogAnalyzer"
                )
            except Exception as e:
                print(Fore.RED + f"Log analysis failed: {e}" + Style.RESET_ALL)

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

        return {
            "generated_email": email,
            "trials": 0,
            "writer_messages": []
        }

    def write_log_analysis(self, state: GraphState) -> GraphState:
        """Runs log analysis directly — skips RAG, outputs findings only."""
        print(Fore.CYAN + "Running log analysis...\n" + Style.RESET_ALL)

        email = state["current_email"]
        log_content = email.attachments or email.body

        analysis = call_with_retry(
            self.agents.log_analyzer.invoke,
            {"log_content": log_content, "email_category": "log_analysis"},
            label="LogAnalysis"
        )

        state["emails"].pop()
        return {
            "generated_email": analysis,
            "trials": 0,
            "writer_messages": []
        }

    def create_draft_response(self, state: GraphState) -> GraphState:
        """Creates a draft response in Gmail."""
        print(Fore.YELLOW + "Creating draft email...\n" + Style.RESET_ALL)
        self.gmail_tools.create_draft_reply(state["current_email"], state["generated_email"])
        return {"retrieved_documents": "", "trials": 0}
    
    def skip_unrelated_email(self, state):
        """Skip unrelated email permanently and remove from emails list."""
        email = state["emails"][-1]
        print(Fore.RED + f"Skipping unrelated email permanently: {email.threadId}\n" + Style.RESET_ALL)
        save_skipped_thread(email.threadId)
        state["emails"].pop()
        return state