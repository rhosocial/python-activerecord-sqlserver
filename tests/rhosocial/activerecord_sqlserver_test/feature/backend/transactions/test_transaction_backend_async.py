# tests/rhosocial/activerecord_sqlserver_test/feature/backend/transactions/test_transaction_backend_async.py
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def setup_test_table(async_sqlserver_backend):
    await async_sqlserver_backend.execute("DROP TABLE IF EXISTS test_table")
    await async_sqlserver_backend.execute("""
        CREATE TABLE test_table (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name VARCHAR(255),
            age INT
        )
    """)
    yield
    await async_sqlserver_backend.execute("DROP TABLE IF EXISTS test_table")


@pytest.mark.asyncio
async def test_transaction_commit(async_sqlserver_backend, setup_test_table):
    """Test transaction commit"""
    async with async_sqlserver_backend.transaction():
        sql = "INSERT INTO test_table (name, age) VALUES (?, ?)"
        params = ("test", 20)
        await async_sqlserver_backend.execute(sql, params)
    row = await async_sqlserver_backend.fetch_one("SELECT * FROM test_table WHERE name = ?", ("test",))
    assert row is not None


@pytest.mark.asyncio
async def test_transaction_rollback(async_sqlserver_backend, setup_test_table):
    """Test transaction rollback"""
    try:
        async with async_sqlserver_backend.transaction():
            sql = "INSERT INTO test_table (name, age) VALUES (?, ?)"
            params = ("test", 20)
            await async_sqlserver_backend.execute(sql, params)
            raise Exception("Force rollback")
    except Exception:
        pass
    row = await async_sqlserver_backend.fetch_one("SELECT * FROM test_table WHERE name = ?", ("test",))
    assert row is None


@pytest.mark.asyncio
async def test_nested_transaction(async_sqlserver_backend, setup_test_table):
    """Test nested transactions"""
    async with async_sqlserver_backend.transaction():
        sql_outer = "INSERT INTO test_table (name, age) VALUES (?, ?)"
        params_outer = ("outer", 20)
        await async_sqlserver_backend.execute(sql_outer, params_outer)
        async with async_sqlserver_backend.transaction():
            sql_inner = "INSERT INTO test_table (name, age) VALUES (?, ?)"
            params_inner = ("inner", 30)
            await async_sqlserver_backend.execute(sql_inner, params_inner)
    rows = await async_sqlserver_backend.fetch_all("SELECT * FROM test_table ORDER BY age")
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_transaction_get_cursor(async_sqlserver_backend):
    """Test that _get_cursor can be called within a transaction context."""
    async with async_sqlserver_backend.transaction():
        cursor = await async_sqlserver_backend._get_cursor()
        assert cursor is not None
        await cursor.close()
