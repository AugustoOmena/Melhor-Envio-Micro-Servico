from __future__ import annotations

import os
import sys


def pytest_configure() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.path.join(root, "src", "auth"))
    sys.path.insert(0, os.path.join(root, "src", "cart"))
    sys.path.insert(0, os.path.join(root, "src", "shared"))

