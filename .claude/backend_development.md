# A Complete Guide to Backend Development

## Overview

This guide provides comprehensive instructions for implementing new database backends for the rhosocial-activerecord ecosystem. A robust backend is more than just a query executor; it's a complete implementation that includes a database-specific **SQL Dialect**, a precise **Type Adaptation** system, reliable **Transaction Management**, robust **Error Handling**, clear **Feature Detection**, and **Performance Optimizations**.

This document covers these essential pillars, outlining the required architecture, patterns, and best practices for creating a fully-featured and reliable backend.

**Important Design Constraint**: Backend implementations must be built using **native database drivers only** (e.g., `mysql-connector-python`, `psycopg`). Do not use or depend on other ORMs like SQLAlchemy or Django ORM. This ensures the ecosystem remains lightweight and independent.

## Reference Implementations

For practical examples of fully-featured, production-ready backend implementations, developers can refer to the following projects:

*   **`rhosocial-activerecord-mysql`**: A mature MySQL backend implementation.
*   **`rhosocial-activerecord-postgres`**: A robust PostgreSQL backend implementation.

These repositories provide concrete examples of how to implement all the components discussed in this guide, including their dedicated test suites. Studying their codebases, especially their `backend.py`, `adapters.py`, and `tests/` directories, is highly recommended as a practical reference.

## Backend Architecture

### Package Structure

The package structure is standardized to support namespace packages and maintain consistency.

```
rhosocial-activerecord-{backend}/
├── src/
│   └── rhosocial/
│       └── activerecord/
│           └── backend/
│               └── impl/
│                   └── {backend}/
│                       ├── __init__.py
│                       ├── backend.py       # Main backend implementation
│                       ├── adapters.py      # Backend-specific type adapters
│                       ├── config.py        # Connection configuration
│                       ├── dialect.py       # SQL dialect handling
│                       ├── transaction.py   # Transaction management
│                       ├── expression/      # Backend-specific expressions (directory)
│                       │   └── __init__.py
│                       ├── functions/       # Backend-specific SQL functions (directory)
│                       │   └── __init__.py
│                       └── features.py      # Optional: Feature detection
```

#### Expression Directory

All backend-specific expressions **must** be placed in the `expression/` directory (not `expressions.py`). This ensures consistent structure across all backends.

```python
# expression/__init__.py
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.dialect import SQLDialectBase

class MyBackendReindexExpression(BaseExpression):
    """MyBackend-specific REINDEX expression."""
    pass
```

**Important**: Use absolute imports for expressions from core or other backends to avoid deep relative import chains:

```python
# Correct - absolute imports
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.dialect import SQLDialectBase

# Avoid - deep relative imports
from .....expression.bases import BaseExpression  # Not recommended
```

## Key Backend Concepts

Before diving into components, it is crucial to understand the **Expression-Dialect System**, which is fundamental to how SQL queries are built and executed:

### The Expression-Dialect Architecture

The expression-dialect system separates SQL query construction from SQL generation, enabling database-agnostic query building while allowing database-specific formatting.

### Advantages of Our Approach

Our expression-dialect system offers several advantages over traditional approaches:

- **No Complex State Management**: Unlike systems that maintain complex object states, our expressions are stateless and pure
- **Direct SQL Generation**: Only 2 steps from expression to SQL, avoiding multi-layer compilation architectures
- **Standard-Based Implementation**: Using the dummy backend as a complete SQL standard reference, other dialects only need to override differences
- **Test-Friendly**: The dummy backend allows testing SQL generation without database connections
- **No Hidden Compilation Steps**: Unlike systems with complex multi-stage compilation, our approach is direct and predictable
- **Fragment Generation**: Any expression can generate SQL fragments independently, unlike systems that require complete query compilation
- **Explicit Control**: Unlike systems with automatic session management or hidden behaviors, our approach gives users complete visibility into when database operations occur
- **Simple Architecture**: No complex object lifecycle tracking, automatic caching mechanisms, or multiple state transitions

