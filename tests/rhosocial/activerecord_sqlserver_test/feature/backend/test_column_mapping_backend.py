# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_column_mapping_backend.py
import pytest
from datetime import datetime
import uuid

# Note: The actual adapters are imported from the core library, as the mysql backend
# may rely on the standard ones if it doesn't provide its own overrides.
from rhosocial.activerecord.backend.type_adapter import UUIDAdapter, BooleanAdapter


@pytest.fixture
def setup_mapped_users_table(sqlserver_backend):
    """Fixture to create and drop a 'mapped_users' table for MySQL."""
    sqlserver_backend.execute("DROP TABLE IF EXISTS mapped_users")
    sqlserver_backend.execute("""
        CREATE TABLE mapped_users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            created_at DATETIME NOT NULL,
            user_uuid VARCHAR(36),
            is_active TINYINT(1)
        )
    """)
    yield
    sqlserver_backend.execute("DROP TABLE IF EXISTS mapped_users")


def test_insert_with_mapping(sqlserver_backend, setup_mapped_users_table):
    """
    Tests that execute() with an INSERT correctly handles mapped data.
    Note: MySQL < 8.0.1 does not support RETURNING, so we verify with a subsequent SELECT.
    """
    backend = sqlserver_backend
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # Data for insertion must use database column names and compatible types
    sql = "INSERT INTO mapped_users (name, email, created_at, user_uuid, is_active) VALUES (%s, %s, %s, %s, %s)"
    params = ("John Doe", "john.doe@example.com", now_str, str(uuid.uuid4()), 1)

    result = backend.execute(sql=sql, params=params)

    assert result.affected_rows == 1
    assert result.last_insert_id is not None and result.last_insert_id > 0


def test_update_with_backend(sqlserver_backend, setup_mapped_users_table):
    """
    Tests that an update operation via execute() works correctly.
    """
    backend = sqlserver_backend
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    backend.execute("INSERT INTO mapped_users (name, email, created_at, user_uuid, is_active) VALUES (%s, %s, %s, %s, %s)",
                    ("Jane Doe", "jane.doe@example.com", now_str, str(uuid.uuid4()), 1))

    sql = "UPDATE mapped_users SET name = %s WHERE user_id = %s"
    params = ("Jane Smith", 1)
    result = backend.execute(sql, params)

    assert result.affected_rows == 1

    fetch_result = backend.execute("SELECT name FROM mapped_users WHERE user_id = 1")
    fetched_row = fetch_result.data[0] if fetch_result.data else None
    assert fetched_row is not None
    assert fetched_row["name"] == "Jane Smith"


def test_fetch_with_combined_mapping_and_adapters(sqlserver_backend, setup_mapped_users_table):
    """
    Tests that execute() correctly applies both column_mapping and column_adapters for MySQL.
    """
    backend = sqlserver_backend
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    test_uuid = uuid.uuid4()

    # Define mappings and adapters
    column_to_field_mapping = {
        "user_id": "pk",
        "name": "full_name",
        "user_uuid": "uuid",
        "is_active": "active"
    }
    
    # Adapters can be instantiated directly for testing purposes
    column_adapters = {
        "user_uuid": (UUIDAdapter(), uuid.UUID),
        "is_active": (BooleanAdapter(), bool)
    }

    # Insert data in DB-compatible format
    backend.execute(
        "INSERT INTO mapped_users (name, email, created_at, user_uuid, is_active) VALUES (%s, %s, %s, %s, %s)",
        ("Combined Test", "combined@example.com", now_str, str(test_uuid), 1)
    )

    # Execute SELECT with both mapping and adapters
    result = backend.execute(
        "SELECT * FROM mapped_users WHERE user_id = 1",
        column_mapping=column_to_field_mapping,
        column_adapters=column_adapters
    )

    fetched_row = result.data[0] if result.data else None
    assert fetched_row is not None

    # 1. Assert keys are the MAPPED FIELD NAMES
    assert "full_name" in fetched_row
    assert "uuid" in fetched_row
    assert "active" in fetched_row
    assert "name" not in fetched_row
    assert "user_uuid" not in fetched_row

    # 2. Assert values are the ADAPTED PYTHON TYPES
    assert fetched_row["full_name"] == "Combined Test"
    assert isinstance(fetched_row["uuid"], uuid.UUID)
    assert fetched_row["uuid"] == test_uuid
    assert isinstance(fetched_row["active"], bool)
    assert fetched_row["active"] is True
