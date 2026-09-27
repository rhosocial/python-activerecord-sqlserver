# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_expression_roundtrip_all.py
"""
Functional serialization coverage for SQL Server expression classes.

Every expression class defined in ``rhosocial.activerecord.backend.impl
.sqlserver.expression`` must round-trip losslessly through dict / JSON / XML
encodings, and produce identical ``to_sql()`` where the SQL Server dialect
supports it.
"""

import pytest

from rhosocial.activerecord.testsuite.utils.expression import (
    collect_expression_classes,
    make_instance,
    register_all,
    register_special_constructor,
    roundtrip_expression,
    sql_consistent,
)

SS_EXPR_PKG = "rhosocial.activerecord.backend.impl.sqlserver.expression"

CLASSES = collect_expression_classes(SS_EXPR_PKG)
register_all(CLASSES)


def _register_sqlserver_specials():
    from rhosocial.activerecord.backend.expression.core import Column

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

    def partition(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionByRangeClause,
        )
        return SQLServerPartitionByRangeClause(
            d, keys=[Column(d, "id")], partition_scheme="ps"
        )

    def alias_type(d):
        from rhosocial.activerecord.backend.expression.types import IntegerType
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerAliasTypeDefinition,
        )
        return SQLServerAliasTypeDefinition(d, IntegerType(d), nullability=True)

    def table_type(d):
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnConstraintType,
            ColumnDefinition,
            TableConstraint,
            TableConstraintType,
        )
        from rhosocial.activerecord.backend.expression.types import IntegerType
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
                    constraints=[
                        ColumnConstraint(d, ColumnConstraintType.NOT_NULL),
                    ],
                )
            ],
            constraints=[
                TableConstraint(
                    d,
                    TableConstraintType.PRIMARY_KEY,
                    columns=["id"],
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
        return SQLServerDropTypeExpression(d, "type_name")

    def rename_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerRenameTypeExpression,
        )
        return SQLServerRenameTypeExpression(d, "old_name", "new_name")

    register_special_constructor("pivot.PivotExpression", pivot)
    register_special_constructor(
        "columnstore.SQLServerColumnstoreIndexExpression", columnstore
    )
    register_special_constructor(
        "partition.SQLServerPartitionByRangeClause", partition
    )
    register_special_constructor("type.SQLServerAliasTypeDefinition", alias_type)
    register_special_constructor("type.SQLServerTableTypeDefinition", table_type)
    register_special_constructor("type.SQLServerClrTypeDefinition", clr_type)
    register_special_constructor("type.SQLServerDropTypeExpression", drop_type)
    register_special_constructor("type.SQLServerRenameTypeExpression", rename_type)


_register_sqlserver_specials()


@pytest.fixture(params=[fqn for fqn in sorted(CLASSES)], ids=sorted(CLASSES))
def sqlserver_expr_case(request, sqlserver_dialect):
    fqn = request.param
    cls = CLASSES[fqn]
    instance, source = make_instance(cls, sqlserver_dialect)
    if instance is None:
        pytest.skip(f"{fqn}: {source}")
    return fqn, instance


class TestSQLServerExpressionRoundtrip:
    """All constructible SQL Server expression classes round-trip losslessly."""

    def test_get_params_roundtrip(self, sqlserver_expr_case, sqlserver_dialect):
        fqn, instance = sqlserver_expr_case
        roundtrip_expression(fqn, instance, sqlserver_dialect)

    def test_to_sql_consistent(self, sqlserver_expr_case, sqlserver_dialect):
        fqn, instance = sqlserver_expr_case
        sql_consistent(fqn, instance, sqlserver_dialect)


def test_core_expressions_also_roundtrip(sqlserver_dialect):
    from rhosocial.activerecord.backend.expression.core import Column, Literal
    from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate

    expr = ComparisonPredicate(
        sqlserver_dialect, "=", Column(sqlserver_dialect, "a"), Literal(sqlserver_dialect, 1)
    )
    roundtrip_expression("core", expr, sqlserver_dialect)
    sql_consistent("core", expr, sqlserver_dialect)