# tests/plugins/expression_xdist.py
"""Default the expression test area to parallel when it is the only target.

The org rules (expression-dialect §12) make pytest-xdist parallel the default
configuration of the expression test directory. The worker count, however, is
read by pytest-xdist before any conftest loads -- a conftest cannot inject
``-n`` -- so the default lives in this repository-local plugin, registered
from ``pytest.ini`` with ``-p plugins.expression_xdist`` and therefore active
for every run in this repository. ``pytest.ini`` also sets
``pythonpath = tests``, and that ini value is what makes the plugin findable by
name at all: pytest applies ``pythonpath`` just before it imports the ``-p``
plugins, so the registration no longer depends on ``PYTHONPATH=src:tests``
being set by whoever ran pytest.

The plugin is deliberately narrow in what it touches:

* **Availability**: with pytest-xdist not installed it enables nothing --
  installation is not this plugin's business, and the run proceeds serially the
  way it always has.
* **Scope**: only when every non-option argument names a path inside the
  expression area (``feature/backend/expression``) is ``-n auto`` appended. A
  whole-repository run, a mixed run, or a run of any other directory keeps the
  serial default; the live scenario tests have their own parallel runner
  (``--scenario-parallel``) and are not dragged into a worker pool they did not
  ask for.
* **Choice respected**: an explicit ``-n`` / ``--numprocesses`` is never
  overridden. An explicit ``--dist`` is never overridden either, except that
  ``loadscope`` and ``loadfile`` are refused outright (§12: they bind whole
  modules together and hide case-to-case dependencies). ``-n`` without
  ``--dist`` gets ``--dist=loadgroup`` appended, because loadgroup is the one
  scheduling the rules allow.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The area this plugin defaults to parallel. Relative to the repository root,
#: which is where ``pyproject.toml`` -- and therefore this plugin's
#: registration -- lives.
_EXPRESSION_AREA = os.path.join(
    "tests",
    "rhosocial",
    "activerecord_sqlserver_test",
    "feature",
    "backend",
    "expression",
)

#: Options that take a separate value, so the value must not be mistaken for a
#: path argument when scoping the invocation. ``-p`` matters most: this plugin
#: is itself registered as ``-p plugins.expression_xdist``, and its own name
#: must not be read as a test target.
_VALUE_TAKING = frozenset(
    {
        "-p", "-k", "-m", "-o", "-r", "-W", "--tb", "--deselect", "--basetemp",
        "--maxfail", "--rootdir", "--import-mode", "--pdbcls", "--lf",
        "--lfnf", "--cov", "--cov-config", "--cov-report",
        "--capture", "--color", "--junitxml", "--result-log",
        "-n", "--numprocesses", "--dist",
    }
)

_FORBIDDEN_DISTS = ("loadscope", "loadfile")


def _looks_like_path(arg: str) -> bool:
    """Whether *arg* names a test target rather than an option or a value."""
    return not arg.startswith("-")


def _expression_area_root() -> Path:
    """The absolute expression-area directory for this repository.

    This module is imported from ``tests/plugins``, two levels below the
    repository root.
    """
    return Path(__file__).resolve().parent.parent.parent / _EXPRESSION_AREA


def _inside_expression_area(arg: str) -> bool:
    path = Path(os.path.abspath(arg))
    return path == _expression_area_root() or _expression_area_root() in path.parents


def pytest_load_initial_conftests(args, early_config, parser):
    """Append the parallel default when the run is expression-only."""
    if not _xdist_available():
        print(
            "[expression_xdist] pytest-xdist is not installed; the expression "
            "area runs serially (install it to get the parallel default the "
            "test rules ask for)"
        )
        return

    targets = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in _VALUE_TAKING:
            skip_next = True
            continue
        if arg.startswith("--") and "=" in arg:
            name = arg.split("=", 1)[0]
            if name in _VALUE_TAKING:
                continue
            continue
        if _looks_like_path(arg):
            targets.append(arg)

    if not targets or not all(_inside_expression_area(t) for t in targets):
        return

    def _option_value(flag: str):
        for index, arg in enumerate(args):
            if arg == flag and index + 1 < len(args):
                return args[index + 1]
            if arg.startswith(flag + "="):
                return arg.split("=", 1)[1]
        return None

    if _option_value("--dist") in _FORBIDDEN_DISTS:
        raise SystemExit(
            "[expression_xdist] --dist=loadscope/loadfile are not allowed for "
            "the expression area (expression-dialect §12: they bind whole "
            "modules together; use --dist=loadgroup)"
        )

    if _option_value("-n") is None and _option_value("--numprocesses") is None:
        args.extend(["-n", "auto"])
    if _option_value("--dist") is None:
        args.extend(["--dist", "loadgroup"])


def _xdist_available() -> bool:
    """The availability condition: the plugin enables nothing without xdist,
    and installing it is nobody's business but the environment's."""
    try:
        import xdist  # noqa: F401
    except ImportError:
        return False
    return True
