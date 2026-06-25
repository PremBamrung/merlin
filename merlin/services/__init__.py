"""
Application service layer.

Framework-agnostic orchestration that the API (and any future CLI) calls.
These modules must NOT import fastapi or any API/UI code — the dependency arrow
points one way: api -> merlin.services -> merlin.{core,db,rag,knowledge_sources}.
"""
