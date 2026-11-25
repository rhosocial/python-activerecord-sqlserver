# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/test_change_point_suggestions.py
"""Offline contract tests for SQL Server's four migration change-point answers.

No server is needed: the dialect's own formatters render every returned node,
so these tests check both the tri-state value and the exact SQL of a real chain.
Each ``False`` answer is backed by a documented grammar/capability reason in
the corresponding suggestion module; the tests point at those words so a future
edit cannot quietly turn a documented refusal into an invented action.
"""
import dataclasses
import importlib
import re

import pytest

from rhosocial.activerecord.backend.dialect.partition_capability import PartitionCapability
from rhosocial.activerecord.backend.expression import Column as ExprColumn
from rhosocial.activerecord.backend.expression import Literal
from rhosocial.activerecord.backend.expression.objects import Table as TableObject
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements import (
    CreateIndexStatement,
    DropIndexStatement,
    IndexDefinition,
)
from rhosocial.activerecord.backend.expression.statements.ddl_partition import PartitionClause
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddIndexAction,
    AddTableConstraintAction,
    AlterTableStatement,
    DropIndexAction,
    DropTableConstraintAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnDefinition,
    ConstraintValidation,
    TableCheckConstraint,
    TableConstraint,
    TableExcludeConstraint,
    TableForeignKeyConstraint,
    TablePrimaryKeyConstraint,
    TableUniqueConstraint,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.sqlserver.backend.backend import SQLServerUnicodeDialect
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionSchemeExpression,
    SQLServerSwitchPartitionExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.index import SQLServerIndexDefinition
from rhosocial.activerecord.backend.suggestion import (
    ColumnReorderSuggestion,
    PartitionSchemeChangeSuggestion,
    TableConstraintChangeSuggestion,
    TableIndexChangeSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    ColumnReorderSuggestionSupport,
    PartitionSchemeChangeSuggestionSupport,
    TableConstraintChangeSuggestionSupport,
    TableIndexChangeSuggestionSupport,
)
from rhosocial.activerecord.migration.schema_change import _freeze

_SUGGESTION_PACKAGE = "rhosocial.activerecord.backend.impl.sqlserver.suggestion"

CASES = (
    ("column_reorder", ColumnReorderSuggestion, ColumnReorderSuggestionSupport,
     "suggest_column_reorder", "column_reorder_suggestion"),
    ("table_constraint_change", TableConstraintChangeSuggestion,
     TableConstraintChangeSuggestionSupport, "suggest_table_constraint_change",
     "table_constraint_change_suggestion"),
    ("table_index_change", TableIndexChangeSuggestion,
     TableIndexChangeSuggestionSupport, "suggest_table_index_change",
     "table_index_change_suggestion"),
    ("partition_scheme_change", PartitionSchemeChangeSuggestion,
     PartitionSchemeChangeSuggestionSupport, "suggest_partition_scheme_change",
     "partition_scheme_change_suggestion"),
)


@pytest.fixture
def dialect():
    return SQLServerDialect((16, 0, 0))


def _sql(operations):
    return " ".join(expression.to_sql()[0] for expression in operations)


def _docstring(module_name):
    return importlib.import_module(f"{_SUGGESTION_PACKAGE}.{module_name}").__doc__ or ""


_SWITCH_SOURCE = re.compile(r"\bALTER\s+TABLE\s+(\S+)\s+SWITCH\b", re.IGNORECASE)
_SWITCH_TARGET = re.compile(
    r"\bSWITCH(?:\s+PARTITION\s+\d+)?\s+TO\s+(\S+)", re.IGNORECASE
)
_DROP_OBJECT = re.compile(r"\bDROP\s+(TABLE|SCHEMA)\b", re.IGNORECASE)


def _plain(name):
    """Strip quoting so a rendered ``[dbo].[events]`` reads as ``dbo.events``."""
    return name.replace("[", "").replace("]", "").lower()


