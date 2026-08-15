# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_async_column_mapping_backend.py
import pytest
import pytest_asyncio
from datetime import datetime
import uuid

from rhosocial.activerecord.backend.type_adapter import UUIDAdapter, BooleanAdapter


@pytest_asyncio.fixture
async def setup_mapped_users_table(async_sqlserver_backend):
    """Async fixture to create and drop a 'mapped_users' table for MySQL."""
    await async_sqlserver_backend.execute("DROP TABLE IF EXISTS mapped_users")
    await async_sqlserver_backend.execute("""
        CREATE TABLE mapped_users (
            user_id INT IDENTITY(1,1) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            created_at DATETIME NOT NULL,
            user_uuid VARCHAR(36),
            is_active TINYINT
        )
    """)
    yield
    await async_sqlserver_backend.execute("DROP TABLE IF EXISTS mapped_users")


@pytest.mark.asyncio
async def test_async_insert_with_mapping(async_sqlserver_backend, setup_mapped_users_table):
    """
    Tests that async execute() with an INSERT correctly handles mapped data.
    """
    backend = async_sqlserver_backend
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    sql = "INSERT INTO mapped_users (name, email, created_at, user_uuid, is_active) VALUES (?, ?, ?, ?, ?)"
    params = ("John Doe Async", "john.doe.async@example.com", now_str, str(uuid.uuid4()), 1)

    result = await backend.execute(sql=sql, params=params)

    assert result.affected_rows == 1
    assert result.last_insert_id is not None and result.last_insert_id > 0


@pytest.mark.asyncio
async def test_async_update_with_backend(async_sqlserver_backend, setup_mapped_users_table):
    """
    Tests that an async update operation via execute() works correctly.
    """
    backend = async_sqlserver_backend
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    await backend.execute("INSERT INTO mapped_users (name, email, created_at, user_uuid, is_active) VALUES (?, ?, ?, ?, ?)",
                          ("Jane Doe Async", "jane.doe.async@example.com", now_str, str(uuid.uuid4()), 1))

    sql = "UPDATE mapped_users SET name = ? WHERE user_id = ?"
    params = ("Jane Smith Async", 1)
    result = await backend.execute(sql, params)

    assert result.affected_rows == 1

    fetch_result = await backend.execute("SELECT name FROM mapped_users WHERE user_id = 1")
    fetched_row = fetch_result.data[0] if fetch_result.data else None
    assert fetched_row is not None
    assert fetched_row["name"] == "Jane Smith Async"


@pytest.mark.asyncio
async def test_async_fetch_with_combined_mapping_and_adapters(async_sqlserver_backend, setup_mapped_users_table):
    """
    Tests that async execute() correctly applies both column_mapping and column_adapters for MySQL.
    """
    backend = async_sqlserver_backend
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    test_uuid = uuid.uuid4()

    column_to_field_mapping = {
        "user_id": "pk",
        "name": "full_name",
        "user_uuid": "uuid",
        "is_active": "active"
    }
    
    column_adapters = {
        "user_uuid": (UUIDAdapter(), uuid.UUID),
        "is_active": (BooleanAdapter(), bool)
    }

    await backend.execute(
        "INSERT INTO mapped_users (name, email, created_at, user_uuid, is_active) VALUES (?, ?, ?, ?, ?)",
        ("Async Combined", "asynccombined@example.com", now_str, str(test_uuid), 1)
    )

    result = await backend.execute(
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
    assert fetched_row["full_name"] == "Async Combined"
    assert isinstance(fetched_row["uuid"], uuid.UUID)
    assert fetched_row["uuid"] == test_uuid
    assert isinstance(fetched_row["active"], bool)
    assert fetched_row["active"] is True
