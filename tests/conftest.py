from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    """
    Make Lambda-style sibling imports work locally.

    The deployed Lambda zip flattens `src/me_microservice/*` into `/var/task/`,
    so modules are imported as siblings (e.g., `from service import ...`).
    """

    module_dir = Path(__file__).resolve().parents[1] / "src" / "me_microservice"
    sys.path.insert(0, str(module_dir))

