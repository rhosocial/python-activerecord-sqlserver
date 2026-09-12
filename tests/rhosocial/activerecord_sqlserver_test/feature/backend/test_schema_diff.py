import pytest
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from rhosocial.activerecord.backend.schema import (
    SchemaSnapshot, SchemaDiff, TableDiff, ColumnDiff,
    SchemaDiffer,
)
from rhosocial.activerecord.backend.introspection.types import (
    ColumnInfo, ColumnNullable, TableInfo, TableType,
    IndexInfo, ForeignKeyInfo,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.schema import SQLServerSchemaDiffer


class TestSQLServerSchemaDiffer:

    def _make_snapshot(self, dialect_class: str, columns: Dict[str, List[ColumnInfo]]) -> SchemaSnapshot:
        tables = {}
        for name, cols in columns.items():
            tables[name] = TableInfo(
                name=name,
                schema="dbo",
                table_type=TableType.BASE_TABLE,
                columns=cols,
                indexes=[],
                foreign_keys=[],
            )
        return SchemaSnapshot(
            dialect_class=dialect_class,
            captured_at=datetime.now(),
            database_info=None,
            tables=tables,
        )

    def _make_column(self, name: str, data_type: str, ordinal: int,
                     nullable: bool = False, is_pk: bool = False,
                     parsed_dt=None) -> ColumnInfo:
        return ColumnInfo(
            name=name,
            table_name="test",
            schema="dbo",
            ordinal_position=ordinal,
            data_type=data_type,
            data_type_full=data_type,
            parsed_data_type=parsed_dt,
            nullable=ColumnNullable.NULLABLE if nullable else ColumnNullable.NOT_NULL,
            is_primary_key=is_pk,
        )

    def test_no_changes(self):
        col = self._make_column("id", "INT", 1, parsed_dt=IntegerType())
        snap = self._make_snapshot("SQLServerDialect", {"users": [col]})
        differ = SQLServerSchemaDiffer()
        diff = differ.compare(snap, snap)
        assert diff.is_empty

    def test_added_column(self):
        old_col = self._make_column("id", "INT", 1, is_pk=True)
        new_col1 = self._make_column("id", "INT", 1, is_pk=True)
        new_col2 = self._make_column("name", "NVARCHAR(100)", 2)

        old_snap = self._make_snapshot("SQLServerDialect", {"users": [old_col]})
        new_snap = self._make_snapshot("SQLServerDialect", {"users": [new_col1, new_col2]})

        differ = SQLServerSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)

        assert "users" in diff.modified_tables
        td = diff.table_diffs["users"]
        added = [cd for cd in td.column_diffs if cd.is_added]
        assert len(added) == 1
        assert added[0].column_name == "name"

    def test_removed_column(self):
        old_col1 = self._make_column("id", "INT", 1, is_pk=True)
        old_col2 = self._make_column("name", "NVARCHAR(100)", 2)
        new_col = self._make_column("id", "INT", 1, is_pk=True)

        old_snap = self._make_snapshot("SQLServerDialect", {"users": [old_col1, old_col2]})
        new_snap = self._make_snapshot("SQLServerDialect", {"users": [new_col]})

        differ = SQLServerSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)
        td = diff.table_diffs["users"]
        removed = [cd for cd in td.column_diffs if cd.is_removed]
        assert len(removed) == 1
        assert removed[0].column_name == "name"

    def test_modified_column_type(self):
        old_col = self._make_column("name", "NVARCHAR(100)", 1,
                                    parsed_dt=VarCharType(length=100))
        new_col = self._make_column("name", "NVARCHAR(200)", 1,
                                    parsed_dt=VarCharType(length=200))

        old_snap = self._make_snapshot("SQLServerDialect", {"users": [old_col]})
        new_snap = self._make_snapshot("SQLServerDialect", {"users": [new_col]})

        differ = SQLServerSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)
        td = diff.table_diffs["users"]
        modified = [cd for cd in td.column_diffs if cd.is_modified]
        assert len(modified) == 1
        assert modified[0].column_name == "name"

    def test_ordinal_position_matters(self):
        """SQL ServerSchemaDiffer checks ordinal_position."""
        col_a_old = self._make_column("a", "INT", 1)
        col_b_old = self._make_column("b", "INT", 2)

        col_a_new = self._make_column("a", "INT", 2)
        col_b_new = self._make_column("b", "INT", 1)

        old_snap = self._make_snapshot("SQLServerDialect", {"test": [col_a_old, col_b_old]})
        new_snap = self._make_snapshot("SQLServerDialect", {"test": [col_a_new, col_b_new]})

        differ = SQLServerSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)
        td = diff.table_diffs["test"]
        assert td.is_modified

    def test_added_table(self):
        differ = SQLServerSchemaDiffer()
        old_snap = self._make_snapshot("SQLServerDialect", {})
        col = self._make_column("id", "INT", 1)
        new_snap = self._make_snapshot("SQLServerDialect", {"new_table": [col]})

        diff = differ.compare(old_snap, new_snap)
        assert "new_table" in diff.added_tables

    def test_removed_table(self):
        differ = SQLServerSchemaDiffer()
        col = self._make_column("id", "INT", 1)
        old_snap = self._make_snapshot("SQLServerDialect", {"old_table": [col]})
        new_snap = self._make_snapshot("SQLServerDialect", {})

        diff = differ.compare(old_snap, new_snap)
        assert "old_table" in diff.removed_tables