def _assert_data_preserved(operations, live="events"):
    """Guard a suggestion chain: no destructive DDL, no SWITCH-out left open.

    ``ALTER TABLE ... SWITCH TO`` reassigns a partition's storage to the target
    (Microsoft Learn, ``ALTER TABLE (Transact-SQL)`` / SWITCH). A chain that
    switches data out of the live table must switch it back in before it ends,
    otherwise the live table is left without its rows. ``DROP TABLE`` and
    ``DROP SCHEMA`` are never an acceptable way to finish a chain either.
    """
    if operations is None or operations is False:
        return
    outside = set()
    for expression in operations:
        sql = expression.to_sql()[0]
        assert not _DROP_OBJECT.search(sql), f"destructive statement returned: {sql}"
        source = _SWITCH_SOURCE.search(sql)
        target = _SWITCH_TARGET.search(sql)
        if source is None or target is None:
            continue
        src, dst = _plain(source.group(1)), _plain(target.group(1))
        if src == _plain(live) and dst != _plain(live):
            outside.add(dst)
        elif dst == _plain(live) and src != _plain(live):
            outside.discard(src)
    assert not outside, f"live table data left outside: {sorted(outside)}"


def _constraint_point(table_name="events", old=(), new=()):
    """A change point as core builds it: frozen projections plus live declarations."""
    return TableConstraintChangeSuggestion(
        table_name=table_name,
        old_constraints=tuple(_freeze(value) for value in old),
        new_constraints=tuple(_freeze(value) for value in new),
        old_constraint_declarations=tuple(old),
        new_constraint_declarations=tuple(new),
    )


def _index_point(table_name="events", old=(), new=()):
    return TableIndexChangeSuggestion(
        table_name=table_name,
        old_indexes=tuple(_freeze(value) for value in old),
        new_indexes=tuple(_freeze(value) for value in new),
        old_index_declarations=tuple(old),
        new_index_declarations=tuple(new),
    )


class TestProtocolRegistration:
    def test_both_dialects_satisfy_all_four_protocols(self, dialect):
        unicode_dialect = SQLServerUnicodeDialect((16, 0, 0))
        for _label, _cls, protocol, method, _module in CASES:
            assert isinstance(dialect, protocol)
            assert isinstance(unicode_dialect, protocol)
            assert callable(getattr(dialect, method))
            assert callable(getattr(unicode_dialect, method))

    def test_answers_are_frozen_tri_state_values(self, dialect):
        for _label, cls, _protocol, method, _module in CASES:
            answer = getattr(dialect, method)(cls())
            assert isinstance(answer, cls)
            assert dataclasses.is_dataclass(answer)
            with pytest.raises(dataclasses.FrozenInstanceError):
                answer.operations = False
            assert answer.state in {"actions", "unaddressable", "absent"}


class TestColumnReorder:
    def test_no_native_column_position_clause(self, dialect):
        point = ColumnReorderSuggestion(
            table_name="events",
            old_order=("id", "created_at"),
            new_order=("created_at", "id"),
            reordered_columns=("id", "created_at"),
        )
        answer = dialect.suggest_column_reorder(point)
        assert answer.operations is False
        assert answer.state == "unaddressable"

    def test_false_is_documented_against_the_alter_table_grammar(self):
        evidence = _docstring("column_reorder_suggestion")
        assert "ALTER TABLE" in evidence
        assert "New columns" in evidence
        assert "are added after all existing columns" in evidence
        assert "no column-position clause" in evidence

    def test_refusal_does_not_depend_on_the_order_shapes(self, dialect):
        for old_order, new_order in (
            ((), ()),
            (("a",), ("b", "a")),
            (("a", "b", "c"), ("c", "b", "a")),
        ):
            point = ColumnReorderSuggestion(
                old_order=old_order,
                new_order=new_order,
                reordered_columns=new_order,
            )
            assert dialect.suggest_column_reorder(point).operations is False


