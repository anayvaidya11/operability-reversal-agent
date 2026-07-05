"""Pytest bootstrap: put the repository root on sys.path so tests can import the
`src` and `data` packages (e.g. `from src.risk_calculator import ...`,
`from data.validate import EUROSCORE_FIELDS`)."""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
