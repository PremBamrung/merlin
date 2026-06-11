"""
Application service layer.

Framework-agnostic orchestration that the UI (and any future API/CLI) calls.
These modules must NOT import streamlit or any UI code — the dependency arrow
points one way: ui -> merlin.services -> merlin.{core,db,rag,knowledge_sources}.
"""