class TestTableConstraintChange:
    def test_add_chain_exact_sql(self, dialect):
        constraint = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["created_at"]), name="uq_created"
        )
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(table_name="events", new_constraints=(constraint,))
        )
        assert answer.state == "actions"
        assert len(answer.operations) == 1
        statement = answer.operations[0]
        assert isinstance(statement, AlterTableStatement)
        assert len(statement.actions) == 1
        assert isinstance(statement.actions[0], AddTableConstraintAction)
        assert statement.to_sql() == (
            "ALTER TABLE [events] ADD CONSTRAINT [uq_created] UNIQUE ([created_at])",
            (),
        )

    def test_drop_chain_exact_sql(self, dialect):
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events", old_constraints=("uq_created",)
            )
        )
        assert answer.state == "actions"
        statement = answer.operations[0]
        assert isinstance(statement.actions[0], DropTableConstraintAction)
        assert statement.to_sql() == (
            "ALTER TABLE [events] DROP CONSTRAINT [uq_created]",
            (),
        )

    def test_changed_definition_drops_before_adding(self, dialect):
        constraint = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["created_at"]), name="uq_created"
        )
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events",
                old_constraints=("uq_created",),
                new_constraints=(constraint,),
            )
        )
        assert _sql(answer.operations) == (
            "ALTER TABLE [events] DROP CONSTRAINT [uq_created] "
            "ALTER TABLE [events] ADD CONSTRAINT [uq_created] UNIQUE ([created_at])"
        )
        assert isinstance(answer.operations[0].actions[0], DropTableConstraintAction)
        assert isinstance(answer.operations[1].actions[0], AddTableConstraintAction)

    def test_frozen_add_projection_is_unsupported_with_reason(self, dialect):
        # The core's freeze drops the branch *class*: UNIQUE and PRIMARY KEY
        # both reduce to {"columns": ...}, so an ADD cannot reuse a node.
        frozen = (
            "params",
            (("branch", ("params", (("columns", ("created_at",)),))),
             ("name", "uq_created")),
        )
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(table_name="events", new_constraints=(frozen,))
        )
        assert answer.operations is False
        reason = _docstring("table_constraint_change_suggestion")
        assert "branch" in reason and "class" in reason
        assert "ALTER TABLE" in reason

    def test_no_difference_is_absent_and_missing_name_is_unsupported(self, dialect):
        assert dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(old_constraints=("uq",), new_constraints=("uq",))
        ).operations is None
        assert dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(table_name="events", old_constraints=(("repr", "x"),))
        ).operations is False
        assert dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(old_constraints=("uq",))
        ).operations is False


class TestTableIndexChange:
    def test_create_chain_exact_sql(self, dialect):
        index = IndexDefinition(dialect, name="ix_created", columns=["created_at"])
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(table_name="events", new_indexes=(index,))
        )
        assert answer.state == "actions"
        statement = answer.operations[0]
        assert isinstance(statement, CreateIndexStatement)
        assert not isinstance(statement, AlterTableStatement)
        assert statement.to_sql() == (
            "CREATE INDEX [ix_created] ON [events] ([created_at])",
            (),
        )

    def test_create_unique_and_include_exact_sql(self, dialect):
        index = IndexDefinition(
            dialect,
            name="ix_created",
            columns=["created_at"],
            unique=True,
            type="NONCLUSTERED",
            include_columns=["tenant_id"],
        )
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(table_name="events", new_indexes=(index,))
        )
        assert answer.operations[0].to_sql() == (
            "CREATE UNIQUE NONCLUSTERED INDEX [ix_created] ON [events] ([created_at]) "
            "INCLUDE ([tenant_id])",
            (),
        )

    def test_drop_chain_exact_sql(self, dialect):
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(table_name="events", old_indexes=("ix_created",))
        )
        assert answer.state == "actions"
        assert isinstance(answer.operations[0], DropIndexStatement)
        assert answer.operations[0].to_sql() == (
            "DROP INDEX [ix_created] ON [events]",
            (),
        )

    def test_drop_before_create_and_no_alter_table_index_actions(self, dialect):
        index = IndexDefinition(dialect, name="ix_created", columns=["created_at"])
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events", old_indexes=("ix_created",), new_indexes=(index,)
            )
        )
        assert _sql(answer.operations) == (
            "DROP INDEX [ix_created] ON [events] "
            "CREATE INDEX [ix_created] ON [events] ([created_at])"
        )
        assert not any(
            isinstance(action, (AddIndexAction, DropIndexAction))
            for statement in answer.operations
            for action in getattr(statement, "actions", ())
        )
        reason = _docstring("table_index_change_suggestion")
        assert "memory-optimized tables" in reason
        assert "CREATE INDEX" in reason and "DROP INDEX" in reason

    def test_frozen_projection_rebuilds_a_plain_index(self, dialect):
        frozen = ("params", (("columns", ("created_at",)), ("name", "ix_created")))
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(table_name="events", new_indexes=(frozen,))
        )
        assert answer.operations[0].to_sql() == (
            "CREATE INDEX [ix_created] ON [events] ([created_at])",
            (),
        )

    def test_unexpressible_index_options_are_unsupported(self, dialect):
        partial = (
            "params",
            (("columns", ("created_at",)), ("name", "ix_created"),
             ("partial_condition", ("repr", "ComparisonPredicate"))),
        )
        assert dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(table_name="events", new_indexes=(partial,))
        ).operations is False
        hash_index = SQLServerIndexDefinition(
            dialect, name="ix_hash", columns=["created_at"], hash_index=True, bucket_count=1024
        )
        assert dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(table_name="events", new_indexes=(hash_index,))
        ).operations is False
        not_exists = ("params", (("columns", ("created_at",)), ("name", "ix_created"),
                                 ("if_not_exists", True)))
        assert dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(table_name="events", new_indexes=(not_exists,))
        ).operations is False

    def test_no_difference_is_absent(self, dialect):
        assert dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(old_indexes=("ix",), new_indexes=("ix",))
        ).operations is None