#### Architecture Principles
- **Expression classes** implement the `ToSQLProtocol` and define how to generate SQL
- **Each expression class** must call its dialect's `format_*` methods instead of self-formatting
- **Dialect classes** are responsible for the actual SQL formatting and parameter handling
- **Expression classes** should never directly concatenate SQL strings; they should delegate to dialect
- This pattern ensures each dialect can customize formatting behavior while maintaining security

#### Relationship Model
```
Expression.to_sql() -> Dialect.format_*() -> SQL string and parameters
```

#### Key Components
1. **Expression Formatting**: Expression classes (subclasses of `BaseExpression`) build query structure and call dialect methods for formatting. The **expression system** handles query construction by calling dialect formatting methods.

2.  **Type Adaptation**: This applies to plain Python values passed as parameters (e.g., a `datetime` object in a `WHERE` clause). The **backend is responsible** for converting these values into a format the native database driver can consume. For instance, converting a Python `datetime` object into a Python `str`. This is handled by the **SQLTypeAdapter Pattern**.

#### Expression System Modules
- `bases.py`: Abstract base classes and protocol definitions
- `core.py`: Core expression components (columns, literals, function calls, subqueries)
- `mixins.py`: Operator-overloading capabilities for expressions
- `operators.py`: SQL operations (binary, unary, arithmetic expressions)
- `predicates.py`: SQL predicate expressions (WHERE clause conditions)
- `query_parts.py`: SQL query clauses (WHERE, GROUP BY, HAVING, ORDER BY, etc.)
- `statements.py`: DML/DQL/DDL statements (SELECT, INSERT, UPDATE, DELETE, etc.)
- `functions.py`: Standalone factory functions for creating SQL expressions
- `aggregates.py`: SQL aggregation expressions and functions
- `advanced_functions.py`: Advanced SQL functions (CASE, CAST, EXISTS, window functions)
- `query_sources.py`: Data source expressions (VALUES, table functions, CTEs)
- `graph.py`: SQL Graph Query (MATCH) expressions

#### Important Limitation
The expression system faithfully builds SQL according to user intent, but **does not validate** whether the generated SQL complies with SQL standards or can be successfully executed in the target database. Semantic validation is the responsibility of the database engine.

#### Design Philosophy: Explicit Over Implicit
Our expression system follows the principle of explicit control over implicit behavior:
- No hidden state management or object lifecycle tracking
- No automatic query compilation or caching mechanisms
- No complex object state transitions
- Users have complete visibility and control over SQL generation
- Unlike systems with complex multi-stage compilation, our approach is direct and predictable

## A Note on Asynchronous Backends

The architecture supports parallel synchronous and asynchronous backends. If you choose to provide an asynchronous version of your backend, it must adhere to one fundamental principle:

-   **Functional Equivalence**: The `AsyncStorageBackend` must provide the same features and functionality as its synchronous `StorageBackend` counterpart. This is achieved by implementing asynchronous versions of all I/O-bound methods (e.g., `async def connect(...)`, `async def execute(...)`) and using async-compatible mixins where appropriate. The goal is to ensure a seamless and predictable developer experience, regardless of whether they are using the sync or async version of your backend.

## The Core Components

A backend is composed of several key components that work together. The following sections detail each required piece.

### 1. The `StorageBackend` Interface

Every backend must implement the `StorageBackend` abstract base class. This is the main entry point for the core library. It is a large interface, and a concrete backend must implement all its abstract methods.

