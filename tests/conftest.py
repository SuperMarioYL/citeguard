"""Test-time bootstrap.

The PDF fixture is rebuilt deterministically from `_build_pdf.py` on every
collection — that keeps the repository auditable (no opaque binary checked in)
and the test suite hermetic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_configure(config) -> None:  # noqa: ARG001
    spec = importlib.util.spec_from_file_location("_build_pdf", FIXTURES / "_build_pdf.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_build_pdf"] = module
    spec.loader.exec_module(module)
    pdf_bytes = module.build_pdf()
    (FIXTURES / "sample_paper.pdf").write_bytes(pdf_bytes)
