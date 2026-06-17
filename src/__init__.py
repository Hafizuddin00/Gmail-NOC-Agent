"""
src/ — core LangGraph agent package.

Modules:
  state     — GraphState TypedDict and Email Pydantic model
  schemas   — Pydantic schemas for all structured LLM outputs
  prompts/  — Prompt templates split by concern
  agents    — LLM chain definitions
  nodes     — LangGraph node implementations
  graph     — Workflow graph assembly
  tools/    — Gmail, attachment, and log-detection utilities
"""