```python
# backend.py
from typing import Any, Dict, List, Optional, Tuple, Type
from ...base import StorageBackend, ConnectionConfig
from ...type_adapter import SQLTypeAdapter

class MyBackend(StorageBackend):
    """Implementation of MyDatabase backend using native driver."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connection = None
        self._transaction_manager = None # Must be initialized in connect()
        self._register_my_adapters() # NEW: Call to register adapters

    # --- Methods to be Implemented by Concrete Backend ---

    def connect(self) -> None:
        """Establish database connection."""
        pass
    
    def disconnect(self) -> None:
        """Close database connection."""
        pass

    def ping(self, reconnect: bool = True) -> bool:
        """Check if connection is valid."""
        pass

    def execute(self, sql: str, params: Optional[Tuple] = None, returning: Optional[Union[bool, List[str], ReturningOptions]] = None, column_adapters: Optional[Dict[str, Tuple[SQLTypeAdapter, Type]]] = None) -> QueryResult:
        """Executes a SQL query."""
        pass
    
    def get_server_version(self) -> tuple:
        """Get database server version as (major, minor, patch)."""
        pass

    def introspect_and_adapt(self) -> None:
        """Introspect backend and adapt to actual database server capabilities.

        This method is called during model configuration to ensure the backend
        adapts to the actual database server version and capabilities. It should:
        1. Connect to the database (if not already connected)
        2. Query the actual server version
        3. Re-initialize dialect and type adapters based on actual version

        Backends that don't need version-specific adaptation (e.g., SQLite, Dummy)
        can implement this as a no-op.
        """
        pass

    def _initialize_capabilities(self) -> DatabaseCapabilities:
        """Declare all features supported by this backend."""
        pass

    def _handle_error(self, error: Exception) -> None:
        """Catch driver-specific exceptions and raise standard errors."""
        pass
    
    @property
    def transaction_manager(self) -> 'TransactionManager':
        """Return an instance of the backend's transaction manager."""
        pass

    @property
    def dialect(self) -> 'SQLDialectBase':
        """Return an instance of the backend's SQL dialect."""
        pass

    # --- Type Adaptation System Hooks ---

    def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[SQLTypeAdapter, Type]]:
        """
        [Backend Implementation] Provides this backend's preferred
        type conversion strategies to the core library.
        """
        # (Full implementation shown in the Type Adaptation section)
        pass
    
    def _register_my_adapters(self):
        """
        A private helper to instantiate and register all necessary type adapters.
        """
        # (Full implementation shown in the Type Adaptation section)
        pass
```

### 2. Connection Configuration

Define an immutable configuration class for your backend.

```python
# config.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from rhosocial.activerecord.backend.config import BaseConfig

@dataclass(frozen=True)
class MyDatabaseConfig(BaseConfig):
    host: str = "localhost"
    port: int = 5432
    database: str
    user: Optional[str] = None
    password: Optional[str] = None
    # ... other options like charset, ssl_mode, etc.
```

### 3. SQL Dialect

The SQL Dialect is the backend's "translator" for database-specific syntax. This is where you define how your backend speaks SQL.

#### Protocol and Mixin Architecture

The dialect system uses a **Protocol-Mixin** architecture:

- **Protocols** (`protocols.py`): Define the interface contract - what methods a dialect must implement
- **Mixins** (`mixins.py`): Provide default SQL standard implementations that dialects can override

Every dialect inherits from:
1. `SQLDialectBase` - Core dialect functionality
2. Relevant Mixins - Default implementations for supported features
3. Relevant Protocols - Interface contracts for type checking

##### Current Protocols and Mixins (Main Package)

| Protocol | Mixin | Description |
|----------|-------|-------------|
| `WindowFunctionSupport` | `WindowFunctionMixin` | Window functions (OVER, PARTITION BY) |
| `CTESupport` | `CTEMixin` | Common Table Expressions (WITH clause) |
| `AdvancedGroupingSupport` | `AdvancedGroupingMixin` | ROLLUP, CUBE, GROUPING SETS |
| `ReturningSupport` | `ReturningMixin` | RETURNING clause |
| `UpsertSupport` | `UpsertMixin` | UPSERT operations (ON CONFLICT) |
| `LateralJoinSupport` | `LateralJoinMixin` | LATERAL joins |
| `ArraySupport` | `ArrayMixin` | Array types and operations |
| `JSONSupport` | `JSONMixin` | JSON types and operations |
| `ExplainSupport` | `ExplainMixin` | EXPLAIN statement |
| `FilterClauseSupport` | `FilterClauseMixin` | FILTER clause for aggregates |
| `OrderedSetAggregationSupport` | `OrderedSetAggregationMixin` | WITHIN GROUP (ORDER BY) |
| `MergeSupport` | `MergeMixin` | MERGE statement |
| `TemporalTableSupport` | `TemporalTableMixin` | FOR SYSTEM_TIME queries |
| `QualifyClauseSupport` | `QualifyClauseMixin` | QUALIFY clause |
| `LockingSupport` | `LockingMixin` | FOR UPDATE, SKIP LOCKED |
| `GraphSupport` | `GraphMixin` | Graph queries (MATCH) |
| `JoinSupport` | `JoinMixin` | JOIN operations |
| `SetOperationSupport` | `SetOperationMixin` | UNION, INTERSECT, EXCEPT |
| `ILIKESupport` | `ILIKEMixin` | Case-insensitive LIKE |
| `TableSupport` | `TableMixin` | CREATE/DROP/ALTER TABLE |
| `ViewSupport` | `ViewMixin` | CREATE/DROP VIEW |
| `TruncateSupport` | `TruncateMixin` | TRUNCATE TABLE |
| `SchemaSupport` | `SchemaMixin` | CREATE/DROP SCHEMA |
| `IndexSupport` | `IndexMixin` | CREATE/DROP INDEX |
| `SequenceSupport` | `SequenceMixin` | CREATE/DROP/ALTER SEQUENCE |
| `TriggerSupport` | `TriggerMixin` | CREATE/DROP TRIGGER (SQL:1999) |
| `FunctionSupport` | `FunctionMixin` | CREATE/DROP FUNCTION (SQL/PSM) |

