# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/expression_parse_contract.py
"""The parse-vs-format round-trip sweep for typed-column contracts.

Vendored from the shared testsuite's ``utils/parse_contract.py`` when that
suite's ``fix/column-constraint-gates`` branch dropped ``utils/expression``
in ``e05edb0`` with the direction "round-trip coverage moves to the owning
repository": this module imported ``make_instance`` from the deleted harness,
and a dead import is a dead test. The sweep itself is unchanged -- the same two
invariants over the same registry -- and the one dependency is now the harness
this repository owns beside it. Fix drift here deliberately; do not re-import
it from the suite.

Every dialect's ``parse_type`` is the introspection inverse of its
``format_data_type_<name>`` renderings. Two invariants make a dialect coherent,
and this module checks both over a backend's full type registry:

**String stability** -- parsing a rendering and re-rendering the answer
must produce the identical string. Whatever ``parse`` answers, its answer
must name the same storage the server holds, or the schema differ would
report a change no one made.

**Class honesty** -- the answer is either the declared instance itself
(``parsed == declared``, the round-trip-equal case) or the *documented*
answer class for that declaration: a backend that widens a declaration on
the way in (four integer widths stored as one integer type, a JSONB
concept stored as the JSON type) answers with the concept that was *not*
widened, and that answer is recorded here once per backend rather than
being re-derived by every test.

What the sweep deliberately does **not** do:

* It does not assert anything about a class the registry cannot construct
  or cannot render -- those are the round-trip matrix's own lists
  (``UNCONSTRUCTIBLE`` / pinned non-renders) and have their own tests.
* It does not guess what ``CustomType`` should parse to -- a
  ``CustomType``'s raw is caller-supplied text that may happen to be a
  word the dialect knows, so the class is skipped by default.
* It does not accept a ``CustomType`` answer for a rendered word. A
  dialect that renders a word its own parse does not model has a gap on
  one side or the other, and the sweep says so instead of blessing it.
"""

from typing import Any, Dict, Optional

from rhosocial.activerecord.backend.expression.types import CustomType, DataType

# The harness is this module's sibling, and this module is itself loaded by path
# (from ``test_sqlserver_type_protocol.py``) as well as by name (from the matrix
# beside it) -- a by-name import would only work in the second case, so the
# sibling is loaded by path and both callers get the same module.
import importlib.util as _importlib_util
from pathlib import Path as _Path

_harness_path = _Path(__file__).parent / "expression_roundtrip_harness.py"
_spec = _importlib_util.spec_from_file_location(
    "sqlserver_roundtrip_harness", _harness_path
)
_harness = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_harness)

make_instance = _harness.make_instance


def parse_roundtrip_failures(
    dialect: Any,
    registry: Dict[str, Any],
    *,
    widening: Optional[Dict[str, Any]] = None,
    skip: Any = (),
) -> Any:
    """Sweep *registry* and return the parse round-trip failures as text.

    Args:
        dialect: the dialect whose ``parse_type`` is under test.
        registry: a mapping of fully-qualified name to class, as the
            backend's round-trip module keeps it (``REGISTERED`` or
            ``ALL_CLASSES``). Only concrete ``DataType`` subclasses are
            swept.
        widening: the backend's documented answer table,
            ``{declared class name: answer}``. An entry here asserts the
            parse answers with exactly that class and that the answer
            re-renders the identical string, **unless** the value is a
            ``(class name, expected string)`` tuple: that form is for the
            documented answers whose re-render deliberately *differs* -- a
            backend that stores a word as its documented alias (Snowflake
            writes TINYINT and stores INTEGER) or completes a bare word
            with the server's default (its bare VARCHAR *is*
            VARCHAR(16777216)). The tuple pins both the answer class and
            the string it re-renders, so the alias is recorded as a
            reviewable fact rather than leaking out as string instability.
            The reason for each entry belongs in the backend's test file
            next to the table, where a reader can check it.
        skip: class names to leave out of the sweep entirely, in addition
            to the built-in ``CustomType`` skip. Use it only for classes
            that are not column types at all (a CAST target, say) and say
            why in the test file.

    Returns:
        A list of human-readable failures. An empty list is the contract
        met; each element names the class, the rendering and the fault,
        so a red test points straight at the offending entry instead of
        leaving the reader to bisect.
    """
    widening = dict(widening or {})
    skipped = set(skip) | {"CustomType"}
    failures = []
    for fqn in sorted(registry):
        cls = registry[fqn]
        if not (isinstance(cls, type) and issubclass(cls, DataType)):
            continue
        if cls is DataType or cls is CustomType:
            continue
        if cls.__name__ in skipped:
            continue
        instance, source = make_instance(cls, dialect)
        if instance is None:
            continue  # the matrix's UNCONSTRUCTIBLE list owns this class
        try:
            rendered, _params = instance.to_sql()
        except Exception:
            continue  # the matrix's pinned non-renders own this class
        try:
            parsed = dialect.parse_type(rendered)
        except Exception as exc:
            failures.append(
                "%s renders %r but parse_type raises %s: %s"
                % (cls.__name__, rendered, type(exc).__name__, exc)
            )
            continue
        if isinstance(parsed, CustomType):
            failures.append(
                "%s renders %r but parse_type answers CustomType -- a "
                "dialect must recognise its own renderings"
                % (cls.__name__, rendered)
            )
            continue
        expected_entry = widening.get(cls.__name__)
        if expected_entry is None:
            if parsed != instance:
                failures.append(
                    "%s renders %r but parse_type answers %r -- neither "
                    "the declaration nor a documented widening"
                    % (cls.__name__, rendered, parsed)
                )
            continue
        if isinstance(expected_entry, tuple):
            expected, expected_restring = expected_entry
        else:
            expected, expected_restring = expected_entry, None
        if type(parsed).__name__ != expected:
            failures.append(
                "%s renders %r; the documented answer is %s but "
                "parse_type answers %s"
                % (cls.__name__, rendered, expected, type(parsed).__name__)
            )
            continue
        try:
            re_rendered, _ = parsed.to_sql()
        except Exception as exc:
            failures.append(
                "%s renders %r; the documented answer %s re-renders with "
                "%s: %s"
                % (cls.__name__, rendered, expected, type(exc).__name__, exc)
            )
            continue
        if expected_restring is not None:
            if re_rendered != expected_restring:
                failures.append(
                    "%s renders %r; the documented answer %s re-renders "
                    "%r but the table says %r"
                    % (cls.__name__, rendered, expected, re_rendered,
                       expected_restring)
                )
        elif re_rendered != rendered:
            failures.append(
                "%s renders %r but the documented answer %s re-renders "
                "%r -- the strings must name the same storage, or the "
                "table entry must record the documented re-render as a "
                "(class, string) tuple"
                % (cls.__name__, rendered, expected, re_rendered)
            )
    return failures


__all__ = ["parse_roundtrip_failures"]
