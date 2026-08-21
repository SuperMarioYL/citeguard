"""Version-consistency regression tests (m6_preflight_lint extension, v0.6.0).

Covers `fix-init-version-drift-vs-pyproject`:
  * `citeguard.__version__` must equal the `pyproject.toml` version (the
    user-visible defect was `citeguard --version` printing a stale version on
    a 0.5.0 install because `__init__.py` was stuck at `0.4.0`), and
  * `scripts/check_version.py` must fail the gate when `__init__.py` drifts
    from `pyproject.toml`.  Pre-fix the gate only watched two of the three
    version sources (pyproject ↔ CHANGELOG ↔ git tag), so this drift class
    slipped through every release gate.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

from citeguard import __version__

_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _ROOT / "pyproject.toml"
_CHECK_VERSION = _ROOT / "scripts" / "check_version.py"


def _load_check_version():
    """Load scripts/check_version.py as an isolated module (it's not a package).

    A fresh module is returned each call, so mutating its path globals in a
    test cannot leak into other tests.
    """
    spec = importlib.util.spec_from_file_location("_check_version_under_test", _CHECK_VERSION)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # __name__ is "_check_version_under_test" (not "__main__"), so the script's
    # `if __name__ == "__main__"` guard keeps main() from auto-running on load.
    spec.loader.exec_module(mod)
    return mod


def test_citeguard_version_matches_pyproject():
    """The shipped __version__ must equal the pyproject version (fix #2)."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    assert __version__ == data["project"]["version"], "__version__ drifts from pyproject"


def test_check_version_detects_init_py_drift(tmp_path):
    """check_version.py must fail the gate when __init__.py drifts from pyproject.

    Pre-fix the script compared only pyproject ↔ CHANGELOG ↔ git tag, never
    `__init__.py`, so a stale `__version__` shipped through every gate.
    Post-fix the gate also asserts `__init__.py` == pyproject.
    """
    cv = _load_check_version()

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.6.0"\n', encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [0.6.0] — 2026-08-21\n\nbody\n", encoding="utf-8")
    init_py = tmp_path / "src" / "citeguard" / "__init__.py"
    init_py.parent.mkdir(parents=True)

    # Drifted __init__.py: still on 0.5.0 while pyproject / CHANGELOG are 0.6.0.
    init_py.write_text('__version__ = "0.5.0"\n', encoding="utf-8")

    # Point the freshly-loaded module's path globals at the temp tree.
    cv._PYPROJECT = pyproject
    cv._CHANGELOG = changelog
    cv._INIT = init_py
    cv._ROOT = tmp_path

    assert cv.main() == 1, "drifted __init__.py must fail the version gate"

    # Green tree: align __init__.py → gate passes.
    init_py.write_text('__version__ = "0.6.0"\n', encoding="utf-8")
    assert cv.main() == 0, "aligned versions must pass the version gate"
