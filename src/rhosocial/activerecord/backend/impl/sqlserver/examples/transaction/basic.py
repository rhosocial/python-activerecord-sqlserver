# src/rhosocial/activerecord/backend/impl/sqlserver/examples/transaction/basic.py
"""Transaction management examples for SQL Server.

Demonstrates:
- Basic transaction control (BEGIN, COMMIT, ROLLBACK)
- Savepoint usage
- Isolation levels
- SNAPSHOT isolation
"""

import yaml
from pathlib import Path

from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)
from rhosocial.activerecord.backend.transaction import IsolationLevel


def get_backend():
    """Get a configured backend instance."""
    config_path = Path(__file__).parent.parent.parent.parent.parent.parent / "tests" / "config" / "sqlserver_scenarios.yaml"
    
    config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            config = config_data.get('scenarios', {}).get('sqlserver_2022', {})
    
    backend = SQLServerBackend(
        connection_config=SQLServerConnectionConfig(
            host=config.get('host', 'localhost'),
            port=config.get('port', 1433),
            database=config.get('database', 'test_db'),
            username=config.get('username', 'sa'),
            password=config.get('password', ''),
            driver=config.get('driver', 'ODBC Driver 17 for SQL Server'),
            encrypt=config.get('encrypt', False),
            trust_server_certificate=config.get('trust_server_certificate', True),
            autocommit=False,
        )
    )
    
    return backend


def example_basic_transaction():
    """Example: Basic transaction with COMMIT.
    
    SQL Server uses BEGIN TRANSACTION / COMMIT TRANSACTION.
    """
    backend = get_backend()
    backend.connect()
    
    try:
        backend.transaction_manager.begin()
        
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
        
        backend.transaction_manager.commit()
        print("Transaction committed successfully")
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Transaction rolled back: {e}")
    
    finally:
        backend.disconnect()


def example_rollback():
    """Example: Transaction with ROLLBACK.
    
    Demonstrates how to rollback a transaction on error.
    """
    backend = get_backend()
    backend.connect()
    
    try:
        backend.transaction_manager.begin()
        
        backend.execute(
            "INSERT INTO test_users (name, email) VALUES (?, ?)",
            ("Jane Doe", "jane@example.com")
        )
        
        raise Exception("Simulated error to trigger rollback")
        
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
    backend = get_backend()
    backend.connect()
    
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
    """Example: Transaction with isolation level.
    
    SQL Server supports multiple isolation levels.
    """
    backend = get_backend()
    backend.connect()
    
    try:
        backend.transaction_manager.begin(isolation_level=IsolationLevel.SERIALIZABLE)
        
        result = backend.execute("SELECT * FROM test_users")
        print(f"Read {len(result.data)} users in SERIALIZABLE isolation")
        
        backend.transaction_manager.commit()
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Error: {e}")
    
    finally:
        backend.disconnect()


def example_snapshot_isolation():
    """Example: SNAPSHOT isolation level.
    
    SQL Server's SNAPSHOT isolation provides MVCC-like behavior.
    """
    backend = get_backend()
    backend.connect()
    
    try:
        backend.transaction_manager.begin(snapshot=True)
        
        result = backend.execute("SELECT * FROM test_users")
        print(f"Read {len(result.data)} users in SNAPSHOT isolation")
        
        backend.transaction_manager.commit()
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Error: {e}")
    
    finally:
        backend.disconnect()


def example_context_manager():
    """Example: Using transaction as context manager.
    
    Transactions can be used with 'with' statement for automatic commit/rollback.
    """
    backend = get_backend()
    backend.connect()
    
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


def example_lock_timeout():
    """Example: Setting lock timeout.
    
    Controls how long SQL Server waits for locked resources.
    """
    backend = get_backend()
    backend.connect()
    
    try:
        backend.transaction_manager.begin()
        backend.transaction_manager.set_lock_timeout(5000)
        print("Lock timeout set to 5000ms (5 seconds)")
        
        backend.execute("SELECT * FROM test_users")
        
        backend.transaction_manager.commit()
        
    except Exception as e:
        backend.transaction_manager.rollback()
        print(f"Error: {e}")
    
    finally:
        backend.disconnect()


def cleanup():
    """Clean up test tables."""
    backend = get_backend()
    backend.connect()
    
    try:
        backend.execute("DROP TABLE IF EXISTS test_users")
        backend.disconnect()
        print("Cleanup completed")
    except:
        backend.disconnect()


def main():
    """Run all transaction examples."""
    print("=" * 60)
    print("SQL Server Transaction Examples")
    print("=" * 60)
    
    examples = [
        ("Basic Transaction", example_basic_transaction),
        ("Rollback", example_rollback),
        ("Savepoint", example_savepoint),
        ("Isolation Level", example_isolation_level),
        ("Snapshot Isolation", example_snapshot_isolation),
        ("Context Manager", example_context_manager),
        ("Lock Timeout", example_lock_timeout),
    ]
    
    for name, func in examples:
        print(f"\n{name}:")
        try:
            func()
            print("   ✓ Success")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    cleanup()
    print("Transaction examples completed")


if __name__ == "__main__":
    main()