##### Principles for Adding New Protocols/Mixins

**When to add to Main Package:**
1. Feature is defined in **SQL standard** (SQL:1999, SQL:2003, SQL:2008, SQL:2011, SQL:2016)
2. Feature is widely supported across multiple database systems
3. Feature is a **DDL (Data Definition Language)** or **DML (Data Manipulation Language)** construct

**When to add to Dialect-Specific Extension:**
1. Feature is **dialect-specific** (not in SQL standard)
2. Feature is implemented differently across databases
3. Feature is proprietary to a specific database vendor

**Example Analysis:**

| Feature | SQL Standard? | Location |
|---------|---------------|----------|
| `CREATE TRIGGER` | Yes (SQL:1999) | Main Package (`TriggerSupport`) |
| `CREATE FUNCTION` | Yes (SQL/PSM) | Main Package (`FunctionSupport`) |
| `COMMENT ON` | No (PostgreSQL/Oracle) | PostgreSQL Extension |
| `CREATE TYPE ... AS ENUM` | No (PostgreSQL-specific) | PostgreSQL Extension |
| `AUTO_INCREMENT` | No (MySQL-specific) | MySQL Extension |
| `BIGSERIAL` | No (PostgreSQL-specific) | PostgreSQL Extension |

##### Implementation Steps for New Protocols

1. **Add to Main Package** (if SQL standard):
   ```python
   # protocols.py
   @runtime_checkable
   class NewFeatureSupport(Protocol):
       def supports_new_feature(self) -> bool: ...
       def format_new_feature_statement(self, expr) -> Tuple[str, tuple]: ...

   # mixins.py
   class NewFeatureMixin:
       def supports_new_feature(self) -> bool: return False
       def format_new_feature_statement(self, expr) -> Tuple[str, tuple]:
           # SQL standard implementation
           ...
   ```

2. **Add to Dialect Extension** (if dialect-specific):
   ```python
   # postgres/dialect.py
   def supports_dialect_feature(self) -> bool: return True
   def format_dialect_statement(self, ...): ...
   ```

3. **Update DummyDialect** (for main package protocols):
   ```python
   # impl/dummy/dialect.py
   class DummyDialect(
       ...,
       NewFeatureMixin,
       NewFeatureSupport,
   ):
       def supports_new_feature(self) -> bool: return True
   ```

4. **Add Tests**:
   - `tests/.../dummy2/test_new_feature.py` - Expression tests
   - `tests/.../dummy/test_dummy_protocol_support.py` - Protocol support verification

