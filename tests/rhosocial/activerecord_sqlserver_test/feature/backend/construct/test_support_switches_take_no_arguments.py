# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/test_support_switches_take_no_arguments.py
"""``supports_*`` is a support switch: no arguments, one bool.

A capability flag answers "does this dialect configuration have capability k",
so its only input is the dialect instance. Anything that needs a name or a kind
is either a separate switch (closed vocabulary) or a format-time validation
(open vocabulary) -- never an argument to ``supports_*``.

The SQL Server backend narrows an open vocabulary into an ``is_*_available``
name lookup (``is_json_function_available`` / ``is_spatial_type_available``),
which is deliberately *not* matched by this guard.
"""

import ast
from pathlib import Path
from typing import List

import pytest


def _repository_root() -> Path:
    """Locate the checkout root by its ``pyproject.toml`` and ``src`` directory."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src").is_dir():
            return parent
    raise AssertionError("cannot locate the repository root above this test file")


def _source_files() -> List[Path]:
    """Every Python file shipped in ``src``."""
    return sorted((_repository_root() / "src").rglob("*.py"))


def _required_arguments(func: ast.FunctionDef) -> List[str]:
    """Parameters that must be passed, excluding ``self``."""
    args = func.args
    positional = list(args.args)
    required = positional[1 : len(positional) - len(args.defaults)]
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is None:
            required.append(arg)
    return [a.arg for a in required]


def _offenders(tree: ast.AST, label: str) -> List[str]:
    """``supports_*`` methods whose signature requires an argument."""
    found: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            if not item.name.startswith("supports_"):
                continue
            missing = _required_arguments(item)
            if missing:
                found.append(f"{label}:{item.lineno} {item.name}({', '.join(missing)})")
    return found


@pytest.mark.parametrize("path", _source_files(), ids=lambda p: str(p.name))
def test_support_switch_takes_no_required_argument(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = _offenders(tree, path.name)
    assert not offenders, "\n".join(offenders)


def test_the_scan_reaches_the_source_tree() -> None:
    files = _source_files()
    assert files, "no source files found; the guard would pass vacuously"
    assert len(files) > 50, f"only {len(files)} source files were scanned"


def test_the_scan_flags_a_planted_violation(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self, name):\n"
        "        return False\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"), filename=str(probe))
    assert _offenders(tree, "probe"), "the guard failed to flag a fabricated violation"


def test_the_scan_flags_a_keyword_only_violation(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self, *, name):\n"
        "        return False\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"), filename=str(probe))
    assert _offenders(tree, "probe")


def test_the_scan_accepts_a_defaulted_parameter(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self, name=None):\n"
        "        return False\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"), filename=str(probe))
    assert not _offenders(tree, "probe")
