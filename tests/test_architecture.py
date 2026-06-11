"""
Architecture boundary guard.

The core library (`merlin/`) must never import Streamlit or the UI layer.
The dependency arrow points one way:  ui -> merlin.services -> merlin.{...}.
"""

from pathlib import Path
import re

_ROOT = Path(__file__).parent.parent
_MERLIN = _ROOT / "merlin"

_FORBIDDEN = re.compile(r"^\s*(import|from)\s+(streamlit|ui)\b", re.MULTILINE)


def test_core_never_imports_streamlit_or_ui():
    offenders = []
    for py in _MERLIN.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if _FORBIDDEN.search(text):
            offenders.append(str(py.relative_to(_ROOT)))
    assert not offenders, (
        "merlin/ must not import streamlit or ui — offenders: " + ", ".join(offenders)
    )