```python
# dialect.py
from rhosocial.activerecord.backend.dialect import (
    SQLDialect, ReturningClauseHandler, TypeMapping
)
from typing import Dict, List, Optional

class MyDatabaseDialect(SQLDialect):
    def __init__(self):
        super().__init__()
        self.returning_handler = MyDatabaseReturningHandler()
    
    def quote_identifier(self, identifier: str) -> str: return f'"{identifier}"'
    def get_placeholder(self, name: str = None) -> str: return "?"
    
    def format_limit_offset(self, sql: str, limit: Optional[int], offset: Optional[int]) -> str:
        if limit is not None: sql += f" LIMIT {limit}"
        if offset is not None: sql += f" OFFSET {offset}"
        return sql
    
    def get_type_mappings(self) -> Dict[str, TypeMapping]:
        return {"INTEGER": TypeMapping("INTEGER"), "TEXT": TypeMapping("TEXT"), ...}

class MyDatabaseReturningHandler(ReturningClauseHandler):
    @property
    def is_supported(self) -> bool: return True
    
    def format_clause(self, columns: Optional[List[str]] = None) -> str:
        cols = "*" if not columns else ', '.join(self.dialect.quote_identifier(c) for c in columns)
        return f"RETURNING {cols}"
```

### 4. The Type Adaptation System

This system handles the conversion of Python values to and from formats compatible with the native database driver. This is a two-part implementation: defining the adapters, and then telling the core library how to use them.

#### a. The `SQLTypeAdapter` Pattern
Each adapter is a stateless component for converting between a source Python type and a target **driver-compatible Python type**.

```python
# From: src/rhosocial/activerecord/backend/type_adapter.py (Core Library)
from abc import ABC, abstractmethod
from typing import Type, Set, Dict

class BaseSQLTypeAdapter(ABC):
    def __init__(self):
        self._supported_types: Dict[Type, Set[Type]] = {}

    def _register_type(self, py_type: Type, driver_py_type: Type):
        """Registers that this adapter can convert from py_type to driver_py_type."""
        if py_type not in self._supported_types:
            self._supported_types[py_type] = set()
        self._supported_types[py_type].add(driver_py_type)

    @abstractmethod
    def _do_to_database(self, value, target_type, options): ...
    @abstractmethod
    def _do_from_database(self, value, target_type, options): ...
```

#### b. Registering Adapters in Your Backend
In your backend's `__init__` (or a helper), you instantiate and register all adapters your backend will use.

```python
# backend.py (inside your MyBackend class)
from .adapters import MyCustomJSONAdapter
from ...type_adapter import DateTimeAdapter, DecimalAdapter 

def _register_my_adapters(self):
    """Register all adapters the backend will use."""
    all_adapters = [
        DateTimeAdapter(),
        DecimalAdapter(),
        MyCustomJSONAdapter(), # Backend-specific adapter can override standard ones
    ]
    for adapter in all_adapters:
        for py_type, driver_types in adapter.supported_types.items():
            for driver_type in driver_types:
                self.adapter_registry.register(
                    adapter, py_type, driver_type, allow_override=True
                )
```

#### c. Providing Suggestions via `get_default_adapter_suggestions`
This method is the "glue". It defines your backend's preferred conversion strategy.

```python
# backend.py (inside your MyBackend class)
def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[SQLTypeAdapter, Type]]:
    suggestions: Dict[Type, Tuple[SQLTypeAdapter, Type]] = {}
    from datetime import date, datetime
    from decimal import Decimal
    # ... other imports

    # Define the desired (Source Python Type -> Target Driver Python Type) mappings
    type_mappings = [
        (datetime, str),    # Prefer converting datetimes to ISO strings
        (Decimal, str),     # Prefer converting Decimals to strings for precision
        (dict, str),
    ]

    for py_type, driver_type in type_mappings:
        adapter = self.adapter_registry.get_adapter(py_type, driver_type)
        if adapter:
            suggestions[py_type] = (adapter, driver_type)
    return suggestions
```

### 5. Transaction Management
Proper transaction management is a cornerstone of any reliable database backend, ensuring data consistency and ACID compliance.

```python
# transaction.py
from contextlib import contextmanager

class MyTransactionManager:
    def __init__(self, backend_connection):
        self.connection = backend_connection
        self._savepoint_counter = 0
    
    @contextmanager
    def transaction(self, isolation_level: Optional[str] = None):
        self.connection.begin()
        try:
            yield self
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    @contextmanager
    def savepoint(self, name: Optional[str] = None):
        self._savepoint_counter += 1
        name = name or f"sp_{self._savepoint_counter}"
        self.connection.execute(f"SAVEPOINT {name}")
        try:
            yield
            self.connection.execute(f"RELEASE SAVEPOINT {name}")
        except Exception:
            self.connection.execute(f"ROLLBACK TO SAVEPOINT {name}")
            raise
```

