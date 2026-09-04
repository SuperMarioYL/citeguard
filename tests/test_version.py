"""Version-consistency regression tests (m6_preflight_lint extension).

Covers `fix-init-version-drift-vs-pyproject` (v0.6.0):
  * `citeguard.__version__` must equal the `pyproject.toml` version (the
    user-visible defect was `citeguard --version` printing a stale version on
    a 0.5.0 install because `__init__.py` was stuck at `0.4.0`), and
  * `scripts/check_version.py` must fail the gate when `__init__.py` drifts
    from `pyproject.toml`.  Pre-fix the gate only watched two of the three
    version sources (pyproject ↔ CHANGELOG ↔ git tag), so this drift class
    slipped through every release gate.

Covers `fix-action-version-pin-stale-again` (v0.7.0):
  * `action.yml`'s `version` input default must equal the `pyproject.toml`
    version — the gate now watches a fourth source so a stale Action pin (the
    documented distribution channel installing a pre-current build) can no
    longer ship through `make lint` / the release gate.
"""

from __future__ import annotations

import importlib.util
import subprocess
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

    # An aligned action.yml in the temp tree isolates this test from the real
    # repo's action.yml (the v0.7.0 gate now reads that 4th source too).
    action_yml = tmp_path / "action.yml"
    action_yml.write_text('inputs:\n  version:\n    default: "0.6.0"\n', encoding="utf-8")

    # Point the freshly-loaded module's path globals at the temp tree.
    cv._PYPROJECT = pyproject
    cv._CHANGELOG = changelog
    cv._INIT = init_py
    cv._ACTION = action_yml
    cv._ROOT = tmp_path

    assert cv.main() == 1, "drifted __init__.py must fail the version gate"

    # Green tree: align __init__.py → gate passes.
    init_py.write_text('__version__ = "0.6.0"\n', encoding="utf-8")
    assert cv.main() == 0, "aligned versions must pass the version gate"


def test_check_version_detects_action_yml_drift(tmp_path):
    """check_version.py must fail the gate when action.yml's `version` default
    drifts from pyproject (v0.7.0 extension — the fourth version source).

    Pre-extension the gate never watched action.yml, so a stale
    `default: "0.5.0"` shipped through every gate while pyproject was 0.6.0.
    """
    cv = _load_check_version()

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.6.0"\n', encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [0.6.0] — 2026-08-21\n\nbody\n", encoding="utf-8")
    init_py = tmp_path / "src" / "citeguard" / "__init__.py"
    init_py.parent.mkdir(parents=True)
    init_py.write_text('__version__ = "0.6.0"\n', encoding="utf-8")

    # Drifted action.yml: default stuck on 0.5.0 while the rest are 0.6.0.
    action_yml = tmp_path / "action.yml"
    action_yml.write_text('inputs:\n  version:\n    default: "0.5.0"\n', encoding="utf-8")

    cv._PYPROJECT = pyproject
    cv._CHANGELOG = changelog
    cv._INIT = init_py
    cv._ACTION = action_yml
    cv._ROOT = tmp_path

    assert cv.main() == 1, "drifted action.yml default must fail the version gate"

    # Green tree: align action.yml → gate passes.
    action_yml.write_text('inputs:\n  version:\n    default: "0.6.0"\n', encoding="utf-8")
    assert cv.main() == 0, "aligned versions must pass the version gate"


def test_check_version_detects_release_tag_above_declared(tmp_path):
    """check_version.py must fail when a git tag strictly greater than the
    declared version exists — the "tagged but not bumped" drift class (v0.8.0).

    v0.7.0 shipped with every version string frozen at 0.6.0 because the gate
    only asked "does tag v{py} exist" (v0.6.0 did, so it printed OK) and never
    noticed the higher v0.7.0 tag.  The gate now enumerates vX.Y.Z tags and fails
    when any is above the declared version.
    """
    cv = _load_check_version()

    # Seed a real temp git repo carrying a tag above the declared version.
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True, check=True
    )
    (tmp_path / "marker").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "tag", "v0.7.0"], cwd=tmp_path, capture_output=True, check=True)

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.6.0"\n', encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [0.6.0] — 2026-08-21\n\nbody\n", encoding="utf-8")
    init_py = tmp_path / "src" / "citeguard" / "__init__.py"
    init_py.parent.mkdir(parents=True)
    init_py.write_text('__version__ = "0.6.0"\n', encoding="utf-8")
    action_yml = tmp_path / "action.yml"
    action_yml.write_text('inputs:\n  version:\n    default: "0.6.0"\n', encoding="utf-8")

    cv._PYPROJECT = pyproject
    cv._CHANGELOG = changelog
    cv._INIT = init_py
    cv._ACTION = action_yml
    cv._ROOT = tmp_path

    assert cv.main() == 1, "a release tag above the declared version must fail the gate"

    # Green tree: the highest tag equals the declared version -> passes.
    subprocess.run(["git", "tag", "-d", "v0.7.0"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "tag", "v0.6.0"], cwd=tmp_path, capture_output=True, check=True)
    assert cv.main() == 0, "aligned versions with no higher tag must pass the gate"
