"""DDL CREATE TABLE examples for SQL Server.

This example demonstrates:
1. Basic table creation
2. IDENTITY columns (auto-increment)
3. Constraints (PRIMARY KEY, FOREIGN KEY, CHECK, DEFAULT)
4. Computed columns
5. Temporal tables (SQL Server 2016+)

Connection configuration is loaded from environment variables with defaults.
"""

import os

from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)


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
    )
    
    backend = SQLServerBackend(connection_config=config)
    backend.connect()
    return backend


def example_basic_table():
    """Example: Basic table creation."""
    print("\n--- Basic Table ---")
    backend = get_backend()
    
    backend.execute("""
        IF OBJECT_ID('basic_table', 'U') IS NOT NULL
            DROP TABLE basic_table
    """)
    
    backend.execute("""
        CREATE TABLE basic_table (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(100) NOT NULL,
            email NVARCHAR(200),
            age INT,
            created_at DATETIME2 DEFAULT SYSDATETIME()
        )
    """)
    
    print("Basic table created")
    backend.disconnect()


def example_identity_column():
    """Example: IDENTITY column (auto-increment).
    
    SQL Server uses IDENTITY for auto-increment columns.
    Syntax: IDENTITY(seed, increment)
    """
    print("\n--- IDENTITY Column ---")
    backend = get_backend()
    
    backend.execute("""
        IF OBJECT_ID('identity_example', 'U') IS NOT NULL
            DROP TABLE identity_example
    """)
    
    backend.execute("""
        CREATE TABLE identity_example (
            id INT IDENTITY(1000, 1) PRIMARY KEY,
            data NVARCHAR(100)
        )
    """)
    
    backend.execute("INSERT INTO identity_example (data) VALUES ('test')")
    
    # Get the last identity value
    identity = backend.get_scope_identity()
    print(f"First ID value: {identity}")
    
    backend.disconnect()


def example_constraints():
    """Example: Table with various constraints.
    
    Demonstrates PRIMARY KEY, FOREIGN KEY, CHECK, DEFAULT, UNIQUE.
    """
    print("\n--- Constraints ---")
    backend = get_backend()
    
    # Drop tables in reverse order due to FK
    backend.execute("""
        IF OBJECT_ID('orders', 'U') IS NOT NULL
            DROP TABLE orders
    """)
    
    backend.execute("""
        IF OBJECT_ID('customers', 'U') IS NOT NULL
            DROP TABLE customers
    """)
    
    backend.execute("""
        CREATE TABLE customers (
            id INT IDENTITY(1,1) PRIMARY KEY,
            email NVARCHAR(200) UNIQUE NOT NULL,
            name NVARCHAR(100) NOT NULL,
            credit_limit DECIMAL(10,2) DEFAULT 0.00,
            CONSTRAINT CHK_credit_limit_positive CHECK (credit_limit >= 0)
        )
    """)
    
    backend.execute("""
        CREATE TABLE orders (
            id INT IDENTITY(1,1) PRIMARY KEY,
            customer_id INT NOT NULL,
            order_date DATE DEFAULT GETDATE(),
            total_amount DECIMAL(10,2),
            status NVARCHAR(20) DEFAULT 'pending',
            CONSTRAINT FK_orders_customer 
                FOREIGN KEY (customer_id) REFERENCES customers(id)
                ON DELETE CASCADE,
            CONSTRAINT CHK_total_positive CHECK (total_amount > 0),
            CONSTRAINT CHK_status CHECK (status IN ('pending', 'processing', 'shipped', 'delivered'))
        )
    """)
    
    print("Tables with constraints created")
    backend.disconnect()


def example_computed_column():
    """Example: Computed column.
    
    SQL Server supports computed columns (virtual or persisted).
    """
    print("\n--- Computed Column ---")
    backend = get_backend()
    
    backend.execute("""
        IF OBJECT_ID('products', 'U') IS NOT NULL
            DROP TABLE products
    """)
    
    backend.execute("""
        CREATE TABLE products (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(100) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            quantity INT NOT NULL DEFAULT 0,
            total_value AS (price * quantity) PERSISTED,
            display_name AS (name + ' ($' + CAST(price AS NVARCHAR(20)) + ')')
        )
    """)
    
    backend.execute(
        "INSERT INTO products (name, price, quantity) VALUES (?, ?, ?)",
        ("Widget", 9.99, 100)
    )
    
    result = backend.execute("SELECT * FROM products")
    row = result.data[0]
    print(f"Product: {row['display_name']}")
    print(f"Total value: ${row['total_value']}")
    
    backend.disconnect()


