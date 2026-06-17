"""
Pydantic schemas for all structured LLM outputs used across the agent pipeline.
"""

from pydantic import BaseModel, Field
from typing import List
from enum import Enum


# ── Email Categorization ───────────────────────────────────────────────────────

class EmailCategory(str, Enum):
    circuit_down             = "circuit_down"
    link_flapping            = "link_flapping"
    packet_loss              = "packet_loss"
    maintenance_notification = "maintenance_notification"
    general_inquiry          = "general_inquiry"
    ewh_fortitoken           = "ewh_fortitoken"
    log_analysis             = "log_analysis"
    unrelated                = "unrelated"


class CategorizeEmailOutput(BaseModel):
    category: EmailCategory = Field(
        ...,
        description="The category assigned to the email, indicating its type based on predefined rules.",
    )


# ── RAG Query Generation ───────────────────────────────────────────────────────

class RAGQueriesOutput(BaseModel):
    queries: List[str] = Field(
        ...,
        description="A list of up to three questions representing the customer's intent, based on their email.",
    )


# ── NOC Procedure Writer ───────────────────────────────────────────────────────

class WriterOutput(BaseModel):
    email: str = Field(
        ...,
        description=(
            "The internal step-by-step NOC action procedure drafted in response "
            "to the incoming request, following the INTERNAL NOC ACTION PROCEDURE format."
        ),
    )


# ── Proofreader ────────────────────────────────────────────────────────────────

class ProofReaderOutput(BaseModel):
    feedback: str = Field(
        ...,
        description="Detailed feedback explaining why the email is or is not sendable.",
    )
    send: bool = Field(
        ...,
        description="Indicates whether the email is ready to be sent (true) or requires rewriting (false).",
    )
