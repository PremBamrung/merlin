"""
Architecture boundary guard.

The core library (`merlin/`) must never import a web framework or the API layer.
The dependency arrow points one way:  api -> merlin.services -> merlin.{...}.
"""

from pathlib import Path
import re

_ROOT = Path(__file__).parent.parent
_MERLIN = _ROOT / "merlin"

_FORBIDDEN = re.compile(r"^\s*(import|from)\s+(streamlit|fastapi|api)\b", re.MULTILINE)


def test_core_never_imports_web_framework_or_api():
    offenders = []
    for py in _MERLIN.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if _FORBIDDEN.search(text):
            offenders.append(str(py.relative_to(_ROOT)))
    assert not offenders, (
        "merlin/ must not import streamlit, fastapi, or api — offenders: "
        + ", ".join(offenders)
    )
