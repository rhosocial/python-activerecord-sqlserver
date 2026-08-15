# tests/providers/fixtures/_common.py
"""Shared helpers for the SQL Server DDL expression fixtures."""

from __future__ import annotations

from typing import Tuple

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
    TableExpression,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


def to_sqlserver_ddl_sql(expr: CreateTableExpression) -> Tuple[str, tuple]:
    """Generate canonical SQL Server DDL for a :class:`CreateTableExpression`.

    No post-processing is required (unlike MySQL where storage option quotes
    must be stripped). This pass-through wrapper exists so the call site is
    the same across backends.
    """
    return expr.to_sql()


def create_table_sql(expr: CreateTableExpression) -> Tuple[str, tuple]:
    """Public alias for :func:`to_sqlserver_ddl_sql`."""
    return to_sqlserver_ddl_sql(expr)


def drop_table(dialect, table_name: str) -> DropTableExpression:
    """Build a ``DROP TABLE IF EXISTS table_name`` expression."""
    return DropTableExpression(
        dialect=dialect,
        table=TableExpression(dialect, table_name),
        if_exists=True,
    )


def _drop_fk_constraints_for_table(backend, table_name: str) -> None:
    """Drop all foreign key constraints that reference the given table."""
    sql = f"""
    DECLARE @sql NVARCHAR(MAX) = N''
    SELECT @sql += 'ALTER TABLE [' + OBJECT_SCHEMA_NAME(fk.parent_object_id) + '].[' + OBJECT_NAME(fk.parent_object_id) + '] DROP CONSTRAINT [' + fk.name + ']; '
    FROM sys.foreign_keys fk
    WHERE OBJECT_NAME(fk.referenced_object_id) = '{table_name}'
      AND OBJECT_SCHEMA_NAME(fk.parent_object_id) = 'dbo'
    EXEC sp_executesql @sql
    """
    try:
        backend.execute(sql)
    except Exception:
        pass


async def _drop_fk_constraints_for_table_async(backend, table_name: str) -> None:
    """Async version: drop all FK constraints that reference the given table."""
    sql = f"""
    DECLARE @sql NVARCHAR(MAX) = N''
    SELECT @sql += 'ALTER TABLE [' + OBJECT_SCHEMA_NAME(fk.parent_object_id) + '].[' + OBJECT_NAME(fk.parent_object_id) + '] DROP CONSTRAINT [' + fk.name + ']; '
    FROM sys.foreign_keys fk
    WHERE OBJECT_NAME(fk.referenced_object_id) = '{table_name}'
      AND OBJECT_SCHEMA_NAME(fk.parent_object_id) = 'dbo'
    EXEC sp_executesql @sql
    """
    try:
        await backend.execute(sql)
    except Exception:
        pass


def _drop_all_fk_constraints(backend) -> None:
    """Drop all foreign key constraints in the current database."""
    sql = """
    DECLARE @sql NVARCHAR(MAX) = N''
    SELECT @sql += 'ALTER TABLE [' + OBJECT_SCHEMA_NAME(fk.parent_object_id) + '].[' + OBJECT_NAME(fk.parent_object_id) + '] DROP CONSTRAINT [' + fk.name + ']; '
    FROM sys.foreign_keys fk WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = 'dbo'
    EXEC sp_executesql @sql
    """
    try:
        backend.execute(sql)
    except Exception:
        pass


def drop_all_tables(backend) -> None:
    """Drop all user tables in the current database, handling FK dependencies."""
    _drop_all_fk_constraints(backend)
    sql = """
    DECLARE @sql NVARCHAR(MAX) = N'';
    SELECT @sql += 'DROP TABLE IF EXISTS [' + TABLE_SCHEMA + '].[' + TABLE_NAME + ']; '
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo';
    EXEC sp_executesql @sql;
    """
    try:
        backend.execute(sql)
    except Exception:
        pass


def safe_drop_table(backend, dialect, table_name: str) -> None:
    """Drop a single table, first removing FK constraints that reference it."""
    _drop_fk_constraints_for_table(backend, table_name)
    options = ExecutionOptions(stmt_type=StatementType.DDL)
    try:
        drop_expr = DropTableExpression(
            dialect=dialect,
            table=TableExpression(dialect, table_name),
            if_exists=True,
        )
        backend.execute(*drop_expr.to_sql(), options=options)
    except Exception:
        pass


async def safe_drop_table_async(backend, dialect, table_name: str) -> None:
    """Async version of safe_drop_table."""
    await _drop_fk_constraints_for_table_async(backend, table_name)
    options = ExecutionOptions(stmt_type=StatementType.DDL)
    try:
        drop_expr = DropTableExpression(
            dialect=dialect,
            table=TableExpression(dialect, table_name),
            if_exists=True,
        )
        await backend.execute(*drop_expr.to_sql(), options=options)
    except Exception:
        pass


def disable_fk_checks(backend) -> None:
    """No-op: SQL Server does not require FK check disabling for DROP TABLE IF EXISTS."""


async def disable_fk_checks_async(backend) -> None:
    """Async no-op."""


def enable_fk_checks(backend) -> None:
    """No-op."""


async def enable_fk_checks_async(backend) -> None:
    """Async no-op."""
