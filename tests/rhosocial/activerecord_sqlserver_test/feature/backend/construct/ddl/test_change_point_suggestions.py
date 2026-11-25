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

import pytest

from rhosocial.activerecord.backend.dialect.partition_capability import PartitionCapability
from rhosocial.activerecord.backend.expression.statements import (
    CreateIndexStatement,
    DropIndexStatement,
    IndexDefinition,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddIndexAction,
    AddTableConstraintAction,
    AlterTableStatement,
    DropIndexAction,
    DropTableConstraintAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    TableConstraint,
    TableUniqueConstraint,
)
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

    def test_native_chain_exact_sql(self, dialect):
        point = PartitionSchemeChangeSuggestion(
            table_name="events", old_partition=self.OLD, new_partition=self.NEW
        )
        answer = dialect.suggest_partition_scheme_change(point)
        assert answer.state == "actions"
        assert dialect.partition_capability() is PartitionCapability.NATIVE
        assert [type(node) for node in answer.operations] == [
            SQLServerPartitionFunctionExpression,
            SQLServerPartitionSchemeExpression,
            SQLServerSwitchPartitionExpression,
            SQLServerDropPartitionSchemeExpression,
            SQLServerDropPartitionFunctionExpression,
        ]
        assert _sql(answer.operations) == (
            "CREATE PARTITION FUNCTION [pf_new] (DATE) AS RANGE RIGHT FOR VALUES ('2026-01-01') "
            "CREATE PARTITION SCHEME [ps_new] AS PARTITION [pf_new] TO ([fg1], [fg2]) "
            "ALTER TABLE [events] SWITCH PARTITION 1 TO [events_stage] PARTITION 1 "
            "DROP PARTITION SCHEME [ps_old] "
            "DROP PARTITION FUNCTION [pf_old]"
        )

    def test_all_filegroup_variant(self, dialect):
        new = {**self.NEW, "filegroups": (), "all_filegroup": "PRIMARY"}
        answer = dialect.suggest_partition_scheme_change(
            PartitionSchemeChangeSuggestion(
                table_name="events", old_partition=self.OLD, new_partition=new
            )
        )
        assert "CREATE PARTITION SCHEME [ps_new] AS PARTITION [pf_new] ALL TO ([PRIMARY])" in _sql(
            answer.operations
        )

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
        assert "type/boundaries" in reason and "SWITCH" in reason

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
