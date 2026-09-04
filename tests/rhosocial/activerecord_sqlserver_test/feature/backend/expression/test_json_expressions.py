# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_json_expressions.py
"""
Tests for SQL Server JSON expression formatting.

SQL Server supports JSON since version 2016 through functions like:
- JSON_VALUE
- JSON_QUERY
- ISJSON
- JSON_MODIFY (not supported)
- OPENJSON for JSON table functionality

Note: SQL Server doesn't have native JSON type - JSON is stored in NVARCHAR(MAX).
"""
import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSQLServerJSONSupport:
    """Test SQL Server JSON dialect support."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(version=(16, 0, 0))

    @pytest.fixture
    def dialect_2016(self):
        return SQLServerDialect(version=(13, 0, 0))

    def test_supports_json_type(self, dialect):
        """Test JSON type support detection."""
        assert dialect.supports_json_type() is True

    def test_supports_json_2016(self, dialect_2016):
        """Test JSON support since SQL Server 2016."""
        assert dialect_2016.supports_json_type() is True

    def test_get_json_access_operator(self, dialect):
        """Test JSON path access operator."""
        op = dialect.get_json_access_operator()
        assert op is None or op == "JSON_VALUE/JSON_QUERY"

    def test_supports_json_table(self, dialect):
        """Test JSON table (OPENJSON) support."""
        assert dialect.supports_json_table() is True


class TestSQLServerJSONAdapter:
    """Test SQL Server JSON type adapter."""

    def test_json_to_db(self):
        """Test JSON adapter serialization."""
        from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerJSONAdapter

        adapter = SQLServerJSONAdapter()

        result = adapter.to_database({"name": "John", "age": 30})
        assert result == '{"name": "John", "age": 30}'

        result = adapter.to_database([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_json_from_db(self):
        """Test JSON adapter deserialization."""
        from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerJSONAdapter

        adapter = SQLServerJSONAdapter()

        result = adapter.from_database('{"name": "John", "age": 30}')
        assert result == {"name": "John", "age": 30}

        result = adapter.from_database("[1, 2, 3]")
        assert result == [1, 2, 3]


class TestSQLServerJSONQueries:
    """Test SQL Server JSON queries with real database."""

    @pytest.fixture
    def test_table(self, sqlserver_backend_single):
        """Create a test table with JSON column."""
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_json_table")
        sqlserver_backend_single.execute("""
            CREATE TABLE test_json_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
        """)
        yield "test_json_table"
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_json_table")

    def test_insert_json_string(self, sqlserver_backend_single, test_table):
        """Test inserting JSON as string."""
        json_data = '{"name": "John", "age": 30}'

        sqlserver_backend_single.execute(
            "INSERT INTO test_json_table (data) VALUES (?)",
            (json_data,)
        )

        row = sqlserver_backend_single.fetch_one(
            "SELECT data FROM test_json_table WHERE id = 1"
        )
        assert row["data"] == json_data

    def test_json_value_extraction(self, sqlserver_backend_single, test_table):
        """Test JSON_VALUE extraction."""
        json_data = '{"name": "John", "age": 30}'

        sqlserver_backend_single.execute(
            "INSERT INTO test_json_table (data) VALUES (?)",
            (json_data,)
        )

        row = sqlserver_backend_single.fetch_one(
            "SELECT JSON_VALUE(data, '$.name') AS name FROM test_json_table"
        )
        assert row["name"] == "John"

    def test_isjson_function(self, sqlserver_backend_single, test_table):
        """Test ISJSON function."""
        sqlserver_backend_single.execute(
            "INSERT INTO test_json_table (data) VALUES (?)",
            ('{"valid": "json"}',)
        )
        sqlserver_backend_single.execute(
            "INSERT INTO test_json_table (data) VALUES (?)",
            ("not json",)
        )

        rows = sqlserver_backend_single.fetch_all(
            "SELECT ISJSON(data) AS is_json FROM test_json_table ORDER BY id"
        )
        assert rows[0]["is_json"] == 1
        assert rows[1]["is_json"] == 0