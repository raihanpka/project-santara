"""pytest bootstrap for the rpc-contracts integration test.

ponytail: prepend the package's python/ directory to sys.path so the
generated stubs are importable without a setup.py install step.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_DIR = Path(__file__).resolve().parent.parent / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))
