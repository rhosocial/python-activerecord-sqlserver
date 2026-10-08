# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_expression_roundtrip_all.py
"""
Serialization and SQL coverage for every expression class SQL Server renders.

Two packages are in scope: the backend's own
``rhosocial.activerecord.backend.impl.sqlserver.expression``, and core's
``rhosocial.activerecord.backend.expression``. The second one used to be
absent, and its absence is why a core class with no SQL Server formatter could
sit in the tree unnoticed -- the backend matrix could not see it, and core's own
matrix renders against the Dummy dialect, where it renders.

Why ``to_sql()`` is classified rather than caught
================================================

This matrix used the testsuite's ``sql_consistent``, whose body was::

    try:
        expected = instance.to_sql()
    except Exception:
        return

Every render failure was therefore a green tick, and the three SQL comparisons
that follow never ran. A formatter reading a field that no longer existed was
indistinguishable from a formatter for a feature SQL Server does not have. The
cost was not abstract: this rewrite found a formatter whose signature no caller
could satisfy, so every ``LateralExpression`` on SQL Server raised ``TypeError``
and no test said so -- and, by collecting core's own classes, four core
expressions whose formatter this backend had shadowed with a different
signature. Both are described where they are fixed and, for the four, where they
are pinned.

Each outcome is now named and asserted:

* **renders** -- all three encodings must restore byte-identical SQL *and*
  byte-identical bind parameters.
* a member of :data:`LEGITIMATE_NON_RENDERS` -- a class that cannot render for a
  reason belonging to its own tree. Each entry pins the exception type *and* a
  message fragment, so a class that started failing for a different reason fails
  here instead of staying quietly green.
* ``UnsupportedFeatureError`` from a class *not* named in the dict -- SQL Server
  does not model the feature. Asserted as exactly that type, so a subclass raised
  for an unrelated reason is still visible rather than passing.
* **anything else** -- a failure naming the class and the exception.

The dict is read before the ``UnsupportedFeatureError`` branch, because core now
reports a *missing formatter* through that same type; see
:func:`assert_sql_roundtrip_classified`.

And when a class cannot be constructed
======================================

``make_instance(...) is None`` becomes a skip, but only for a class named in
:data:`UNCONSTRUCTIBLE`, and :func:`test_unconstructible_list_is_exact` pins that
tuple against what the constructor really skips. Both directions fail: a class
that gains a constructor, and a class that starts failing to build.

Discovery does not use ``ExpressionRegistry._registry``. That registry is
process-global and grows as sibling test modules import their own backends, so
reading it made this matrix's contents depend on which files pytest happened to
import first. :func:`collect_expression_classes` walks a package instead, which
is deterministic.
"""

