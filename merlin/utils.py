import hmac
import logging
import os
from datetime import datetime

import streamlit as st


def setup_logging():
    """Configure logging for the application."""
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create a log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"merlin_{timestamp}.log")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),  # Also log to console
        ],
    )

    # Create logger
    logger = logging.getLogger("merlin")
    logger.setLevel(logging.INFO)

    return logger


# Initialize logger
logger = setup_logging()


def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], os.getenv("PASSWORD")):
            logger.info("Successful login attempt")
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            logger.warning("Failed login attempt")
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


def set_layout():
    st.set_page_config(
        page_title="Merlin",
        page_icon="🧙‍♂️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