class TestPartitionSchemeChange:
    OLD = {"scheme": "ps_old", "function": "pf_old"}
    NEW = {
        "function": "pf_new",
        "data_type": "DATE",
        "boundaries": ("2026-01-01",),
        "scheme": "ps_new",
        "filegroups": ("fg1", "fg2"),
        "stage_table": "events_stage",
        "source_partition": 1,
        "target_partition": 1,
    }

    def test_real_change_is_unaddressable(self, dialect):
        # The old chain switched partition 1 out to [events_stage] and never
        # switched it back, emptying the live table. It is not a safe answer.
        point = PartitionSchemeChangeSuggestion(
            table_name="events", old_partition=self.OLD, new_partition=self.NEW
        )
        answer = dialect.suggest_partition_scheme_change(point)
        assert answer.operations is False
        assert answer.state == "unaddressable"

    def test_refusal_documents_switch_semantics_and_the_missing_switch_back(self):
        reason = _docstring("partition_scheme_change_suggestion")
        assert "SWITCH" in reason and "SWITCH-back" in reason
        assert "already exist" in reason and "empty" in reason
        assert "rebuild/migration" in reason and "suggestion contract" in reason

    def test_full_declarations_stay_unaddressable(self, dialect):
        variants = (
            self.NEW,
            {**self.NEW, "filegroups": (), "all_filegroup": "PRIMARY"},
            {**self.NEW, "source_partition": 2, "target_partition": 3},
        )
        for new in variants:
            answer = dialect.suggest_partition_scheme_change(
                PartitionSchemeChangeSuggestion(
                    table_name="events", old_partition=self.OLD, new_partition=new
                )
            )
            assert answer.operations is False

    def test_edition_gate_is_honest(self):
        standard = SQLServerDialect((16, 0, 0), edition="Standard Edition")
        assert standard.partition_capability() is PartitionCapability.UNSUPPORTED
        answer = standard.suggest_partition_scheme_change(
            PartitionSchemeChangeSuggestion(
                table_name="events", old_partition=self.OLD, new_partition=self.NEW
            )
        )
        assert answer.operations is False

    def test_version_floor_is_honest(self):
        old_server = SQLServerDialect((9, 0, 0))
        answer = old_server.suggest_partition_scheme_change(
            PartitionSchemeChangeSuggestion(
                table_name="events", old_partition=self.OLD, new_partition=self.NEW
            )
        )
        assert answer.operations is False

    def test_clause_level_projection_is_unsupported_with_reason(self, dialect):
        # A model's frozen partition clause names a scheme and a key column
        # only: no function type/boundaries and no SWITCH target.
        clause = (
            "params",
            (("partition_scheme", "ps_new"), ("range_direction", "RIGHT"),
             ("keys", ("created_at",))),
        )
        answer = dialect.suggest_partition_scheme_change(
            PartitionSchemeChangeSuggestion(table_name="events", new_partition=clause)
        )
        assert answer.operations is False
        reason = _docstring("partition_scheme_change_suggestion")
        assert "Enterprise" in reason and "2008" in reason
        assert "SWITCH" in reason and "rebuild/migration" in reason

    def test_incomplete_new_projection_is_unsupported(self, dialect):
        for missing in ("function", "data_type", "boundaries", "scheme", "stage_table"):
            new = {k: v for k, v in self.NEW.items() if k != missing}
            answer = dialect.suggest_partition_scheme_change(
                PartitionSchemeChangeSuggestion(
                    table_name="events", old_partition=self.OLD, new_partition=new
                )
            )
            assert answer.operations is False

    def test_no_change_is_absent(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            PartitionSchemeChangeSuggestion(
                table_name="events", old_partition=self.OLD, new_partition=dict(self.OLD)
            )
        )
        assert answer.operations is None