def example_temporal_table():
    """Example: Temporal table (SQL Server 2016+).
    
    Temporal tables automatically track history of data changes.
    """
    print("\n--- Temporal Table ---")
    backend = get_backend()
    
    # Drop history table first
    backend.execute("""
        IF OBJECT_ID('employees_history', 'U') IS NOT NULL
            DROP TABLE employees_history
    """)
    
    try:
        # Try to disable system versioning if exists
        backend.execute("""
            IF OBJECT_ID('employees', 'U') IS NOT NULL
            BEGIN
                ALTER TABLE employees SET (SYSTEM_VERSIONING = OFF);
                DROP TABLE employees;
            END
        """)
    except:
        pass
    
    try:
        backend.execute("""
            CREATE TABLE employees (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(100) NOT NULL,
                department NVARCHAR(50),
                salary DECIMAL(10,2),
                valid_from DATETIME2 GENERATED ALWAYS AS ROW START HIDDEN,
                valid_to DATETIME2 GENERATED ALWAYS AS ROW END HIDDEN,
                PERIOD FOR SYSTEM_TIME (valid_from, valid_to)
            )
            WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = dbo.employees_history))
        """)
        
        print("Temporal table created")
        
    except Exception as e:
        print(f"Note: Temporal table may require specific permissions: {e}")
    
    backend.disconnect()


def example_table_with_json():
    """Example: Table with JSON data.
    
    SQL Server 2016+ supports JSON functions, though not a native JSON type.
    Uses ISJSON() for validation in CHECK constraint.
    """
    print("\n--- JSON Data ---")
    backend = get_backend()
    
    backend.execute("""
        IF OBJECT_ID('json_data', 'U') IS NOT NULL
            DROP TABLE json_data
    """)
    
    backend.execute("""
        CREATE TABLE json_data (
            id INT IDENTITY(1,1) PRIMARY KEY,
            data NVARCHAR(MAX),
            CONSTRAINT CHK_json CHECK (ISJSON(data) = 1)
        )
    """)
    
    backend.execute("""
        INSERT INTO json_data (data) VALUES (JSON_OBJECT('name': 'John', 'age': 30))
    """)
    
    result = backend.execute("""
        SELECT 
            id,
            JSON_VALUE(data, '$.name') AS name,
            JSON_VALUE(data, '$.age') AS age
        FROM json_data
    """)
    
    for row in result.data:
        print(f"ID: {row['id']}, Name: {row['name']}, Age: {row['age']}")
    
    backend.disconnect()


def cleanup():
    """Clean up test tables."""
    print("\n--- Cleanup ---")
    backend = get_backend()
    
    tables = ['basic_table', 'identity_example', 'customers', 'orders', 
              'products', 'json_data']
    
    for table in tables:
        backend.execute(f"IF OBJECT_ID('{table}', 'U') IS NOT NULL DROP TABLE {table}")
    
    try:
        backend.execute("ALTER TABLE employees SET (SYSTEM_VERSIONING = OFF)")
    except:
        pass
    
    backend.execute("IF OBJECT_ID('employees', 'U') IS NOT NULL DROP TABLE employees")
    backend.execute("IF OBJECT_ID('employees_history', 'U') IS NOT NULL DROP TABLE employees_history")
    
    backend.disconnect()
    print("Cleanup completed")


def main():
    """Run all DDL examples."""
    print("=" * 60)
    print("SQL Server DDL Examples")
    print("=" * 60)
    
    examples = [
        ("Basic Table", example_basic_table),
        ("IDENTITY Column", example_identity_column),
        ("Constraints", example_constraints),
        ("Computed Column", example_computed_column),
        ("Temporal Table", example_temporal_table),
        ("JSON Data", example_table_with_json),
    ]
    
    for name, func in examples:
        try:
            func()
            print(f"   ✓ {name} completed")
        except Exception as e:
            print(f"   ✗ {name} failed: {e}")
    
    print("\n" + "=" * 60)
    cleanup()
    print("DDL examples completed")


if __name__ == "__main__":
    main()
