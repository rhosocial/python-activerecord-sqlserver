# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_protocol_conformance.py
"""
Generic protocol conformance tests for SQLServerDialect.

This module complements ``test_protocol_support.py`` (which covers the
SQL Server-specific protocols) by asserting how ``SQLServerDialect`` relates
to the *generic* dialect protocols declared in
``rhosocial.activerecord.backend.dialect.protocols``.

Coverage:
- Positive: SQLServerDialect implements every protocol in ``SQLSERVER_PROTOCOLS``.
- Negative: SQLServerDialect must NOT implement any protocol in
  ``SQLSERVER_NOT_IMPLEMENTED`` (intentional omissions + tracked gaps).
- Partition completeness: every generic protocol is classified in exactly one
  of the two lists, so a new protocol forces a conscious decision.
"""

import inspect

import pytest
from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

# Construction requires a version tuple; 2022 exercises the newest feature set.
SQLSERVER_VERSION = (16, 0, 0)


def get_all_protocol_methods(proto: type) -> set:
    """Extract all public member names from a protocol, including inherited."""
    members = set()
    for cls in proto.__mro__:
        if cls is object:
            continue
        for name in cls.__dict__:
            if name.startswith("_"):
                continue
            val = cls.__dict__[name]
            if callable(val) or isinstance(val, (property, classmethod, staticmethod)):
                members.add(name)
        members.update(
            k for k in getattr(cls, "__annotations__", {}) if not k.startswith("_")
        )
    return members


def get_all_generic_protocols() -> dict:
    """Discover every generic dialect protocol defined in protocols.py."""
    from typing import Protocol

    discovered = {}
    for name, obj in inspect.getmembers(dialect_protocols, inspect.isclass):
        if Protocol in getattr(obj, "__mro__", []) and name.endswith("Support"):
            discovered[name] = obj
    return discovered


# Generic protocols SQLServerDialect satisfies.
SQLSERVER_PROTOCOLS = [
    dialect_protocols.AdvancedGroupingSupport,
    dialect_protocols.AlterTableModifierSupport,
    dialect_protocols.ArraySupport,
    dialect_protocols.AutoIncrementSupport,
    dialect_protocols.CTESupport,
    dialect_protocols.CollationSupport,
    dialect_protocols.ConstraintSupport,
    dialect_protocols.DDLTypeSupport,
    dialect_protocols.ExplainSupport,
    dialect_protocols.FilterClauseSupport,
    dialect_protocols.GraphSupport,
    dialect_protocols.IndexSupport,
    dialect_protocols.IntrospectionSupport,
    dialect_protocols.JSONSupport,
    dialect_protocols.JoinSupport,
    dialect_protocols.LateralJoinSupport,
    dialect_protocols.LockingSupport,
    dialect_protocols.MergeSupport,
    dialect_protocols.OrderedSetAggregationSupport,
    dialect_protocols.PartitionSupport,
    dialect_protocols.QualifyClauseSupport,
    dialect_protocols.ReturningSupport,
    dialect_protocols.SQLFunctionSupport,
    dialect_protocols.SchemaSupport,
    dialect_protocols.SequenceSupport,
    dialect_protocols.SetOperationSupport,
    dialect_protocols.TableSupport,
    dialect_protocols.TemporalTableSupport,
    dialect_protocols.TransactionControlSupport,
    dialect_protocols.TriggerSupport,
    dialect_protocols.TruncateSupport,
    dialect_protocols.UpsertSupport,
    dialect_protocols.ViewSupport,
    dialect_protocols.WildcardSupport,
    dialect_protocols.WindowFunctionSupport,
]


# Generic protocols SQLServerDialect intentionally does NOT implement.
#
# Listing them makes the omission a deliberate, tested contract: if SQL Server
# ever satisfies one by accident, the negative test fails and forces a conscious
# decision (move to SQLSERVER_PROTOCOLS or revert).
SQLSERVER_NOT_IMPLEMENTED = [
    # --- Intentional non-support ---
    # SQL Server's native XML/XQuery (FOR XML, OPENXML, .query()/.value()) is not
    # the standard SQL/XML feature set, so no SQL/XML formatters are exposed.
    dialect_protocols.SQLXMLSupport,
    dialect_protocols.SQLXMLParsingSupport,
    dialect_protocols.SQLXMLSerializationSupport,
    dialect_protocols.SQLXMLConstructionSupport,
    dialect_protocols.SQLXMLAggregationSupport,
    dialect_protocols.SQLXMLQueryingSupport,
    # SQL Server has no SQL/PGQ property-graph GRAPH_TABLE expression.
    dialect_protocols.GraphTableSupport,
    # SQL Server has no ILIKE operator; case-insensitive matching is achieved
    # through collation rather than a dedicated operator.
    dialect_protocols.ILIKESupport,
    # SQL Server routines are T-SQL, not SQL/PSM; function DDL is exposed through
    # backend-specific protocols instead of the generic FunctionSupport.
    dialect_protocols.FunctionSupport,
    # --- Known gaps (feature exists, generic protocol not yet declared) ---
    # TODO: SQL Server supports computed columns (VIRTUAL by default, PERSISTED
    # stored), but the dialect exposes ``supports_generated_column`` (singular)
    # while the generic protocol requires ``supports_generated_columns`` (plural).
    # Rename/alias the method, then move this to SQLSERVER_PROTOCOLS.
    dialect_protocols.GeneratedColumnSupport,
]


class TestSQLServerDialectProtocolConformance:
    """Assert SQLServerDialect implements all generic protocols it declares."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQLSERVER_VERSION)

    @pytest.mark.parametrize("protocol", SQLSERVER_PROTOCOLS)
    def test_implements_protocol(self, dialect, protocol):
        """SQLServerDialect should implement each protocol in SQLSERVER_PROTOCOLS."""
        assert isinstance(dialect, protocol), (
            f"SQLServerDialect does not implement protocol {protocol.__name__}, "
            f"missing methods: {get_all_protocol_methods(protocol) - set(dir(dialect))}"
        )


class TestSQLServerDialectNegativeProtocolConformance:
    """Assert SQLServerDialect does not implement intentionally-unsupported protocols."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQLSERVER_VERSION)

    @pytest.mark.parametrize("protocol", SQLSERVER_NOT_IMPLEMENTED)
    def test_does_not_implement_protocol(self, dialect, protocol):
        """SQLServerDialect must NOT implement any protocol in SQLSERVER_NOT_IMPLEMENTED."""
        assert not isinstance(dialect, protocol), (
            f"SQLServerDialect unexpectedly implements {protocol.__name__}. "
            f"If intentional, move it from SQLSERVER_NOT_IMPLEMENTED to "
            f"SQLSERVER_PROTOCOLS (and implement the behaviour fully)."
        )

    def test_positive_and_negative_lists_partition_all_protocols(self):
        """Every generic protocol must be classified for SQL Server."""
        all_protos = set(get_all_generic_protocols())
        positive = {
            p.__name__
            for p in SQLSERVER_PROTOCOLS
            if p.__module__ == dialect_protocols.__name__
        }
        negative = {p.__name__ for p in SQLSERVER_NOT_IMPLEMENTED}

        overlap = positive & negative
        assert not overlap, f"Protocols in BOTH lists: {sorted(overlap)}"

        unclassified = all_protos - positive - negative
        assert not unclassified, (
            f"Generic protocols not classified for SQL Server: {sorted(unclassified)}. "
            f"Add each to SQLSERVER_PROTOCOLS or SQLSERVER_NOT_IMPLEMENTED."
        )
