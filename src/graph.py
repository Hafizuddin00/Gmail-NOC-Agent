"""
LangGraph workflow — assembles nodes into the email-processing state graph.
"""

from langgraph.graph import END, StateGraph
from .state import GraphState
from .nodes import Nodes

class Workflow():
    def __init__(self):
        # initiate graph state & nodes
        workflow = StateGraph(GraphState)
        nodes = Nodes()

        # define all graph nodes
        workflow.add_node("load_inbox_emails", nodes.load_new_emails)
        workflow.add_node("is_email_inbox_empty", nodes.is_email_inbox_empty)
        workflow.add_node("categorize_email", nodes.categorize_email)
        workflow.add_node("construct_rag_queries", nodes.construct_rag_queries)
        workflow.add_node("retrieve_from_rag", nodes.retrieve_from_rag)
        workflow.add_node("email_writer", nodes.write_draft_email)
        workflow.add_node("log_analysis_writer", nodes.write_log_analysis)
        workflow.add_node("send_email", nodes.create_draft_response)
#        workflow.add_node("send_to_google_chat", nodes.send_to_google_chat)
        workflow.add_node("skip_unrelated_email", nodes.skip_unrelated_email)

        # load inbox emails
        workflow.set_entry_point("load_inbox_emails")

        # check if there are emails to process
        workflow.add_edge("load_inbox_emails", "is_email_inbox_empty")
        workflow.add_conditional_edges(
            "is_email_inbox_empty",
            nodes.check_new_emails,
            {
                "process": "categorize_email",
                "empty": END
            }
        )

        # route email based on category
        workflow.add_conditional_edges(
            "categorize_email",
            nodes.route_email_based_on_category,
            {
                "circuit down": "construct_rag_queries",
                "link flapping": "construct_rag_queries",
                "packet loss": "construct_rag_queries",
                "maintenance notification": "construct_rag_queries",
                "general inquiry": "construct_rag_queries",
                "ewh fortitoken": "construct_rag_queries",
                "log analysis": "log_analysis_writer",
                "unrelated": "skip_unrelated_email"
            }
        )

        # pass constructed queries to RAG chain to retrieve information
        workflow.add_edge("construct_rag_queries", "retrieve_from_rag")
        # give information to writer agent to create draft email
        workflow.add_edge("retrieve_from_rag", "email_writer")
        # writer sends directly to draft
        workflow.add_edge("email_writer", "send_email")
        workflow.add_edge("log_analysis_writer", "send_email")
#        # writer sends to Google Chat
#        workflow.add_edge("email_writer", "send_to_google_chat")
#        workflow.add_edge("log_analysis_writer", "send_to_google_chat")

        # check if there are still emails to be processed
        workflow.add_edge("send_email", "is_email_inbox_empty")
#        workflow.add_edge("send_to_google_chat", "is_email_inbox_empty")
        workflow.add_edge("skip_unrelated_email", "is_email_inbox_empty")

        # Compile
        self.app = workflow.compile()