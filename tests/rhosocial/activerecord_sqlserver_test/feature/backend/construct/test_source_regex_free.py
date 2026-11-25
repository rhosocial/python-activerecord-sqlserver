# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/test_source_regex_free.py
"""Guard: the shipped backend source does not use the ``re`` module.

The backend reads server text -- error messages, type spellings, prepared
statements -- with plain character scanning (``.._scan``), so the runtime
surface carries no standard-library regular expressions. Tests may still keep
regexes, but only to assert generated SQL; this guard covers ``src`` only.

Each source file is checked twice: an AST pass rejects any ``re`` import, and
a tokenizer pass rejects any ``re`` attribute use. Tokenizing instead of
scanning raw text keeps prose such as "core." from being mistaken for an
attribute access.
"""

import ast
import io
import tokenize
from pathlib import Path
from typing import List, Optional


def _repository_root() -> Path:
    """Locate the checkout root by its ``pyproject.toml`` and ``src`` directory."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src").is_dir():
            return parent
    raise AssertionError("cannot locate the repository root above this test file")


def _source_files() -> List[Path]:
    """Every Python file shipped in ``src``."""
    return sorted((_repository_root() / "src").rglob("*.py"))


def _import_violations(path: Path, source: str) -> List[str]:
    """Lines importing the ``re`` module, including ``from re import ...``."""
    tree = ast.parse(source, filename=str(path))
    violations: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re" or alias.name.startswith("re."):
                    violations.append(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "re" or module.startswith("re."):
                violations.append(f"{path}:{node.lineno}: from {module} import ...")
    return violations


def _attribute_violations(path: Path, source: str) -> List[str]:
    """Lines where the name ``re`` is followed by an attribute access."""
    violations: List[str] = []
    previous: Optional[tokenize.TokenInfo] = None
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.OP and token.string == ".":
            if previous is not None and previous.type == tokenize.NAME:
                if previous.string == "re":
                    violations.append(f"{path}:{previous.start[0]}: re.")
        if token.type not in (
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.COMMENT,
        ):
            previous = token
    return violations


def test_src_does_not_import_the_re_module() -> None:
    files = _source_files()
    assert files, "no source files found; the guard would pass vacuously"
    violations = []
    for path in files:
        violations.extend(_import_violations(path, path.read_text(encoding="utf-8")))
    assert not violations, "src must not import the re module:\n" + "\n".join(violations)


def test_src_does_not_access_re_attributes() -> None:
    files = _source_files()
    assert files, "no source files found; the guard would pass vacuously"
    violations = []
    for path in files:
        violations.extend(_attribute_violations(path, path.read_text(encoding="utf-8")))
    assert not violations, "src must not use re attributes:\n" + "\n".join(violations)
