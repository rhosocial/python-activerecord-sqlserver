"""Transaction management examples for SQL Server.

This example demonstrates:
1. Basic transaction control (BEGIN, COMMIT, ROLLBACK)
2. Savepoint usage
3. Isolation levels
4. SNAPSHOT isolation (SQL Server specific)

Connection configuration is loaded from environment variables with defaults.
"""

import os

from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)
from rhosocial.activerecord.backend.transaction import IsolationLevel


def get_backend():
    """Get a configured backend instance from environment variables."""
    config = SQLServerConnectionConfig(
        host=os.environ.get('SQLSERVER_HOST', 'localhost'),
        port=int(os.environ.get('SQLSERVER_PORT', '1433')),
        database=os.environ.get('SQLSERVER_DATABASE', 'test_db'),
        username=os.environ.get('SQLSERVER_USERNAME', 'sa'),
        password=os.environ.get('SQLSERVER_PASSWORD', 'Password123!'),
        driver=os.environ.get('SQLSERVER_DRIVER', 'ODBC Driver 17 for SQL Server'),
        encrypt=os.environ.get('SQLSERVER_ENCRYPT', 'false').lower() == 'true',
        trust_server_certificate=os.environ.get('SQLSERVER_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true',
        autocommit=False,
    )
    
    backend = SQLServerBackend(connection_config=config)
    backend.connect()
    return backend


def setup_test_table(backend):
    """Create test table for examples."""
    backend.execute("""
        IF OBJECT_ID('test_users', 'U') IS NOT NULL
            DROP TABLE test_users
    """)
    
    backend.execute("""
        CREATE TABLE test_users (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(100) NOT NULL,
            email NVARCHAR(200)
        )
    """)
    
    backend.execute(
        "INSERT INTO test_users (name, email) VALUES (?, ?)",
        ("John Doe", "john@example.com")
    )


def example_basic_transaction():
    """Example: Basic transaction with COMMIT."""
    print("\n--- Basic Transaction ---")
    backend = get_backend()
    
    try:
        backend.transaction_manager.begin()
        
        backend.execute(
            "INSERT INTO test_users (name, email) VALUES (?, ?)",
            ("Jane Doe", "jane@example.com")
        )
        
        backend.transaction_manager.commit()
        print("Transaction committed successfully")
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Transaction rolled back: {e}")
    
    finally:
        backend.disconnect()


def example_rollback():
    """Example: Transaction with ROLLBACK."""
    print("\n--- Rollback ---")
    backend = get_backend()
    
    try:
        backend.transaction_manager.begin()
        
        backend.execute(
            "INSERT INTO test_users (name, email) VALUES (?, ?)",
            ("Rollback Test", "rollback@example.com")
        )
        
        # Simulate an error to trigger rollback
        print("Simulating error...")
        raise Exception("Simulated error")
        
        backend.transaction_manager.commit()
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Rolled back due to: {e}")
    
    finally:
        backend.disconnect()


def example_savepoint():
    """Example: Savepoint usage within transaction.
    
    SQL Server supports SAVE TRANSACTION for savepoints.
    """
    print("\n--- Savepoint ---")
    backend = get_backend()
    
    try:
        backend.transaction_manager.begin()
        
        backend.execute(
            "INSERT INTO test_users (name, email) VALUES (?, ?)",
            ("User 1", "user1@example.com")
        )
        
        backend.transaction_manager.savepoint("sp1")
        print("Savepoint sp1 created")
        
        backend.execute(
            "INSERT INTO test_users (name, email) VALUES (?, ?)",
            ("User 2", "user2@example.com")
        )
        
        backend.transaction_manager.savepoint("sp2")
        print("Savepoint sp2 created")
        
        backend.execute(
            "INSERT INTO test_users (name, email) VALUES (?, ?)",
            ("User 3", "user3@example.com")
        )
        
        # Rollback to savepoint sp2
        backend.transaction_manager.rollback("sp2")
        print("Rolled back to sp2 (User 3 undone)")
        
        backend.transaction_manager.commit()
        print("Transaction committed (User 1 and User 2 saved)")
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Error: {e}")
    
    finally:
        backend.disconnect()


def example_isolation_level():
    """Example: Transaction with isolation level."""
    print("\n--- Isolation Level ---")
    backend = get_backend()
    
    try:
        backend.transaction_manager.begin(isolation_level=IsolationLevel.SERIALIZABLE)
        
        result = backend.execute("SELECT COUNT(*) AS count FROM test_users")
        print(f"Read {result.data[0]['count']} users in SERIALIZABLE isolation")
        
        backend.transaction_manager.commit()
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Error: {e}")
    
    finally:
        backend.disconnect()


def example_snapshot_isolation():
    """Example: SNAPSHOT isolation level.
    
    SQL Server's SNAPSHOT isolation provides MVCC-like behavior,
    similar to PostgreSQL's MVCC.
    """
    print("\n--- SNAPSHOT Isolation ---")
    backend = get_backend()
    
    try:
        backend.transaction_manager.begin(snapshot=True)
        
        result = backend.execute("SELECT COUNT(*) AS count FROM test_users")
        print(f"Read {result.data[0]['count']} users in SNAPSHOT isolation")
        
        backend.transaction_manager.commit()
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Error: {e}")
    
    finally:
        backend.disconnect()


def example_context_manager():
    """Example: Using transaction as context manager.
    
    Transactions can be used with 'with' statement for automatic
    commit/rollback.
    """
    print("\n--- Context Manager ---")
    backend = get_backend()
    
    try:
        with backend.transaction_manager.transaction():
            backend.execute(
                "INSERT INTO test_users (name, email) VALUES (?, ?)",
                ("Context User", "context@example.com")
            )
        
        print("Auto-committed via context manager")
        
    except Exception as e:
        print(f"Auto-rolled back: {e}")
    
    finally:
        backend.disconnect()


def cleanup():
    """Clean up test tables."""
    backend = get_backend()
    
    try:
        backend.execute("DROP TABLE IF EXISTS test_users")
        print("Cleanup completed")
    except:
        pass
    
    backend.disconnect()


def main():
    """Run all transaction examples."""
    print("=" * 60)
    print("SQL Server Transaction Examples")
    print("=" * 60)
    
    # Setup test table first
    print("\nSetting up test table...")
    backend = get_backend()
    setup_test_table(backend)
    backend.disconnect()
    
    examples = [
        ("Basic Transaction", example_basic_transaction),
        ("Rollback", example_rollback),
        ("Savepoint", example_savepoint),
        ("Isolation Level", example_isolation_level),
        ("Snapshot Isolation", example_snapshot_isolation),
        ("Context Manager", example_context_manager),
    ]
    
    for name, func in examples:
        try:
            func()
            print(f"   ✓ {name} completed")
        except Exception as e:
            print(f"   ✗ {name} failed: {e}")
    
    print("\n" + "=" * 60)
    cleanup()
    print("Transaction examples completed")


if __name__ == "__main__":
    main()
