"""Pytest configuration for the python client package.

Pytest's rootdir discovery may pick the repo root (platform-backend/) instead of
python-client/, which makes `import mip` fail during test
collection. Ensure the python-client directory is importable.
"""

from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
