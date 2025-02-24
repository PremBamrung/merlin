"""
This is the entry point for uvicorn to run the FastAPI application.
The actual application is defined in backend.app.main
"""

from backend.app.main import app

# This allows uvicorn to import the app directly:
# uvicorn main:app --reload
