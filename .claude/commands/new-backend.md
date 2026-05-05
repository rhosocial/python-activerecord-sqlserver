Create new database backend implementation

Create a new database backend for rhosocial-activerecord.

## Backend Structure

Create directory: src/rhosocial/activerecord/backend/impl/{backend_name}/

Required files:
1. backend.py - StorageBackend implementation (sync and async)
2. dialect.py - SQLDialect implementation
3. config.py - Connection configuration
4. type_adapter.py - Type adapter for Python <-> DB type conversion

## Implementation Guidelines

### backend.py
- Implement StorageBackend for sync
- Implement AsyncStorageBackend for async
- Must support: connect, disconnect, execute, transaction methods
- Use dialect for SQL generation (don't generate SQL directly)

### dialect.py  
- Inherit from SQLDialectBase
- Implement format_* methods for SQL formatting
- Implement supports_* protocol methods for feature detection
- Handle backend-specific SQL syntax

### config.py
- Define connection configuration dataclass
- Include: host, port, database, username, password, etc.
- Provide to_connection_string() method

### type_adapter.py
- Register Python <-> DB type conversions
- Handle special types (datetime, decimal, json, etc.)

## Testing
Create tests in: tests/rhosocial/activerecord_test/feature/backend/{backend_name}/

Ask the user:
1. Backend name (e.g., mysql, postgresql)?
2. Python driver package (e.g., pymysql, psycopg2)?
3. Any special features to support?
