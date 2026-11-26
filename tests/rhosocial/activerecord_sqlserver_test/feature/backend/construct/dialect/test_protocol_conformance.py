# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/dialect/test_protocol_conformance.py
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
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.suggestion import protocols as suggestion_protocols
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
    ``__name__``, so an alias (``DataTypeSupport`` is kept as a second name for
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
    dialect_protocols.AutoIncrementColumnSupport,
    dialect_protocols.CTESupport,
    dialect_protocols.CollationSupport,
    dialect_protocols.ColumnAttributeSupport,
    suggestion_protocols.ColumnTypeSuggestionSupport,
    dialect_protocols.ConstraintSupport,
    dialect_protocols.DataTypeSupport,
    dialect_protocols.DatabaseAssignedColumnSupport,
    dialect_protocols.DataTypeSupport,
    dialect_protocols.ExplainSupport,
    dialect_protocols.FilterClauseSupport,
    dialect_protocols.GeneratedColumnSupport,
    dialect_protocols.GraphSupport,
    dialect_protocols.ILIKESupport,
    dialect_protocols.IdentityColumnSupport,
    suggestion_protocols.GeneratedValueSuggestionSupport,
    # Core split the single introspection protocol into four families, each
    # with an async twin. SQL Server answers three of them (structure,
    # operational statistics and data profiling); the fourth, DDL extraction,
    # is a declared gap classified (and refused) below.
    dialect_protocols.StructureIntrospectionSupport,
    dialect_protocols.AsyncStructureIntrospectionSupport,
    dialect_protocols.OperationalStatsIntrospectionSupport,
    dialect_protocols.AsyncOperationalStatsIntrospectionSupport,
    dialect_protocols.DataProfileIntrospectionSupport,
    dialect_protocols.AsyncDataProfileIntrospectionSupport,
    dialect_protocols.JSONSupport,
    dialect_protocols.JoinSupport,
    dialect_protocols.LateralJoinSupport,
    dialect_protocols.LockingSupport,
    dialect_protocols.MergeSupport,
    dialect_protocols.OrderedSetAggregationSupport,
    suggestion_protocols.PartitionAddSuggestionSupport,
    suggestion_protocols.PartitionBuildSuggestionSupport,
    suggestion_protocols.PartitionDropSuggestionSupport,
    suggestion_protocols.PartitionMergeSuggestionSupport,
    suggestion_protocols.PartitionRetentionSuggestionSupport,
    suggestion_protocols.PartitionSplitSuggestionSupport,
    suggestion_protocols.PartitionTableAlterSuggestionSupport,
    suggestion_protocols.PartitionTableDropSuggestionSupport,
    dialect_protocols.PartitionSupport,
    dialect_protocols.QualifyClauseSupport,
    dialect_protocols.UUIDSupport,
    dialect_protocols.ReturningSupport,
    suggestion_protocols.FunctionSuggestionSupport,
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
    dialect_protocols.TimestampSupport,
    dialect_protocols.DqlOrderSupport,
    dialect_protocols.PivotSupport,
    # Protocols added by the core refactor that this dialect satisfies.
    dialect_protocols.DDLColumnSupport,
    dialect_protocols.DMLSupport,
    dialect_protocols.DQLSupport,
    dialect_protocols.DatabaseNameSupport,
    dialect_protocols.DateTimeSupport,
    dialect_protocols.ExpressionSupport,
    dialect_protocols.FunctionCallSupport,
    dialect_protocols.PredicateSupport,
    dialect_protocols.PropertyGraphNameSupport,
    dialect_protocols.RelationSourceSupport,
    dialect_protocols.SchemaNameSupport,
    dialect_protocols.TrimSupport,
]


# Introspection families whose capability answer is "no": the protocol members
# are structurally present because core's mixin supplies refusing stubs, so
# ``isinstance`` alone would call the family implemented. The classification
# here is by the family's capability gate instead -- negative, with an explicit
# refusal test -- and the implementation is deliberately not flipped: SQL
# Server has no per-object DDL retrieval, and an assembly would claim the
# engine said something it did not.
SQLSERVER_INTROSPECTION_REFUSED = [
    dialect_protocols.DdlExtractionIntrospectionSupport,
    dialect_protocols.AsyncDdlExtractionIntrospectionSupport,
]


# Generic protocols SQLServerDialect intentionally does NOT implement.
#
# Listing them makes the omission a deliberate, tested contract: if SQL Server
# ever satisfies one by accident, the negative test fails and forces a conscious
# decision (move to SQLSERVER_PROTOCOLS or revert).
SQLSERVER_NOT_IMPLEMENTED = [
    # --- Tracked gaps ---
    # SQL Server does hold DDL inside a transaction, but SQLServerDialect has
    # not exposed supports_transactional_ddl() yet, so the dialect cannot
    # answer. Move it to SQLSERVER_PROTOCOLS once the probe lands.
    dialect_protocols.TransactionalDDLSupport,
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
    # SQL Server has no LPAD / RPAD / REPEAT functions; padding is spelled with
    # REPLICATE together with RIGHT / LEFT.
    dialect_protocols.LpadSupport,
    dialect_protocols.RepeatSupport,
    dialect_protocols.RpadSupport,
]


