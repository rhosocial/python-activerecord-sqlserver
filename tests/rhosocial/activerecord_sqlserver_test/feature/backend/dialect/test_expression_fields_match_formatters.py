# tests/rhosocial/activerecord_sqlserver_test/feature/backend/dialect/test_expression_fields_match_formatters.py
"""A formatter may not read a field its statement does not carry.

A statement formatter that reads ``expr.schema_name`` needs the expression to
have that attribute. When the formatter was changed to qualify names and the
expression was not given the field, the result is not wrong SQL -- it is an
``AttributeError`` on a statement that can never be built, which is how
SQLServerColumnstoreIndexExpression reached CI.

These are source scans rather than runtime tests because the failure needs the
right dialect, the right statement options and a live server to reach; a scan
fails the build the moment the shape reappears, wherever it appears.
"""
import inspect

import pytest


class TestQualifiedStatementsRender:
    """A statement whose formatter qualifies names must build with a schema.

    Checked by building each statement rather than by scanning source. A scan
    was tried and does not work here: whether the field exists depends on
    inheritance reaching core, which lives in another repository, and on
    **core_kwargs forwarding. Reading the source of this repository cannot see
    either, so the scan reported defects that were not there -- two were chased
    down and both were false alarms -- while a field genuinely removed still
    passed. Constructing the statement and rendering it answers the question the
    defect actually asks: does this statement build, and does the schema reach
    the SQL?

    Each case names the statement and how to build it, so adding coverage for a
    newly qualified object type is one entry rather than a new mechanism.
    """

    @pytest.fixture
    def dialect(self):
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import (
            SQLServerDialect,
        )

        return SQLServerDialect(version=(2019, 0, 0))

    def test_columnstore_index(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.columnstore import (
            SQLServerColumnstoreIndexExpression,
        )

        expr = SQLServerColumnstoreIndexExpression(
            dialect, index_name="idx", table_name="orders", columns=["id"]
        )
        assert "idx" in expr.to_sql()[0]
        with_schema = SQLServerColumnstoreIndexExpression(
            dialect,
            index_name="idx",
            table_name="orders",
            columns=["id"],
            schema_name="dbo",
        )
        assert "dbo" in with_schema.to_sql()[0], with_schema.to_sql()[0]

    def test_spatial_index(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.spatial import (
            SQLServerCreateSpatialIndexExpression,
        )

        expr = SQLServerCreateSpatialIndexExpression(
            dialect, index_name="idx", table_name="places", column="geom"
        )
        assert "idx" in expr.to_sql()[0]
        with_schema = SQLServerCreateSpatialIndexExpression(
            dialect,
            index_name="idx",
            table_name="places",
            column="geom",
            schema_name="dbo",
        )
        assert "dbo" in with_schema.to_sql()[0], with_schema.to_sql()[0]

    def test_drop_type_inherits_the_field_from_core(self, dialect):
        """The case a source scan got wrong in both directions.

        SQLServerDropTypeExpression forwards schema_name to core's
        DropTypeExpression, which assigns it. A scan of this repository sees
        only the forwarding and no assignment, so it either misses a field that
        is there or reports one that is not, depending on how it resolves the
        base. Building it settles the question.
        """
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerDropTypeExpression,
        )

        plain = SQLServerDropTypeExpression(dialect, "my_type")
        assert "my_type" in plain.to_sql()[0]
        qualified = SQLServerDropTypeExpression(dialect, "my_type", schema_name="dbo")
        assert "dbo" in qualified.to_sql()[0], qualified.to_sql()[0]

    def test_partition_function_and_scheme_qualify_together(self, dialect):
        """A partition scheme cannot be qualified on its own.

        SQL Server requires a scheme and the function it references to sit in the
        same schema, so CREATE PARTITION SCHEME has to qualify both names or
        neither. The function expression had no schema field at all and its
        formatter compensated by splitting on a dot in the name, which put the
        qualification in the string instead of on the statement -- the one place
        the rest of the file cannot see it.
        """
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionFunctionExpression,
            SQLServerPartitionSchemeExpression,
        )

        def build(schema_name=None):
            function = SQLServerPartitionFunctionExpression(
                dialect, "pf_orders", "DATE", ["2024-01-01"], schema_name=schema_name
            )
            scheme = SQLServerPartitionSchemeExpression(
                dialect, "ps_orders", "pf_orders", ["fg1"], schema_name=schema_name
            )
            return function.to_sql()[0], scheme.to_sql()[0]

        assert build() == (
            "CREATE PARTITION FUNCTION [pf_orders] (DATE) "
            "AS RANGE RIGHT FOR VALUES ('2024-01-01')",
            "CREATE PARTITION SCHEME [ps_orders] AS PARTITION [pf_orders] TO ([fg1])",
        )
        assert build("sales") == (
            "CREATE PARTITION FUNCTION [sales].[pf_orders] (DATE) "
            "AS RANGE RIGHT FOR VALUES ('2024-01-01')",
            "CREATE PARTITION SCHEME [sales].[ps_orders] "
            "AS PARTITION [sales].[pf_orders] TO ([fg1])",
        )


class TestExpressionSignatures:
    """The expressions this backend's formatters qualify must take the field."""

    @pytest.mark.parametrize(
        "import_path,class_name",
        [
            (
                "rhosocial.activerecord.backend.impl.sqlserver.expression.columnstore",
                "SQLServerColumnstoreIndexExpression",
            ),
        ],
    )
    def test_qualified_expression_accepts_schema_name(self, import_path, class_name):
        import importlib

        module = importlib.import_module(import_path)
        cls = getattr(module, class_name)
        params = inspect.signature(cls.__init__).parameters
        assert "schema_name" in params, (
            f"{class_name} is qualified by its formatter, so it needs the "
            f"field; got {list(params)}"
        )
        assert params["schema_name"].default is None, (
            f"{class_name} must default schema_name to None -- None is what "
            f"means unqualified"
        )