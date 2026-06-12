"""Merlin FastAPI layer.

A thin HTTP skin over `merlin.services` for the v3 React frontend (`web/`).
Routers validate input, call exactly one service function, and serialise the
plain dict the service already returns — no business logic lives here. The core
library (`merlin/`) is never modified or imported-around.
"""