class TestEnrichedChangePointContext:
    """Live declarations on a frozen point recover only the honest answers."""

    def test_enriched_add_spells_every_tsql_constraint_kind(self, dialect):
        cases = (
            (
                TableUniqueConstraint(dialect, ["created_at"]),
                "UNIQUE ([created_at])",
            ),
            (
                TablePrimaryKeyConstraint(dialect, ["id"]),
                "PRIMARY KEY ([id])",
            ),
            (
                TableCheckConstraint(
                    dialect,
                    ComparisonPredicate(
                        dialect, ">", ExprColumn(dialect, "age"), Literal(dialect, 18, inline=True)
                    ),
                ),
                "CHECK ([age] > 18)",
            ),
            (
                TableForeignKeyConstraint(
                    dialect, ["tenant_id"], (TableObject(dialect, "tenants"), ["id"])
                ),
                "FOREIGN KEY ([tenant_id]) REFERENCES [tenants]([id])",
            ),
        )
        for branch, body in cases:
            declaration = TableConstraint(dialect, branch=branch, name="c1")
            answer = dialect.suggest_table_constraint_change(_constraint_point(new=(declaration,)))
            assert answer.state == "actions"
            assert len(answer.operations) == 1
            statement = answer.operations[0]
            assert len(statement.actions) == 1
            action = statement.actions[0]
            assert isinstance(action, AddTableConstraintAction)
            assert action.constraint is declaration
            assert statement.to_sql() == (
                f"ALTER TABLE [events] ADD CONSTRAINT [c1] {body}",
                (),
            )

    def test_enriched_changed_constraint_keeps_the_live_branch_and_drops_first(self, dialect):
        old = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["created_at"]), name="c1"
        )
        new = TableConstraint(
            dialect, branch=TablePrimaryKeyConstraint(dialect, ["created_at"]), name="c1"
        )
        answer = dialect.suggest_table_constraint_change(_constraint_point(old=(old,), new=(new,)))
        assert _sql(answer.operations) == (
            "ALTER TABLE [events] DROP CONSTRAINT [c1] "
            "ALTER TABLE [events] ADD CONSTRAINT [c1] PRIMARY KEY ([created_at])"
        )
        assert isinstance(answer.operations[0].actions[0], DropTableConstraintAction)
        add = answer.operations[1].actions[0]
        assert isinstance(add, AddTableConstraintAction)
        assert add.constraint is new
        assert isinstance(add.constraint.branch, TablePrimaryKeyConstraint)

    def test_enriched_unspellable_constraints_stay_false(self, dialect):
        unspellable = (
            TableConstraint(dialect, branch=TableExcludeConstraint(dialect, ["id"]), name="c1"),
            TableConstraint(
                dialect,
                branch=TableUniqueConstraint(dialect, ["id"]),
                name="c1",
                enforced=True,
            ),
            TableConstraint(
                dialect,
                branch=TableUniqueConstraint(dialect, ["id"]),
                name="c1",
                deferrable=True,
            ),
            TableConstraint(
                dialect,
                branch=TableCheckConstraint(
                    dialect,
                    ComparisonPredicate(
                        dialect, ">", ExprColumn(dialect, "age"), Literal(dialect, 18, inline=True)
                    ),
                ),
                name="c1",
                validation=ConstraintValidation.NOVALIDATE,
            ),
        )
        for declaration in unspellable:
            answer = dialect.suggest_table_constraint_change(
                _constraint_point(new=(declaration,))
            )
            assert answer.operations is False

    def test_enriched_declaration_with_a_different_name_is_not_reused(self, dialect):
        frozen = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["id"]), name="wanted"
        )
        other = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["id"]), name="other"
        )
        point = TableConstraintChangeSuggestion(
            table_name="events",
            new_constraints=(_freeze(frozen),),
            new_constraint_declarations=(other,),
        )
        assert dialect.suggest_table_constraint_change(point).operations is False

    def test_enriched_create_spells_clustered_unique_and_include(self, dialect):
        index = IndexDefinition(
            dialect,
            name="ix_created",
            columns=["created_at"],
            unique=True,
            type="CLUSTERED",
            include_columns=["tenant_id"],
        )
        answer = dialect.suggest_table_index_change(_index_point(new=(index,)))
        assert answer.state == "actions"
        statement = answer.operations[0]
        assert isinstance(statement, CreateIndexStatement)
        assert statement.to_sql() == (
            "CREATE UNIQUE CLUSTERED INDEX [ix_created] ON [events] ([created_at]) "
            "INCLUDE ([tenant_id])",
            (),
        )

    def test_enriched_create_spells_nonclustered_composite_index(self, dialect):
        index = IndexDefinition(
            dialect,
            name="ix_created",
            columns=["created_at", "tenant_id"],
            type="NONCLUSTERED",
        )
        answer = dialect.suggest_table_index_change(_index_point(new=(index,)))
        assert answer.operations[0].to_sql() == (
            "CREATE NONCLUSTERED INDEX [ix_created] ON [events] ([created_at], [tenant_id])",
            (),
        )

    def test_enriched_drop_and_create_chain_exact_sql(self, dialect):
        old = IndexDefinition(dialect, name="ix_old", columns=["created_at"])
        new = IndexDefinition(dialect, name="ix_new", columns=["tenant_id"], unique=True)
        answer = dialect.suggest_table_index_change(_index_point(old=(old,), new=(new,)))
        assert _sql(answer.operations) == (
            "DROP INDEX [ix_old] ON [events] "
            "CREATE UNIQUE INDEX [ix_new] ON [events] ([tenant_id])"
        )
        assert isinstance(answer.operations[0], DropIndexStatement)
        assert not any(
            isinstance(action, (AddIndexAction, DropIndexAction))
            for statement in answer.operations
            for action in getattr(statement, "actions", ())
        )

    def test_enriched_unsupported_index_options_stay_false(self, dialect):
        unsupported = (
            SQLServerIndexDefinition(
                dialect,
                name="ix_hash",
                columns=["created_at"],
                hash_index=True,
                bucket_count=1024,
            ),
            IndexDefinition(dialect, name="ix_ne", columns=["created_at"], if_not_exists=True),
            IndexDefinition(dialect, name="ix_conc", columns=["created_at"], concurrent=True),
            IndexDefinition(
                dialect,
                name="ix_partial",
                columns=["created_at"],
                partial_condition=("repr", "ComparisonPredicate"),
            ),
        )
        for declaration in unsupported:
            answer = dialect.suggest_table_index_change(_index_point(new=(declaration,)))
            assert answer.operations is False

    def test_enriched_full_column_definitions_do_not_change_reorder_refusal(self, dialect):
        fields = {
            "id": ColumnDefinition(dialect, "id", IntegerType(dialect)),
            "created_at": ColumnDefinition(dialect, "created_at", IntegerType(dialect)),
        }
        point = ColumnReorderSuggestion(
            table_name="events",
            old_order=("id", "created_at"),
            new_order=("created_at", "id"),
            reordered_columns=("id",),
            old_fields=fields,
            new_fields=fields,
        )
        for server in (dialect, SQLServerUnicodeDialect((16, 0, 0))):
            answer = server.suggest_column_reorder(point)
            assert answer.operations is False
            assert answer.state == "unaddressable"

    def test_enriched_partition_declarations_stay_unaddressable(self, dialect):
        old = PartitionClause(dialect, "RANGE", [ExprColumn(dialect, "created_at")])
        new = PartitionClause(dialect, "RANGE", [ExprColumn(dialect, "id")])
        point = PartitionSchemeChangeSuggestion(
            table_name="events",
            old_partition=_freeze(old),
            new_partition=_freeze(new),
            old_partition_declaration=old,
            new_partition_declaration=new,
        )
        for server in (
            dialect,
            SQLServerUnicodeDialect((16, 0, 0)),
            SQLServerDialect((16, 0, 0), edition="Standard Edition"),
            SQLServerDialect((9, 0, 0)),
        ):
            answer = server.suggest_partition_scheme_change(point)
            assert answer.operations is False
            assert answer.state == "unaddressable"
        # Enrichment does not turn an unchanged projection into an action.
        unchanged = PartitionSchemeChangeSuggestion(
            table_name="events",
            old_partition=_freeze(old),
            new_partition=_freeze(old),
            old_partition_declaration=old,
            new_partition_declaration=new,
        )
        assert dialect.suggest_partition_scheme_change(unchanged).operations is None