class TestDialectProtocolConformance:
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


class TestDialectNegativeProtocolConformance:
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
        refused = _classified_keys(SQLSERVER_INTROSPECTION_REFUSED)

        overlap = (positive & negative) | (positive & refused) | (negative & refused)
        assert not overlap, f"Protocols in more than one list: {sorted(overlap)}"

        unclassified = all_protos - positive - negative - refused
        assert not unclassified, (
            f"Generic protocols not classified for SQL Server: {sorted(unclassified)}. "
            f"Add each to SQLSERVER_PROTOCOLS, SQLSERVER_NOT_IMPLEMENTED or "
            f"SQLSERVER_INTROSPECTION_REFUSED."
        )

    def test_the_refused_introspection_family_is_capability_false(self):
        """The DDL family is absent by capability, and refuses with a name."""
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        dialect = SQLServerDialect(SQLSERVER_VERSION)
        assert isinstance(dialect, dialect_protocols.DdlExtractionIntrospectionSupport)
        assert dialect.supports_ddl_extraction() is False
        assert dialect.supports_ddl_extraction_native() is False
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_ddl_statement_query_statement(object())


class TestTheBackendOwnAnswersAreTheEffectiveOnes:
    """A backend mixin's method must resolve to a backend class.

    The other checks in this file are about the *declaration*: the mixin
    declares the method, and the protocol declares it too. This one is
    about the *resolution*. A core class that wins the MRO makes the
    backend's implementation dead code, and the answer a caller gets is
    core's rather than the backend's -- so the backend never says what it
    means about itself, and nothing else in the suite notices: the
    declaration is there either way.

    A protocol class is a declaration rather than an implementation (its
    body is ``...``), so a core class may legitimately precede it; only
    the mixins are held to this.
    """

    def test_no_backend_method_is_shadowed_by_a_core_class(self):
        mro = type(SQLServerDialect(SQLSERVER_VERSION)).__mro__
        own = "rhosocial.activerecord.backend.impl.sqlserver"
        shadowed = []
        for klass in mro:
            if not klass.__module__.startswith(own):
                continue
            if not klass.__name__.endswith("Mixin"):
                continue
            for name in vars(klass):
                if not name.startswith(("format_", "supports_", "get_")):
                    continue
                if not callable(vars(klass)[name]):
                    continue
                winner = next((k for k in mro if name in k.__dict__), None)
                if winner is None or winner.__module__.startswith(own):
                    continue
                shadowed.append(f"{klass.__name__}.{name} -> {winner.__name__}")
        assert not shadowed, (
            "a core class wins these backend methods, so the backend's "
            f"implementation is dead code: {shadowed}"
        )


class TestIntrospectionFamilySplit:
    """Pin the adoption of core's four-family introspection split."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQLSERVER_VERSION)

    def test_the_four_families_import_from_their_own_core_modules(self):
        expected = {
            dialect_protocols.StructureIntrospectionSupport: (
                "rhosocial.activerecord.backend.dialect.protocols.introspect.structure"
            ),
            dialect_protocols.OperationalStatsIntrospectionSupport: (
                "rhosocial.activerecord.backend.dialect.protocols.introspect.operational_stats"
            ),
            dialect_protocols.DataProfileIntrospectionSupport: (
                "rhosocial.activerecord.backend.dialect.protocols.introspect.data_profile"
            ),
            dialect_protocols.DdlExtractionIntrospectionSupport: (
                "rhosocial.activerecord.backend.dialect.protocols.introspect.ddl_extraction"
            ),
        }
        for protocol, module in expected.items():
            assert protocol.__module__ == module, (
                f"{protocol.__name__} resolves to {protocol.__module__}, not {module}"
            )

    def test_the_old_single_protocol_names_are_gone(self):
        """Core removed them without aliases; nothing may import or re-add them."""
        assert not hasattr(dialect_protocols, "IntrospectionSupport")
        assert not hasattr(dialect_protocols, "AsyncIntrospectionSupport")

    def test_supports_partition_info_is_gone(self, dialect):
        """One question now has one name: the partition mixin's metadata probe."""
        assert not hasattr(dialect, "supports_partition_info")

    def test_the_partitions_cli_family_asks_the_metadata_probe(self, dialect):
        """``introspect partitions`` must gate on the read probe, not the DDL one."""
        from rhosocial.activerecord.backend.impl.sqlserver.cli.introspect import (
            _TYPE_CAPABILITIES,
        )

        assert _TYPE_CAPABILITIES["partitions"] == (
            "supports_partition_metadata_introspection"
        )
        assert isinstance(dialect, dialect_protocols.PartitionSupport)
        assert dialect.supports_partition_metadata_introspection() is True

    def test_the_absent_family_refuses_instead_of_answering(self, dialect):
        """Absence is a refusal with a name, never an empty list or a guess."""
        assert isinstance(dialect, dialect_protocols.StructureIntrospectionSupport)
        assert isinstance(
            dialect, dialect_protocols.DdlExtractionIntrospectionSupport
        )
        assert dialect.supports_ddl_extraction() is False
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_ddl_statement_query_statement(object())
