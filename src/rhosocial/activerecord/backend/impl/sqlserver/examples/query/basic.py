"""Basic query examples for SQL Server.

This example demonstrates:
1. Simple SELECT queries
2. Parameterized queries
3. Pagination with OFFSET FETCH
4. Aggregation queries
5. Common Table Expressions (CTE)
6. Window functions

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


def example_simple_select():
    """Example: Simple SELECT query."""
    print("\n--- Simple SELECT ---")
    backend = get_backend()
    
    result = backend.execute("SELECT 1 AS id, 'Hello' AS message")
    
    print(f"Query returned {len(result.data)} rows")
    for row in result.data:
        print(f"  id={row['id']}, message={row['message']}")
    
    backend.disconnect()
    return result


def example_parameterized_query():
    """Example: Parameterized query with placeholders.
    
    SQL Server uses ? for parameter placeholders (qmark style).
    """
    print("\n--- Parameterized Query ---")
    backend = get_backend()
    
    result = backend.execute(
        "SELECT name FROM sys.databases WHERE database_id < ?",
        (5,)
    )
    
    print(f"Found {len(result.data)} databases")
    for row in result.data:
        print(f"  {row['name']}")
    
    backend.disconnect()
    return result


def example_pagination():
    """Example: Pagination with OFFSET FETCH.
    
    SQL Server 2012+ uses OFFSET FETCH syntax for pagination.
    Note: ORDER BY is required when using OFFSET FETCH.
    """
    print("\n--- Pagination (OFFSET FETCH) ---")
    backend = get_backend()
    
    page = 1
    page_size = 10
    offset = (page - 1) * page_size
    
    result = backend.execute("""
        SELECT name, database_id, create_date
        FROM sys.databases
        ORDER BY name
        OFFSET ? ROWS
        FETCH NEXT ? ROWS ONLY
    """, (offset, page_size))
    
    print(f"Page {page} (showing {page_size} rows):")
    for row in result.data:
        print(f"  {row['name']} (id={row['database_id']})")
    
    backend.disconnect()
    return result


def example_aggregation():
    """Example: Aggregation queries."""
    print("\n--- Aggregation ---")
    backend = get_backend()
    
    result = backend.execute("""
        SELECT 
            COUNT(*) AS total_count,
            MIN(name) AS min_name,
            MAX(name) AS max_name
        FROM sys.databases
    """)
    
    if result.data:
        row = result.data[0]
        print(f"Total databases: {row['total_count']}")
        print(f"Name range: {row['min_name']} to {row['max_name']}")
    
    backend.disconnect()
    return result


def example_group_by():
    """Example: GROUP BY with HAVING."""
    print("\n--- GROUP BY ---")
    backend = get_backend()
    
    result = backend.execute("""
        SELECT 
            type_desc,
            COUNT(*) AS count
        FROM sys.master_files
        GROUP BY type_desc
        HAVING COUNT(*) > 0
        ORDER BY count DESC
    """)
    
    print("File types:")
    for row in result.data:
        print(f"  {row['type_desc']}: {row['count']} files")
    
    backend.disconnect()
    return result


def example_case_expression():
    """Example: CASE expression for conditional logic."""
    print("\n--- CASE Expression ---")
    backend = get_backend()
    
    result = backend.execute("""
        SELECT 
            name,
            CASE 
                WHEN database_id = 1 THEN 'System'
                WHEN database_id = 2 THEN 'TempDB'
                WHEN database_id BETWEEN 3 AND 4 THEN 'Model/MSDB'
                ELSE 'User Database'
            END AS category
        FROM sys.databases
        ORDER BY database_id
    """)
    
    for row in result.data:
        print(f"  {row['name']}: {row['category']}")
    
    backend.disconnect()
    return result


def example_common_table_expression():
    """Example: Common Table Expression (CTE)."""
    print("\n--- CTE ---")
    backend = get_backend()
    
    result = backend.execute("""
        WITH db_info AS (
            SELECT name, database_id, create_date
            FROM sys.databases
            WHERE database_id < 10
        )
        SELECT * FROM db_info
        ORDER BY name
    """)
    
    print("Databases (via CTE):")
    for row in result.data:
        print(f"  {row['name']}")
    
    backend.disconnect()
    return result


def example_window_function():
    """Example: Window functions (SQL Server 2012+)."""
    print("\n--- Window Functions ---")
    backend = get_backend()
    
    result = backend.execute("""
        SELECT 
            name,
            database_id,
            ROW_NUMBER() OVER (ORDER BY name) AS row_num,
            RANK() OVER (ORDER BY database_id) AS rank
        FROM sys.databases
        ORDER BY name
    """)
    
    for row in result.data[:5]:
        print(f"  {row['row_num']}: {row['name']} (rank={row['rank']})")
    
    backend.disconnect()
    return result


def main():
    """Run all query examples."""
    print("=" * 60)
    print("SQL Server Basic Query Examples")
    print("=" * 60)
    
    examples = [
        ("Simple SELECT", example_simple_select),
        ("Parameterized Query", example_parameterized_query),
        ("Pagination (OFFSET FETCH)", example_pagination),
        ("Aggregation", example_aggregation),
        ("GROUP BY", example_group_by),
        ("CASE Expression", example_case_expression),
        ("CTE", example_common_table_expression),
        ("Window Functions", example_window_function),
    ]
    
    for name, func in examples:
        try:
            func()
            print(f"   ✓ {name} completed")
        except Exception as e:
            print(f"   ✗ {name} failed: {e}")
    
    print("\n" + "=" * 60)
    print("Query examples completed")


if __name__ == "__main__":
    main()