class TestSuggestionChainSafety:
    """Structural guard on every change-point answer, not just one pinned SQL."""

    LIVE = "events"

    def test_no_answer_leaves_live_table_data_outside(self, dialect):
        points = (
            ColumnReorderSuggestion(
                table_name=self.LIVE,
                old_order=("id", "created_at"),
                new_order=("created_at", "id"),
                reordered_columns=("id",),
            ),
            TableConstraintChangeSuggestion(
                table_name=self.LIVE,
                old_constraints=("uq_created",),
                new_constraints=("uq_created_2",),
            ),
            TableIndexChangeSuggestion(
                table_name=self.LIVE,
                old_indexes=("ix_created",),
                new_indexes=(IndexDefinition(dialect, name="ix_created", columns=["created_at"]),),
            ),
            PartitionSchemeChangeSuggestion(
                table_name=self.LIVE,
                old_partition=TestPartitionSchemeChange.OLD,
                new_partition=TestPartitionSchemeChange.NEW,
            ),
        )
        methods = {label: method for label, _cls, _protocol, method, _module in CASES}
        for server in (dialect, SQLServerUnicodeDialect((16, 0, 0))):
            for point in points:
                answer = getattr(server, methods[point.label])(point)
                _assert_data_preserved(answer.operations, live=self.LIVE)

    def test_enriched_points_keep_chains_safe(self, dialect):
        constraint = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["created_at"]), name="uq_created"
        )
        index = IndexDefinition(dialect, name="ix_created", columns=["created_at"])
        fields = {
            "id": ColumnDefinition(dialect, "id", IntegerType(dialect)),
            "created_at": ColumnDefinition(dialect, "created_at", IntegerType(dialect)),
        }
        old_partition = PartitionClause(dialect, "RANGE", [ExprColumn(dialect, "created_at")])
        new_partition = PartitionClause(dialect, "RANGE", [ExprColumn(dialect, "id")])
        points = (
            ColumnReorderSuggestion(
                table_name=self.LIVE,
                old_order=("id", "created_at"),
                new_order=("created_at", "id"),
                reordered_columns=("id",),
                old_fields=fields,
                new_fields=fields,
            ),
            _constraint_point(self.LIVE, new=(constraint,)),
            _index_point(self.LIVE, old=("ix_retired",), new=(index,)),
            PartitionSchemeChangeSuggestion(
                table_name=self.LIVE,
                old_partition=_freeze(old_partition),
                new_partition=_freeze(new_partition),
                old_partition_declaration=old_partition,
                new_partition_declaration=new_partition,
            ),
        )
        methods = {label: method for label, _cls, _protocol, method, _module in CASES}
        for server in (dialect, SQLServerUnicodeDialect((16, 0, 0))):
            for point in points:
                answer = getattr(server, methods[point.label])(point)
                _assert_data_preserved(answer.operations, live=self.LIVE)

    def test_guard_rejects_a_switch_without_a_switch_back(self, dialect):
        # Negative control: the exact shape the old scheme-change answer used.
        old_chain = (
            SQLServerPartitionFunctionExpression(dialect, "pf_new", "DATE", ["2026-01-01"]),
            SQLServerPartitionSchemeExpression(dialect, "ps_new", "pf_new", ["fg1", "fg2"]),
            SQLServerSwitchPartitionExpression(
                dialect, self.LIVE, "events_stage", source_partition=1, target_partition=1
            ),
            SQLServerDropPartitionSchemeExpression(dialect, "ps_old"),
            SQLServerDropPartitionFunctionExpression(dialect, "pf_old"),
        )
        with pytest.raises(AssertionError, match="data left outside"):
            _assert_data_preserved(old_chain, live=self.LIVE)

    def test_guard_accepts_a_balanced_switch_out_and_back(self, dialect):
        chain = (
            SQLServerSwitchPartitionExpression(
                dialect, self.LIVE, "events_stage", source_partition=1, target_partition=1
            ),
            SQLServerSwitchPartitionExpression(
                dialect, "events_stage", self.LIVE, source_partition=1, target_partition=1
            ),
        )
        _assert_data_preserved(chain, live=self.LIVE)

    def test_guard_rejects_destructive_statements(self):
        class _Raw:
            def __init__(self, sql):
                self.sql = sql

            def to_sql(self):
                return self.sql, ()

        for sql in ("DROP TABLE [events]", "DROP SCHEMA [dbo]"):
            with pytest.raises(AssertionError, match="destructive"):
                _assert_data_preserved((_Raw(sql),), live=self.LIVE)