### 6. Error Handling
A robust backend must catch driver-specific exceptions and re-raise them as standardized `DatabaseError` subclasses from the core library (`IntegrityError`, `ConnectionError`, etc.).

```python
# In backend.py, as part of the _handle_error implementation
from ...errors import IntegrityError, ConnectionError
# import native_driver

def _handle_error(self, error: Exception) -> None:
    if isinstance(error, native_driver.UniqueConstraintViolation):
        raise IntegrityError("Unique constraint failed") from error
    if isinstance(error, native_driver.CannotConnectNow):
        raise ConnectionError("Connection failed") from error
    # Fallback to a generic database error
    raise DatabaseError(f"An unexpected database error occurred: {error}") from error
```

### 7. Other Core Components
- **Feature Detection**: A class that checks the database version to declare supported features (CTEs, Window Functions, etc.).
- **Performance Optimization**: Advanced features like connection pooling and query optimization hints.

## Testing Requirements

A backend is only as reliable as its tests. The test suite should be comprehensive and cover all aspects of the implementation.

- **Connection & Configuration**: Test successful connections, disconnections, pings, and failure modes with bad configurations.
- **CRUD & Query Execution**: Verify that `execute`, `fetch_one`, `fetch_all`, etc., work correctly for all statement types.
- **Type Adaptation System**:
    - Write dedicated unit tests for each custom `SQLTypeAdapter`.
    - Test that `get_default_adapter_suggestions` returns the correct adapter and target type.
    - Write integration tests that save and retrieve models with all supported data types to ensure end-to-end correctness.
- **Transaction Management**: Test `commit`, `rollback`, and savepoints.
- **Dialect & SQL Formatting**: Test that the dialect produces correct SQL for `LIMIT`/`OFFSET`, `RETURNING`, etc.
- **Error Handling**: Test that driver-specific errors are correctly caught and re-raised as standard exceptions.
- **Expression Formatting**: Integration tests should confirm that queries using `SQLExpression` objects (like `CurrentExpression`) execute correctly.

## Preparing for Public Release

Beyond implementing the core components, a production-quality backend intended for public release should meet the following standards to ensure quality, compatibility, and maintainability:

*   **Comprehensive Backend Testing**: The backend must have its own robust test suite covering all aspects mentioned in the "Testing Requirements" section. This is the first line of defense for quality.
*   **Testsuite Compliance**: The backend must integrate with and pass the official `rhosocial-activerecord-testsuite`. This is a mandatory step to guarantee compatibility with the ActiveRecord core and other ecosystem components.
*   **Continuous Integration (CI)**: It is highly recommended to set up a CI pipeline for automated testing across different Python versions and environments. You can refer to the workflow files in the main project's `.github/workflows/` directory for a working example of how to configure this.

## Checklist for New Backends

This checklist summarizes all the required and recommended steps for creating a high-quality backend.

### Required Implementation
- [ ] Implement all `StorageBackend` abstract methods (`connect`, `disconnect`, `ping`, `get_server_version`, `introspect_and_adapt`, etc.).
- [ ] Provide a `Connection Configuration` class.
- [ ] Implement a `SQL Dialect` for syntax differences.
- [ ] Implement the full **Type Adaptation System**:
    - [ ] Create specific adapters where needed (`adapters.py`).
    - [ ] Register all adapters in `_register_my_adapters`.
    - [ ] Implement `get_default_adapter_suggestions` to define the conversion strategy.
- [ ] Implement `Transaction Management`.
- [ ] Implement `Error Handling` to map driver exceptions.
- [ ] Implement `Feature Detection` to declare capabilities.
- [ ] If providing an `AsyncStorageBackend`, ensure it has **Functional Equivalence** with the sync version.

### Required Tests
- [ ] Comprehensive tests for every item in the **Testing Requirements** section above.

### Release Readiness
- [ ] All backend-specific tests are passing.
- [ ] The backend is fully compliant with the official `rhosocial-activerecord-testsuite`.
- [ ] A **Continuous Integration (CI)** pipeline is set up for automated testing.
