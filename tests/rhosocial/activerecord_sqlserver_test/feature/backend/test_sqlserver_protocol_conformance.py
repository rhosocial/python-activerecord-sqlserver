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
    """Discover every generic dialect protocol defined in the protocols package."""
    from typing import Protocol

    discovered = {}
    for name, obj in inspect.getmembers(dialect_protocols, inspect.isclass):
        if Protocol in getattr(obj, "__mro__", []) and name.endswith("Support"):
            discovered[name] = obj
    return discovered


def _classified_keys(protocols) -> set:
    """Every exported name whose protocol is in *protocols*.

    Keyed by the names the protocols package exports rather than by
    ``__name__``, so an alias (``DDLTypeSupport`` is kept as a second name for
    ``DataTypeSupport``) counts as classified when its target is listed.
    """
    listed = {id(protocol) for protocol in protocols}
    return {
        name
        for name, protocol in get_all_generic_protocols().items()
        if id(protocol) in listed
    }


# Generic protocols SQLServerDialect satisfies.
SQLSERVER_PROTOCOLS = [
    dialect_protocols.AdvancedGroupingSupport,
    dialect_protocols.AlterTableModifierSupport,
    dialect_protocols.ArraySupport,
    dialect_protocols.AutoIncrementSupport,
    dialect_protocols.CTESupport,
    dialect_protocols.CollationSupport,
    dialect_protocols.ColumnAttributeSupport,
    dialect_protocols.ConstraintSupport,
    dialect_protocols.DataTypeSupport,
    dialect_protocols.DDLTypeSupport,
    dialect_protocols.ExplainSupport,
    dialect_protocols.FilterClauseSupport,
    dialect_protocols.GeneratedColumnSupport,
    dialect_protocols.GraphSupport,
    dialect_protocols.ILIKESupport,
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
    dialect_protocols.SetOperationSupport,
    dialect_protocols.TemporalTableSupport,
    dialect_protocols.TransactionControlSupport,
    dialect_protocols.TruncateSupport,
    dialect_protocols.UpsertSupport,
    dialect_protocols.WildcardSupport,
    dialect_protocols.WindowFunctionSupport,
    # The object protocols: one per kind. SQL Server is the engine that renders
    # all three namespace levels, so it inherits NamespaceSupport and every
    # kind's protocol, each naming a format_<kind>_object the dialect provides.
    dialect_protocols.NamespaceSupport,
    dialect_protocols.TableObjectSupport,
    dialect_protocols.ViewObjectSupport,
    dialect_protocols.MaterializedViewObjectSupport,
    dialect_protocols.ForeignTableObjectSupport,
    dialect_protocols.IndexObjectSupport,
    dialect_protocols.SequenceObjectSupport,
    dialect_protocols.TriggerObjectSupport,
    dialect_protocols.RoutineObjectSupport,
    dialect_protocols.TypeObjectSupport,
    dialect_protocols.SynonymObjectSupport,
    # DDL, one protocol per statement expression.
    dialect_protocols.CreateTableSupport,
    dialect_protocols.CreateTableAsSupport,
    dialect_protocols.CreateTableCloneSupport,
    dialect_protocols.CreateTableLikeSupport,
    dialect_protocols.CreateTableUsingTemplateSupport,
    dialect_protocols.DropTableSupport,
    dialect_protocols.AlterTableSupport,
    dialect_protocols.CreateViewSupport,
    dialect_protocols.DropViewSupport,
    dialect_protocols.MaterializedViewSupport,
    dialect_protocols.CreateIndexSupport,
    dialect_protocols.DropIndexSupport,
    dialect_protocols.FulltextIndexSupport,
    dialect_protocols.CreateSequenceSupport,
    dialect_protocols.DropSequenceSupport,
    dialect_protocols.AlterSequenceSupport,
    dialect_protocols.CreateTriggerSupport,
    dialect_protocols.DropTriggerSupport,
    dialect_protocols.CreateRoutineSupport,
    dialect_protocols.DropRoutineSupport,
    dialect_protocols.CreateTypeSupport,
    dialect_protocols.DropTypeSupport,
    dialect_protocols.AlterTypeSupport,
    dialect_protocols.CreateSchemaSupport,
    dialect_protocols.DropSchemaSupport,
    dialect_protocols.AlterDatabaseSupport,
    dialect_protocols.DateTimeSupport,
    dialect_protocols.DqlOrderSupport,
    dialect_protocols.PivotSupport,
]


# Generic protocols SQLServerDialect intentionally does NOT implement.
#
# Listing them makes the omission a deliberate, tested contract: if SQL Server
# ever satisfies one by accident, the negative test fails and forces a conscious
# decision (move to SQLSERVER_PROTOCOLS or revert).
SQLSERVER_NOT_IMPLEMENTED = [
    # --- Intentional non-support ---
    # SQL Server has no standalone COMMENT ON statement; comments use
    # sp_addextendedproperty (not modelled as a COMMENT ON expression).
    dialect_protocols.CommentSupport,
    # CREATE/DROP DATABASE are rendered by SQLServerDatabaseMixin, but the
    # per-statement protocols also require the generic option probes
    # (supports_database_encoding, supports_undrop_database, and the rest),
    # which SQL Server has no spelling for. Tracked gap rather than an
    # omission of intent.
    dialect_protocols.CreateDatabaseSupport,
    dialect_protocols.DropDatabaseSupport,
    # SQL Server has no CREATE/ALTER/DROP DOMAIN.
    dialect_protocols.CreateDomainSupport,
    dialect_protocols.AlterDomainSupport,
    dialect_protocols.DropDomainSupport,
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
        positive = _classified_keys(SQLSERVER_PROTOCOLS)
        negative = _classified_keys(SQLSERVER_NOT_IMPLEMENTED)

        overlap = positive & negative
        assert not overlap, f"Protocols in BOTH lists: {sorted(overlap)}"

        unclassified = all_protos - positive - negative
        assert not unclassified, (
            f"Generic protocols not classified for SQL Server: {sorted(unclassified)}. "
            f"Add each to SQLSERVER_PROTOCOLS or SQLSERVER_NOT_IMPLEMENTED."
        )