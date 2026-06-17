"""
Agent chains — wraps all LLM calls used by the graph nodes.
"""

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser

from .schemas import CategorizeEmailOutput, RAGQueriesOutput, WriterOutput
from .prompts import (
    CATEGORIZE_EMAIL_PROMPT,
    GENERATE_RAG_QUERIES_PROMPT,
    LOG_ANALYSIS_PROMPT,
    WRITER_PROMPTS,
)


class Agents:
    def __init__(self):
        # ── LLM ───────────────────────────────────────────────────────────────
        gemini = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)

        # ── Vector store / retriever ──────────────────────────────────────────
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        vectorstore = Chroma(persist_directory="db", embedding_function=embeddings)
        self.retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

        # ── Categorize email chain ────────────────────────────────────────────
        self.categorize_email = (
            PromptTemplate(template=CATEGORIZE_EMAIL_PROMPT, input_variables=["email"])
            | gemini.with_structured_output(CategorizeEmailOutput)
        )

        # ── RAG query designer (kept for potential future use) ─────────────────
        self.design_rag_queries = (
            PromptTemplate(template=GENERATE_RAG_QUERIES_PROMPT, input_variables=["email"])
            | gemini.with_structured_output(RAGQueriesOutput)
        )

        # ── Log analyzer ──────────────────────────────────────────────────────
        self.log_analyzer = (
            PromptTemplate(
                template=LOG_ANALYSIS_PROMPT,
                input_variables=["log_content", "email_category"],
            )
            | gemini
            | StrOutputParser()
        )

        # ── Per-category writer chains ────────────────────────────────────────
        # Each category only receives its own prompt; falls back to general_inquiry.
        self.email_writers = {
            category: (
                PromptTemplate(
                    template=prompt_text,
                    input_variables=["email_information", "category"],
                )
                | gemini.with_structured_output(WriterOutput)
            )
            for category, prompt_text in WRITER_PROMPTS.items()
        }