import inspect
from typing import Dict, Tuple, Type

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.objects import (
    Database,
    Function,
    Index,
    Schema,
    Sequence,
    Table,
    Trigger,
    Type,
    View,
)
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.serialization import ExpressionRegistry
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.expression.statements import (
    ddl_alter,
    ddl_table,
    ddl_type,
    ddl_view,
    dml,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.dml import (
    MergeAction,
    MergeActionType,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.testsuite.utils.expression import (
    collect_expression_classes,
    make_instance,
    register_all,
    register_special_constructor,
    roundtrip_expression,
)

SS_EXPR_PKG = "rhosocial.activerecord.backend.impl.sqlserver.expression"
CORE_EXPR_PKG = "rhosocial.activerecord.backend.expression"


def _collect(pkg: str) -> Dict[str, type]:
    """Every concrete expression class one package defines.

    Walked rather than read from the registry, for the reason in the module
    docstring. Two packages export the same class under different names in
    different places, so the first name in sorted order wins and the matrix does
    not assert one class twice.
    """
    ExpressionRegistry._auto_register_builtins()
    collected = collect_expression_classes(pkg)
    by_identity: Dict[int, str] = {}
    for fqn, cls in sorted(collected.items()):
        by_identity.setdefault(id(cls), fqn)
    return {
        fqn: cls
        for cls in collected.values()
        if not inspect.isabstract(cls)
        for fqn in [by_identity[id(cls)]]
    }


CORE_REGISTERED = _collect(CORE_EXPR_PKG)
SS_REGISTERED = _collect(SS_EXPR_PKG)
REGISTERED: Dict[str, type] = {**CORE_REGISTERED, **SS_REGISTERED}
register_all(REGISTERED)


# ---------------------------------------------------------------------------
# Special constructors: a real value where the introspective guess is a lie
# ---------------------------------------------------------------------------
#
# ``make_instance`` reads each required parameter's annotation and guesses:
# ``"x"`` for a string, ``[]`` for a list, ``IntegerType()`` for a type. That is
# right for a name and wrong for everything that wants a catalogue object -- a
# Table, an Index, a Type -- because a bare ``"x"`` is not one, and the formatter
# now refuses it by name. It is also wrong for the containers that require at
# least one member (CASE, WINDOW, temporal options), for the constraints that
# must render without bind parameters, and for the enums the guess supplies a
# string for.
#
# Every registration below replaces a guess that would otherwise have produced an
# instance SQL Server cannot render. Suffixes are relative to the expression
# package because ``make_instance`` matches with ``str.endswith`` and several
# modules export identically named classes.


def _table_obj(dialect, name="t"):
    """A table with a bare name and no namespace."""
    return Table(dialect, name)


def _schema_obj(dialect):
    """A Schema, for the CREATE/DROP SCHEMA statements the guess cannot name."""
    return Schema(dialect, "app")


def _database_obj(dialect):
    """A Database, for CREATE/DROP/ALTER DATABASE."""
    return Database(dialect, "app")


def _sequence_obj(dialect):
    """A Sequence, for the three SEQUENCE statements."""
    return Sequence(dialect, "s")


def _type_obj(dialect):
    """A Type, for CREATE/DROP TYPE."""
    return Type(dialect, "t")


def _index_obj(dialect, name="i"):
    """An Index, for the index statements."""
    return Index(dialect, name)


def _view_obj(dialect, name="v"):
    """A View, for the view statements."""
    return View(dialect, name)


def _alias_type_definition(dialect):
    """A SQL Server alias TYPE definition, bound to the dialect.

    The testsuite registers the Dummy backend's definition for CREATE TYPE,
    which SQL Server cannot spell: a TYPE definition is part of the statement,
    not a parameter, so its body must render as SQL rather than a bind value.
    """
    from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
        SQLServerAliasTypeDefinition,
    )

    return SQLServerAliasTypeDefinition(dialect, IntegerType(dialect), nullability=True)


def _column_predicate(dialect):
    """A predicate comparing two columns, so it renders with no bind parameters."""
    return ComparisonPredicate(dialect, "=", Column(dialect, "a"), Column(dialect, "b"))


def _one_column_query(dialect):
    """A single-column ``SELECT`` over a table, for CREATE VIEW and TABLE AS.

    Used by the CREATE VIEW and materialized-view registrations, where the
    guess would otherwise supply a bare string for the query slot.
    """
    return QueryExpression(
        dialect, select=[Column(dialect, "id")], from_=_table_obj(dialect)
    )


def _integer_column(dialect, name="col"):
    """A column definition carrying a *dialect-bound* type.

    The binding is load-bearing: ``to_sql()`` dispatches on the type through its
    own dialect, so an unbound ``IntegerType()`` raises the moment anything
    renders it.
    """
    return ddl_table.ColumnDefinition(dialect, name, IntegerType(dialect))


def _sqlserver_collation(dialect):
    from rhosocial.activerecord.backend.impl.sqlserver.collation import (
        SQLServerCollation,
    )

    return SQLServerCollation.LATIN1_GENERAL_CI_AS


def register_specials():
    """Replace every introspective guess that would cost a real assertion."""
    # -- the FROM side ------------------------------------------------------
    register_special_constructor(
        "sources.relation.NamedRelationRef",
        lambda d: NamedRelationRef(d, _table_obj(d)),
    )
    # CREATE VIEW needs a query, and the guess supplies the string "x" for it.
    register_special_constructor(
        "statements.ddl_view.CreateViewExpression",
        lambda d: ddl_view.CreateViewExpression(
            d, view=_view_obj(d), query=_one_column_query(d)
        ),
    )

    # -- column pieces ------------------------------------------------------
    # Overrides the shared testsuite factory, which binds no dialect to its type.
    register_special_constructor(
        "statements.ddl_table.ColumnDefinition", _integer_column
    )

    # -- containers that must not be empty ----------------------------------
    from rhosocial.activerecord.backend.expression.advanced_functions import (
        CaseExpression,
        WindowClause,
        WindowDefinition,
        WindowSpecification,
    )

    register_special_constructor(
        "advanced_functions.CaseExpression",
        lambda d: CaseExpression(
            d, cases=[(_column_predicate(d), Literal(d, 1))], else_result=Literal(d, 0)
        ),
    )
    register_special_constructor(
        "advanced_functions.WindowSpecification",
        lambda d: WindowSpecification(d, partition_by=["a"]),
    )
    register_special_constructor(
        "advanced_functions.WindowDefinition",
        lambda d: WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"])),
    )
    register_special_constructor(
        "advanced_functions.WindowClause",
        lambda d: WindowClause(d, [WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"]))]),
    )
    # An empty options dict is refused by the formatter, so a time-travel clause
    # needs an actual option.
    register_special_constructor(
        "datetime.TemporalOptionsExpression",
        lambda d: __import__(
            "rhosocial.activerecord.backend.expression.datetime",
            fromlist=["TemporalOptionsExpression"],
        ).TemporalOptionsExpression(d, {"as_of": "2020-01-01"}),
    )
    # The guess supplies the string "x", which SQL Server's collation validator
    # rightly refuses.
    register_special_constructor(
        "collation.CollateExpression",
        lambda d: __import__(
            "rhosocial.activerecord.backend.expression.collation",
            fromlist=["CollateExpression"],
        ).CollateExpression(d, Column(d, "a"), _sqlserver_collation(d)),
    )

    # -- ALTER TABLE actions ------------------------------------------------
    register_special_constructor(
        "ddl_alter.AddColumn", lambda d: ddl_alter.AddColumn(d, _integer_column(d))
    )
    register_special_constructor(
        "ddl_alter.AddTableConstraint",
        lambda d: ddl_alter.AddTableConstraint(
            d, TableConstraint(d, TableConstraintType.PRIMARY_KEY, name="c", columns=["a"])
        ),
    )
    register_special_constructor(
        "ddl_alter.AddIndex", lambda d: ddl_alter.AddIndex(d, ddl_table.IndexDefinition(d, "i", ["a"]))
    )

    # -- constraints that must render without bind parameters ----------------
    register_special_constructor(
        "ddl_table.ColumnConstraint",
        lambda d: ColumnConstraint(d, ColumnConstraintType.NOT_NULL, name="c"),
    )
    register_special_constructor(
        "ddl_table.TableConstraint",
        lambda d: TableConstraint(d, TableConstraintType.PRIMARY_KEY, name="c", columns=["a"]),
    )
    # REFERENCES needs at least one referenced column; the guess supplies none.
    register_special_constructor(
        "ddl_table.ReferencesClause",
        lambda d: ddl_table.ReferencesClause(d, Table(d, "other"), ["b"]),
    )

    # -- statements holding objects the guess cannot name --------------------
    # Each of these was found by running the matrix, not by reading it: the
    # introspective guess hands the statement a bare ``"x"``, and the formatter
    # now refuses that by name.
    #
    # The keys are spelled *identically* to the testsuite's own where they
    # overlap, because ``make_instance`` returns the **first** registry key whose
    # suffix matches -- and the testsuite populates its registry at import time,
    # so a new, shorter key is never consulted for a class an earlier, longer key
    # already claims. Registering ``ddl_type.CreateTypeExpression`` next to the
    # testsuite's ``statements.ddl_type.CreateTypeExpression`` would be silent
    # dead code; re-using the key replaces the entry. That is why the two TYPE
    # registrations below keep the ``statements.`` prefix.
    from rhosocial.activerecord.backend.expression.statements import (
        ddl_comment,
        ddl_index,
        ddl_truncate,
    )

    register_special_constructor(
        "ddl_truncate.TruncateExpression",
        lambda d: ddl_truncate.TruncateExpression(d, _table_obj(d)),
    )
    register_special_constructor(
        "ddl_table.CreateTableExpression",
        lambda d: ddl_table.CreateTableExpression(d, _table_obj(d), [_integer_column(d)]),
    )
    register_special_constructor(
        "ddl_table.DropTableExpression",
        lambda d: ddl_table.DropTableExpression(d, _table_obj(d)),
    )
    register_special_constructor(
        "ddl_view.DropViewExpression",
        lambda d: ddl_view.DropViewExpression(d, _view_obj(d)),
    )
    register_special_constructor(
        "ddl_index.DropFulltextIndexExpression",
        lambda d: ddl_index.DropFulltextIndexExpression(
            d, _index_obj(d), _table_obj(d)
        ),
    )
    register_special_constructor(
        "ddl_index.CreateFulltextIndexExpression",
        lambda d: ddl_index.CreateFulltextIndexExpression(
            d, index=_index_obj(d), table=_table_obj(d), columns=["a"]
        ),
    )
    # A COMMENT ON is DDL: its comment must render as a literal rather than a
    # bind parameter, so the guess's bare string is replaced by one with a name.
    register_special_constructor(
        "ddl_comment.CommentOnExpression",
        lambda d: ddl_comment.CommentOnExpression(d, "table", _table_obj(d), comment="c"),
    )
    register_special_constructor(
        "ddl_trigger.DropTriggerExpression",
        lambda d: __import__(
            "rhosocial.activerecord.backend.expression.statements.ddl_trigger",
            fromlist=["DropTriggerExpression"],
        ).DropTriggerExpression(d, Trigger(d, "trg")),
    )
    # A TYPE definition must be a definition object, and the one the testsuite
    # registers is the Dummy's -- which SQL Server cannot spell, so the statement
    # reports the feature as unsupported rather than rendering. SQL Server's own
    # alias definition is used instead, so it renders and the round-trip is
    # asserted. Same key as the testsuite's, deliberately.
    register_special_constructor(
        "statements.ddl_type.CreateTypeExpression",
        lambda d: ddl_type.CreateTypeExpression(
            d, _type_obj(d), _alias_type_definition(d)
        ),
    )

    # -- MERGE ---------------------------------------------------------------
    register_special_constructor(
        "dml.MergeAction",
        lambda d: MergeAction(
            d,
            MergeActionType.UPDATE,
            {"a": Literal(d, 1)},
            _column_predicate(d),
            "matched",
        ),
    )
    register_special_constructor(
        "dml.MergeExpression",
        lambda d: dml.MergeExpression(
            d,
            target_table=_table_obj(d),
            source=NamedRelationRef(d, Table(d, "src")),
            on_condition=_column_predicate(d),
            when_matched=[
                MergeAction(
                    d,
                    MergeActionType.UPDATE,
                    {"a": Literal(d, 1)},
                    _column_predicate(d),
                    "matched",
                )
            ],
        ),
    )

    # -- SQL Server's own expressions ---------------------------------------
    def pivot(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.pivot import (
            PivotExpression,
        )

        return PivotExpression(d, aggregate_function="SUM", value_column="amount", pivot_column="q")

    def columnstore(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.columnstore import (
            SQLServerColumnstoreIndexExpression,
        )

        return SQLServerColumnstoreIndexExpression(d, "cci", "t", columns=["a"])

    def partition_range(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionByRangeClause,
            SQLServerPartitionFunctionExpression,
            SQLServerPartitionRangeDirection,
            SQLServerPartitionSchemeExpression,
        )

        return SQLServerPartitionByRangeClause(
            d, keys=[Column(d, "id")], partition_scheme="ps"
        )

    def partition_function(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionFunctionExpression,
        )

        return SQLServerPartitionFunctionExpression(d, "pf_sales", "DATE", ["2020-01-01"])

    def partition_scheme(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionSchemeExpression,
        )

        return SQLServerPartitionSchemeExpression(d, "ps_sales", "pf_sales", ["PRIMARY"])

    def alias_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerAliasTypeDefinition,
        )

        return SQLServerAliasTypeDefinition(d, IntegerType(d), nullability=True)

    def table_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerTableTypeDefinition,
        )
        from rhosocial.activerecord.backend.impl.sqlserver.expression.index import (
            SQLServerIndexDefinition,
        )

        return SQLServerTableTypeDefinition(
            d,
            columns=[
                ColumnDefinition(
                    d,
                    "id",
                    IntegerType(d),
                    constraints=[ColumnConstraint(d, ColumnConstraintType.NOT_NULL)],
                )
            ],
            constraints=[
                TableConstraint(
                    d, TableConstraintType.PRIMARY_KEY, columns=["id"]
                )
            ],
            indexes=[SQLServerIndexDefinition(d, "ix_id", ["id"])],
        )

    def clr_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerClrTypeDefinition,
        )

        return SQLServerClrTypeDefinition(d, "assembly", "Namespace.Class")

    def drop_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerDropTypeExpression,
        )

        return SQLServerDropTypeExpression(d, Type(d, "type_name"))

    def rename_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerRenameTypeExpression,
        )

        return SQLServerRenameTypeExpression(d, "old_name", "new_name")

    def column_definition(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.column import (
            SQLServerColumnDefinition,
        )

        return SQLServerColumnDefinition(d, "id", IntegerType(d))

    def alter_column(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.alter_column import (
            SQLServerAlterColumn,
        )

        return SQLServerAlterColumn(d, "c", data_type="INT")

    def create_table(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.create_table import (
            SQLServerCreateTableExpression,
        )

        return SQLServerCreateTableExpression(d, _table_obj(d), [_integer_column(d)])

    def as_graph_table(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.graph import (
            SQLServerAsGraphTableExpression,
            SQLServerGraphTableKind,
        )

        return SQLServerAsGraphTableExpression(d, SQLServerGraphTableKind.NODE)

    def create_function(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.routine import (
            SQLServerCreateFunctionExpression,
        )

        return SQLServerCreateFunctionExpression(
            d, "fn", returns="INT", body="SELECT 1"
        )

    def create_procedure(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.routine import (
            SQLServerCreateProcedureExpression,
        )

        return SQLServerCreateProcedureExpression(d, "p", body="SELECT 1")

    def create_trigger(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.trigger import (
            SQLServerCreateTriggerExpression,
        )

        return SQLServerCreateTriggerExpression(
            d, "trg", "t", timing="AFTER", events=["INSERT"], body="SELECT 1",
        )

    def sqlserver_merge(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.dml import (
            SQLServerMergeExpression,
        )

        return SQLServerMergeExpression(
            d,
            target_table=_table_obj(d),
            source=NamedRelationRef(d, Table(d, "src")),
            on_condition=_column_predicate(d),
        )

    def option_hint(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.option_hint import (
            maxdop_hint,
            SQLServerOptionHintClause,
        )

        return SQLServerOptionHintClause(d, [maxdop_hint(4)])

    def pseudo_column(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.graph import (
            SQLServerGraphPseudoColumn,
        )

        return SQLServerGraphPseudoColumn(d, "$node_id", table="g")

    def graph_pattern(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.graph import (
            SQLServerGraphEdgeRef,
            SQLServerGraphNodeRef,
            SQLServerGraphPattern,
        )

        return SQLServerGraphPattern(
            d,
            SQLServerGraphNodeRef(d, "people"),
            [(SQLServerGraphEdgeRef(d, "knows"), SQLServerGraphNodeRef(d, "friends"))],
        )

    def match_predicate(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.graph import (
            SQLServerMatchPredicate,
        )

        return SQLServerMatchPredicate(d, graph_pattern(d))

    def shortest_path(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.graph import (
            SQLServerShortestPathExpression,
        )

        return SQLServerShortestPathExpression(d, graph_pattern(d), 1, 3)

    # ``make_instance`` matches suffixes with ``str.endswith``, and core also has
    # a ``pivot.PivotExpression``. The longer suffix keeps this registration on
    # the SQL Server class instead of capturing core's as well. Core's own
    # PivotExpression is left to the guess: SQL Server's PIVOT spelling needs an
    # aggregate the guess does not supply, and it is pinned as a non-render below
    # rather than given a constructor here.
    register_special_constructor(
        "sqlserver.expression.pivot.PivotExpression", pivot
    )
    register_special_constructor(
        "columnstore.SQLServerColumnstoreIndexExpression", columnstore
    )
    register_special_constructor(
        "partition.SQLServerPartitionByRangeClause", partition_range
    )
    register_special_constructor(
        "partition.SQLServerPartitionFunctionExpression", partition_function
    )
    register_special_constructor(
        "partition.SQLServerPartitionSchemeExpression", partition_scheme
    )
    register_special_constructor("type.SQLServerAliasTypeDefinition", alias_type)
    register_special_constructor("type.SQLServerTableTypeDefinition", table_type)
    register_special_constructor("type.SQLServerClrTypeDefinition", clr_type)
    register_special_constructor("type.SQLServerDropTypeExpression", drop_type)
    register_special_constructor("type.SQLServerRenameTypeExpression", rename_type)
    register_special_constructor("column.SQLServerColumnDefinition", column_definition)
    register_special_constructor("alter_column.SQLServerAlterColumn", alter_column)
    register_special_constructor(
        "create_table.SQLServerCreateTableExpression", create_table
    )
    register_special_constructor(
        "ddl.graph.SQLServerAsGraphTableExpression", as_graph_table
    )
    register_special_constructor(
        "ddl.routine.SQLServerCreateFunctionExpression", create_function
    )
    register_special_constructor(
        "ddl.routine.SQLServerCreateProcedureExpression", create_procedure
    )
    register_special_constructor(
        "ddl.trigger.SQLServerCreateTriggerExpression", create_trigger
    )
    register_special_constructor("dml.SQLServerMergeExpression", sqlserver_merge)
    register_special_constructor("option_hint.SQLServerOptionHintClause", option_hint)
    register_special_constructor("graph.SQLServerGraphPseudoColumn", pseudo_column)
    register_special_constructor("graph.SQLServerGraphPattern", graph_pattern)
    register_special_constructor("graph.SQLServerMatchPredicate", match_predicate)
    register_special_constructor(
        "graph.SQLServerShortestPathExpression", shortest_path
    )


register_specials()


# ---------------------------------------------------------------------------
# Lists that cannot grow or shrink silently
# ---------------------------------------------------------------------------

#: Classes the introspective constructor cannot build.
#:
#: Each is a real coverage gap, named here so it is visible rather than lost.
#: :func:`test_unconstructible_list_is_exact` pins the tuple against what the
#: constructor really skips, in both directions: a class that gains a
#: constructor fails here until this entry is removed, and a class that starts
#: failing to build fails here too. Neither can become a quiet skip.
#:
#: The reasons are grouped by cause, not by module, and all four are now the same
#: cause: a required parameter the introspective guess cannot satisfy, because it
#: sits behind a defaulted positional or is a member of a closed set. Registering a
#: constructor is the way to retire any of them.
#:
#: The four XML classes this tuple used to hold were never a gap in the classes.
#: ``XMLTableExpression`` wants ``columns: Sequence[XMLTableColumn]`` and the three
#: forest-shaped ones each want a ``Sequence`` of their own item type; the guess
#: read that annotation's *alias* name, ``"Sequence"``, decided it named a
#: catalogue object and handed the parameter a ``Sequence`` instead of a list. The
#: classes were fine and the harness was wrong. They construct now, and each one
#: turns out to be a genuine capability gap rather than a render, which is why all
#: four moved to :data:`LEGITIMATE_NON_RENDERS` rather than to a render assertion.
UNCONSTRUCTIBLE = (
    # ALTER CONSTRAINT. `name` and `constraint_type` sit behind defaulted
    # positionals and are keyword-only, so the introspective constructor skips
    # them and the class refuses an incomplete action (`ValueError: constraint_name
    # must be a non-empty string`, because the defaulted `constraint_name` stays
    # None).
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterConstraint",
    # VALIDATE CONSTRAINT. Same shape as AlterConstraint: the required `name` is
    # keyword-only behind a defaulted positional.
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.ValidateConstraint",
    # ADD DOMAIN CHECK. Widens a SQLPredicate into a DomainCheckConstraint and
    # needs one; the guess supplies a bare comparison whose literal would have
    # to render as a bind parameter, which DDL cannot carry. (It supplies a bare
    # *string* in fact: the annotation names a `DomainCheckConstraint`, whose
    # `\bDomain\b` fragment does not match inside the longer word, so the guess
    # falls through to its name-based default and the class raises
    # `TypeError: check must be a DomainCheckConstraint instance, got str`.)
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.AddDomainCheckAction",
    # ENUM type. Its `values` list is keyword-only behind a defaulted positional,
    # so the introspective constructor skips it and the type declares no members
    # (`ValueError: EnumType requires values`).
    "rhosocial.activerecord.backend.expression.types.enum_.EnumType",
)

#: Message fragments the pins below match on.
_NO_FORMATTER = "does not declare its dialect formatting method name"
#: The *dispatch* failure -- ``format_method`` named a method the dialect does
#: not define, so ``to_sql()`` never called anything. Core reported that as
#: ``AttributeError`` and now reports it as ``UnsupportedFeatureError``, which is
#: the type a dialect uses when it *knows* a statement and refuses it. The two are
#: the same type now, so the fragment is what separates them: this is the one
#: phrase only the dispatch's suggestion contains, offering to mix in a mixin.
#: A class that stopped being a dispatch failure and became a genuine refusal
#: would raise the same type and fail on the fragment instead.
_NO_SUCH_METHOD = "mix in the mixin that provides it"
_NO_SUCH_TYPE = "does not support the generic type"

#: Classes that construct but cannot render, for a reason belonging to their own
#: tree rather than to a defect. Each entry pins the exception type *and* a
#: message fragment, so a class that starts failing for a *different* reason
#: fails here instead of passing quietly -- which is the whole point, given that
#: this matrix used to swallow every one of these.
LEGITIMATE_NON_RENDERS = {
    # ---- bases that name an expression category, not a renderable thing ----
    # Each of these is a base class that deliberately declares no `format_method`,
    # so `to_sql()` reports that there is nothing to dispatch. They are not
    # `inspect.isabstract` -- they are concrete enough to construct -- so the
    # registry keeps them, and each is pinned to its exact message so a base that
    # started rendering fails here instead of passing quietly.
    "rhosocial.activerecord.backend.expression.bases.SQLPredicate": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.bases.SQLValueExpression": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # The roots of the object tree. Each concrete object overrides `format_method`
    # with its own `format_*_object`; the base names only what every catalogue
    # object has in common.
    "rhosocial.activerecord.backend.expression.objects.base.SchemaObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.relation.RelationObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.routine.RoutineObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.type_.TypeObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # Expression-category bases whose concrete members each name their own
    # formatter: an ALTER TABLE action, an INSERT row source, a transaction
    # step, a temporal value, an introspection query.
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterTableAction": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.dml.InsertDataSource": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.transaction.TransactionExpression": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.datetime._TemporalValueExpression": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.introspection.IntrospectionExpression": (
        NotImplementedError,
        _NO_FORMATTER,
    ),

    # ---- the root of the row-source tree ----
    # No concrete source renders through `format_table_source`; each overrides
    # `format_method`. Rendering the base would mean inventing SQL for an object
    # that carries nothing but an alias. Dispatch failure, so UnsupportedFeatureError.
    "rhosocial.activerecord.backend.expression.sources.base.TableSource": (
        UnsupportedFeatureError,
        _NO_SUCH_METHOD,
    ),

    # ---- features SQL Server does not model ----
    # Each of these names a `format_method` the dialect does not define, so the
    # dispatch fails before any formatter is called: `to_sql()` reports that the
    # dialect declares no such method, not that it knows the statement and refuses
    # it. Those are now the *same* exception type -- core raised AttributeError
    # for the first and unified it to UnsupportedFeatureError with everything
    # else -- so the pinned type no longer tells the two apart and the pinned
    # fragment does. See _NO_SUCH_METHOD.
    #
    # SQL/XML (thirteen): SQL Server's native XML/Xquery is not the SQL/XML
    # feature set, which is why every SQLXML* protocol is in the dialect's
    # negative list.
    #
    # Nine are the XMLAGG / XMLCOMMENT / XMLElement / XMLEXISTS / XMLPARSE /
    # XMLPI / XMLQUERY / XMLROOT / XMLSERIALIZE family; four more are XMLTABLE,
    # XMLATTRIBUTES, XMLCONCAT and XMLFOREST. All thirteen give the same answer
    # to the same question -- `SQLServerDialect` declares no `format_xml*` method
    # at all, so the dispatch refuses each by name before any formatter is
    # reached. The second four only became visible when the testsuite's
    # introspective constructor stopped reading a `Sequence[...]` annotation as a
    # request for a `Sequence` catalogue object; see the note above
    # UNCONSTRUCTIBLE. They are not a new gap in SQL Server -- the other nine
    # had been saying the same thing all along.
    "rhosocial.activerecord.backend.expression.xml.XMLAggExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLAttributesExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLCommentExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLConcatExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLElementExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLExistsExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLForestExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLPIExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLParseExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLQueryExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLRootExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLSerializeExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLTableExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    # CREATE/ALTER/DROP DOMAIN (nine): SQL Server has no DOMAIN. The three
    # statements and their five actions plus the check constraint and the domain
    # value all name a formatter the dialect does not have.
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.CreateDomainExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.AlterDomainExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DropDomainExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DomainCheckConstraint": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DomainValueExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DropDomainCheckAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DropDomainDefaultAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DropDomainNotNullAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.RenameDomainAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.SetDomainDefaultAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.SetDomainNotNullAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    # SQL/PGQ property graphs (eight): no GRAPH_TABLE, so no graph DDL either.
    # The negative list records GraphTableSupport; these are the same gap seen
    # from the expression tree.
    "rhosocial.activerecord.backend.expression.graph.GraphTableExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.VertexTable": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.EdgeTable": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.ColumnsClause": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.TablePropertiesClause": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.CreatePropertyGraphExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.AlterPropertyGraphExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.DropPropertyGraphExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    # PIVOT / UNPIVOT (two): SQL Server spells PIVOT its own way, through
    # SQLServerPivotExpression. Core's generic PIVOT is not the same statement.
    "rhosocial.activerecord.backend.expression.pivot.PivotExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.pivot.UnpivotExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    # COMMENT ON: SQL Server has no standalone COMMENT ON statement, which the
    # dialect's negative list records as CommentSupport.
    "rhosocial.activerecord.backend.expression.statements.ddl_comment.CommentOnExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),

    # ---- the root of the type tree ----
    # Every concrete type declares its own generic `name`, which is what
    # `format_data_type` dispatches on; the root declares none, so there is
    # nothing to dispatch. TypeError, not UnsupportedFeatureError, because the
    # class is incomplete rather than the dialect being unable.
    "rhosocial.activerecord.backend.expression.types._base.DataType": (
        TypeError,
        "does not declare a valid generic type name",
    ),
    # Core types with no SQL Server spelling (eight). SQL Server has no ARRAY,
    # no JSONB, no TIMESTAMPTZ, and spells BINARY as its own types, so these
    # declare a generic name the dialect does not implement. This is a
    # capability gap in this backend's type table, not a defect in the class.
    "rhosocial.activerecord.backend.expression.types.array.ArrayType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.binary.BinaryType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.binary.VarBinaryType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.IntervalType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.TimeTzType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.TimestampTzType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.json_.JsonBType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.uuid_.UUIDType": (
        TypeError, _NO_SUCH_TYPE
    ),

    # ---- core expressions SQL Server has no T-SQL spelling for ----
    #
    # These four are the shadowing problem, and they are the reason this matrix
    # exists in this form. SQL Server's own T-SQL DDL for full-text indexes,
    # functions and triggers is spelled by formatters that took over the *core
    # formatter names*: ``format_create_fulltext_index_statement`` here takes
    # ``(table, columns, key_index, catalog_name)`` where core's takes the
    # expression, and ``format_create_function_statement`` takes a
    # ``SQLServerCreateFunctionExpression`` where core's takes a
    # ``CreateFunctionExpression``. So when the core expression dispatches --
    # which is what ``format_method`` does -- it calls a function whose
    # signature it cannot satisfy.
    #
    # This is a recorded gap, not an oversight, and each entry pins the exact
    # failure so the shape of it cannot change unnoticed. The fix is to rename
    # the backend's formatters (``format_sqlserver_create_fulltext_index_statement``
    # and friends) so the core names are free again, and to point the backend's
    # own expressions at the renamed methods. That is a rename across five files
    # and four protocol declarations, which is its own change with its own
    # review; it is not smuggled in here behind a comment.
    "rhosocial.activerecord.backend.expression.statements.ddl_index.CreateFulltextIndexExpression": (
        TypeError,
        "missing 3 required positional arguments",
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_index.DropFulltextIndexExpression": (
        ValueError,
        "name must be a non-empty string",
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_function.CreateFunctionExpression": (
        ValueError,
        "function name is required",
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_trigger.DropTriggerExpression": (
        ValueError,
        "trigger name is required",
    ),
}


# ---------------------------------------------------------------------------
# The local SQL assertion: classify the outcome instead of swallowing it
# ---------------------------------------------------------------------------


def assert_sql_roundtrip_classified(
    fqn: str, instance, dialect
) -> str:
    """Assert an expression's SQL survives the round-trip, or say precisely why not.

    Four outcomes, each asserted:

    * **renders** -- all three encodings must restore byte-identical SQL *and*
      byte-identical bind parameters.
    * a member of :data:`LEGITIMATE_NON_RENDERS` -- unrenderable by design,
      asserted as its exact type *and* message fragment.
    * ``UnsupportedFeatureError`` from a class *not* named in the dict -- SQL
      Server does not model the feature. Asserted as exactly that type, so a
      subclass raised for an unrelated reason is still visible rather than passing.
    * **anything else** -- a failure naming the class and the exception.

    The dict is consulted before the ``UnsupportedFeatureError`` branch, not
    after. A missing formatter is now reported through that same type, so with the
    ``except`` clause in front a pinned dispatch-failure entry would never be
    looked up: its type and message would go unasserted on this path and the
    table would have stopped saying which of the two causes each class has.
    Checking the pin first keeps both halves of it load-bearing.

    Args:
        fqn: Fully qualified name of the class, used in every message.
        instance: The expression to render.
        dialect: The dialect to render it against.

    Returns:
        A short string naming the branch taken, so the classification
        distribution can be reported.

    Raises:
        AssertionError: On a round-trip mismatch, on an unexpected exception
            type, or when a class's rendering outcome changed.
    """
    from rhosocial.activerecord.backend.expression.serialization import (
        deserialize,
        deserialize_json,
        deserialize_xml,
        serialize,
        serialize_json,
        serialize_xml,
    )

    try:
        expected_sql, expected_params = instance.to_sql()
    except Exception as exc:
        if fqn in LEGITIMATE_NON_RENDERS:
            expected_type, fragment = LEGITIMATE_NON_RENDERS[fqn]
            assert type(exc) is expected_type, (
                f"{fqn}: LEGITIMATE_NON_RENDERS pins this class as a legitimate "
                f"non-render raising {expected_type.__name__}, but it raised "
                f"{type(exc).__name__}: {exc}"
            )
            assert fragment in str(exc), (
                f"{fqn}: expected {expected_type.__name__} and was expected to say "
                f"{fragment!r}, but it said: {exc}"
            )
            return "non-render"
        if type(exc) is UnsupportedFeatureError:
            return "unsupported"
        raise AssertionError(
            f"{fqn}: to_sql() raised {type(exc).__name__}, which is neither a "
            f"render nor a classified non-render, and this is a defect.\n"
            f"  UnsupportedFeatureError means the dialect lacks the feature and "
            f"is always allowed.\n"
            f"  A class that cannot render for a reason belonging to its own "
            f"tree belongs in LEGITIMATE_NON_RENDERS.\n"
            f"  Exception: {exc}"
        ) from exc

    for channel, decoded in (
        ("dict", deserialize(serialize(instance), dialect)),
        ("json", deserialize_json(serialize_json(instance), dialect)),
        ("xml", deserialize_xml(serialize_xml(instance), dialect)),
    ):
        decoded_sql, decoded_params = decoded.to_sql()
        assert decoded_sql == expected_sql, (
            f"{fqn}: {channel} round-trip changed the SQL.\n"
            f"  original: {expected_sql!r}\n"
            f"  {channel}: {decoded_sql!r}"
        )
        assert decoded_params == expected_params, (
            f"{fqn}: {channel} round-trip changed the bind parameters.\n"
            f"  original: {expected_params!r}\n"
            f"  {channel}: {decoded_params!r}"
        )
    return "rendered"


@pytest.fixture(params=sorted(REGISTERED), ids=sorted(REGISTERED))
def sqlserver_expr_case(request, sqlserver_dialect):
    """One expression instance per collected class, or a pinned skip.

    A class that cannot be built is a skip only if it is named in
    :data:`UNCONSTRUCTIBLE`; anything else fails here rather than disappearing,
    because an unnamed skip is a coverage hole with no marker.
    """
    fqn = request.param
    cls = REGISTERED[fqn]
    instance, source = make_instance(cls, sqlserver_dialect)
    if instance is None:
        assert fqn in UNCONSTRUCTIBLE, (
            f"{fqn} cannot be built by the generic constructor ({source}) and is "
            f"not in UNCONSTRUCTIBLE. Either register a special constructor for "
            f"it or add it to the tuple with a reason -- do not let it disappear "
            f"into a skip."
        )
        pytest.skip(f"{fqn}: pinned in UNCONSTRUCTIBLE, cannot be constructed ({source})")
    return fqn, instance


class TestSQLServerExpressionRoundtrip:
    """All constructible expression classes round-trip through all encodings."""

    def test_get_params_roundtrip(self, sqlserver_expr_case, sqlserver_dialect):
        fqn, instance = sqlserver_expr_case
        roundtrip_expression(fqn, instance, sqlserver_dialect)

    def test_to_sql_roundtrip_classified(self, sqlserver_expr_case, sqlserver_dialect):
        """A render must survive the round-trip; a non-render must be classified."""
        fqn, instance = sqlserver_expr_case
        assert_sql_roundtrip_classified(fqn, instance, sqlserver_dialect)


class TestMatrixIntegrity:
    """Guards on the matrix and its lists, so neither can quietly change."""

    def test_unconstructible_list_is_exact(self, sqlserver_dialect):
        """Pin the unconstructible tuple against what the constructor really skips.

        Two directions are checked. A class named here that now builds has gained
        a constructor and the entry is stale; a class that fails to build without
        being named would become a silent skip. Both fail here.
        """
        ExpressionRegistry._auto_register_builtins()
        actual = tuple(
            sorted(
                fqn
                for fqn in REGISTERED
                if make_instance(REGISTERED[fqn], sqlserver_dialect)[0] is None
            )
        )
        assert actual == tuple(sorted(UNCONSTRUCTIBLE)), (
            "the set of expression classes the generic constructor cannot build "
            "changed.\n"
            f"  now skipped but not named: "
            f"{sorted(set(actual) - set(UNCONSTRUCTIBLE))}\n"
            f"  named but now built: "
            f"{sorted(set(UNCONSTRUCTIBLE) - set(actual))}\n"
            "Each new entry needs a reason in the comment above UNCONSTRUCTIBLE."
        )

    def test_unconstructible_entries_are_real_classes(self):
        """Every entry names a class that was actually collected.

        A typo in the tuple would otherwise exempt nothing while still reading as
        a deliberate decision.
        """
        unknown = set(UNCONSTRUCTIBLE) - set(REGISTERED)
        assert not unknown, (
            f"UNCONSTRUCTIBLE names classes that were not registered: {sorted(unknown)}"
        )

    def test_legitimate_non_renders_are_real_classes(self):
        """Every pinned non-render names a class that was actually collected."""
        unknown = set(LEGITIMATE_NON_RENDERS) - set(REGISTERED)
        assert not unknown, (
            f"LEGITIMATE_NON_RENDERS names classes that were not registered: "
            f"{sorted(unknown)}"
        )

    def test_pinned_non_render_really_does_not_render(self, sqlserver_dialect):
        """Each pinned entry still raises what it claims, for the stated reason.

        Without this, an entry could sit in the dict for a class that renders
        perfectly well, and the matrix would be asserting nothing about it.
        """
        for fqn, (expected_type, fragment) in LEGITIMATE_NON_RENDERS.items():
            instance, source = make_instance(REGISTERED[fqn], sqlserver_dialect)
            assert instance is not None, (
                f"{fqn} is pinned as a non-render but could not be constructed "
                f"({source})"
            )
            with pytest.raises(expected_type) as exc_info:
                instance.to_sql()
            assert fragment in str(exc_info.value), (
                f"{fqn}: expected the message to mention {fragment!r}, got: "
                f"{exc_info.value}"
            )

    def test_matrix_covers_both_packages(self):
        """The matrix covers every concrete class both packages define.

        Re-walked here rather than trusting the module-level collection, so a
        class that appeared after import is caught. The package walk is used
        rather than the registry because the registry also holds whatever
        backends other test modules happened to import -- which is exactly the
        non-determinism this matrix moved off.
        """
        ExpressionRegistry._auto_register_builtins()
        for pkg in (CORE_EXPR_PKG, SS_EXPR_PKG):
            expected = set(_collect(pkg))
            covered = {
                fqn for fqn in REGISTERED if fqn.startswith(f"{pkg}.")
            }
            assert expected == covered, (
                f"the set of classes {pkg} defines changed after collection.\n"
                f"  now defined but not covered: {sorted(expected - covered)}\n"
                f"  covered but no longer defined: {sorted(covered - expected)}"
            )
        assert len(REGISTERED) > 300, (
            f"only {len(REGISTERED)} classes collected; the package walk may "
            f"have stopped early"
        )

    def test_every_covered_class_is_registered_for_deserialization(self):
        """A class in the matrix can be found again when deserializing.

        Deserialization looks the class up by name, so a class the matrix renders
        but the registry cannot resolve would round-trip into the wrong thing or
        nothing at all.
        """
        ExpressionRegistry._auto_register_builtins()
        unresolved = sorted(set(REGISTERED) - set(ExpressionRegistry._registry))
        assert not unresolved, (
            f"the matrix covers classes the registry cannot resolve: {unresolved}"
        )

    def test_coverage_report(self, sqlserver_dialect):
        """Surface what the matrix covers, so coverage stays transparent."""
        ExpressionRegistry._auto_register_builtins()
        branches = {"rendered": 0, "unsupported": 0, "non-render": 0}
        constructible = []
        for fqn in sorted(REGISTERED):
            instance, source = make_instance(REGISTERED[fqn], sqlserver_dialect)
            if instance is None:
                continue
            constructible.append(fqn)
            branches[
                assert_sql_roundtrip_classified(fqn, instance, sqlserver_dialect)
            ] += 1
        assert constructible
        print(
            f"\nexpression matrix: {len(REGISTERED)} collected, "
            f"{len(constructible)} constructible, "
            f"{len(UNCONSTRUCTIBLE)} pinned-unconstructible; "
            f"rendered {branches['rendered']}, "
            f"unsupported {branches['unsupported']}, "
            f"pinned non-render {branches['non-render']}"
        )
        for fqn in UNCONSTRUCTIBLE:
            print(f"  not constructible: {fqn}")