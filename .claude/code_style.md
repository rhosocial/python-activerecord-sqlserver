# Code Style and Conventions

## Overview

This document defines the coding standards and conventions for the rhosocial-activerecord project. All contributions must follow these guidelines to maintain consistency and quality.

## Python Version and Standards

### Target Python Version
- **Minimum**: Python 3.8
- **Type Hints**: Use Python 3.8+ compatible syntax
- **Features**: Avoid features only available in Python 3.9+ unless conditionally imported

### PEP Compliance
- **PEP 8**: Follow with modifications noted below
- **PEP 440**: Version numbering format
- **PEP 484**: Type hints
- **PEP 526**: Variable annotations

## Code Formatting

### Tools Configuration

```toml
# pyproject.toml settings
[tool.black]
line-length = 100
target-version = ["py38"]
include = '\.pyi?$'

[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 100

[tool.ruff]
line-length = 100
target-version = "py38"
select = ["E", "F", "B"]
```

### Import Organization

```python
# Standard library imports
import os
import sys
from typing import Any, Dict, List, Optional

# Third-party imports (minimal - primarily Pydantic)
import pytest  # Only in tests
from pydantic import BaseModel, Field

# Note: No ORM imports (no SQLAlchemy, Django ORM, etc.)
# This project is a standalone implementation

# Local application imports
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend import StorageBackend

# Relative imports (within same package)
from .base import BaseActiveRecord
from ..interface import IActiveRecord
```

### Line Length and Wrapping

- Maximum line length: 100 characters
- Wrap long lines using parentheses:

```python
result = (
    very_long_function_name(
        argument_one, argument_two,
        argument_three, argument_four
    )
    .chain_method()
    .another_method()
)
```

## Naming Conventions

### General Rules

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `ActiveRecord`, `StorageBackend` |
| Functions | snake_case | `find_by_id`, `save_record` |
| Variables | snake_case | `user_name`, `is_valid` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Private | Leading underscore | `_internal_method`, `_private_var` |
| Protected | Single underscore | `_protected_method` |
| Magic | Double underscore | `__table_name__`, `__primary_key__` |

### Sync/Async Function Signature Naming Rules

**CRITICAL**: For functions that need to distinguish between synchronous and asynchronous versions (e.g., I/O operations), the naming convention is strictly defined:

1. **Method names must be IDENTICAL** - No `_async` suffix or similar distinctions
2. **Only the `async`/`await` keywords differ** - Everything else in the signature must match
3. **This applies to**: 
   - Method names
   - Parameter names and types
   - Return type annotations (except `async` methods return `Coroutine`)

```python
# CORRECT: Sync/Async methods with identical names
class StorageBackend:
    def connect(self) -> None:
        """Establish connection to database."""
        pass
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> QueryResult:
        """Execute a SQL query."""
        pass

class AsyncStorageBackend:
    async def connect(self) -> None:
        """Establish connection to database asynchronously."""
        pass
    
    async def execute(self, sql: str, params: Optional[Tuple] = None) -> QueryResult:
        """Execute a SQL query asynchronously."""
        pass

# WRONG: Do NOT use _async suffix
class BadExample:
    async def connect_async(self):  # ❌ WRONG
        pass
    
    async def execute_async(self, sql: str):  # ❌ WRONG
        pass
```

**Rationale**: This convention ensures that sync and async APIs are strictly equivalent, making it easier for users to switch between them without learning different method names. The only difference users need to be aware of is the `async`/`await` keywords.

### Special Naming Patterns

```python
# Type variables
T = TypeVar('T')
ModelT = TypeVar('ModelT', bound='IActiveRecord')

# Query-related names
# Use placeholder expressions for where clauses
User.where("age >= ?", (18,)) # age >= 18
User.where("name LIKE ?", ('%john%',))  # name LIKE '%john%'

# Class attributes
class User(ActiveRecord):
    __table_name__ = "users"  # Magic attribute
    __primary_key__ = "id"     # Magic attribute
    _relations = {}            # Protected class attribute
    
# Instance attributes
self._dirty_fields = set()    # Protected instance attribute
self._is_from_db = False      # Protected flag
```

## Type Annotations

### Basic Types

```python
from typing import Any, Dict, List, Optional, Union, Tuple, Set

def process_data(
    data: Dict[str, Any],
    fields: Optional[List[str]] = None,
    validate: bool = True
) -> Tuple[bool, Optional[str]]:
    """Process data with optional field filtering."""
    pass
```

### Generic Types

```python
from typing import TypeVar, Generic, Type

T = TypeVar('T')
ModelT = TypeVar('ModelT', bound='IActiveRecord')

class QueryBuilder(Generic[ModelT]):
    def __init__(self, model_class: Type[ModelT]) -> None:
        self.model_class = model_class
    
    def where(self, **conditions) -> 'QueryBuilder[ModelT]':
        return self
```

### Protocol Types

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Persistable(Protocol):
    def save(self) -> bool: ...
    def delete(self) -> bool: ...
    
def persist_object(obj: Persistable) -> None:
    obj.save()
```

## Documentation Standards

### Module Documentation

```python
# src/rhosocial/activerecord/backend/base.py
"""
Storage backend abstract base class.

This module defines the core interface that all database backends must implement.
It provides abstract methods for:
- Connection management
- CRUD operations
- Transaction handling
- Query execution
"""
```

### Class Documentation

```python
class StorageBackend(ABC):
    """Abstract base class for storage backends.
    
    This class defines the interface that all database backend implementations
    must follow. It provides abstract methods for database operations and
    connection management.
    
    Attributes:
        connection_config: Database connection configuration
        logger: Optional logger instance for debugging
        _connection: Internal database connection object
    
    Example:
        >>> backend = SQLiteBackend(config)
        >>> backend.connect()
        >>> result = backend.execute("SELECT * FROM users")
        >>> backend.disconnect()
    """
```

### Method Documentation

```python
def execute(
    self,
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    returning: bool = False
) -> QueryResult:
    """Execute a SQL query with optional parameters.
    
    Args:
        sql: SQL query string with placeholders
        params: Dictionary of parameter values
        returning: Whether to use RETURNING clause
    
    Returns:
        QueryResult containing affected rows and returned data
    
    Raises:
        DatabaseError: If query execution fails
        ValidationError: If parameters are invalid
        
    Example:
        >>> result = backend.execute(
        ...     "INSERT INTO users (name) VALUES (?)",
        ...     {"name": "John"}
        ... )
    """
```

## Code Organization

### File Structure

```python
# Standard file header
# src/rhosocial/activerecord/module/submodule.py
"""Module description."""

# Imports (grouped and sorted)
import standard_library
from typing import annotations

import third_party

from rhosocial.activerecord import local
from . import relative

# Constants
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# Type definitions
UserDict = Dict[str, Any]

# Classes (main content)
class MainClass:
    pass

# Functions
def utility_function():
    pass

# Module initialization (if needed)
__all__ = ['MainClass', 'utility_function']
```

#### Grouping Functionalities and File Splitting
- If a single file contains several functionalities and the file is not long, it is recommended to group and arrange these functionalities together, and add section comments (e.g., `# region ... # endregion`).
- If the file is too long, e.g., over 1000 lines, and a single group also exceeds 400 lines, it is recommended to split it into separate files under a directory package.

### Class Organization

```python
class ActiveRecord(BaseModel):
    """Class documentation."""
    
    # Class variables
    __table_name__: ClassVar[str]
    __primary_key__: ClassVar[str] = 'id'
    
    # Instance attributes (with type hints)
    _dirty_fields: Set[str]
    _original_values: Dict[str, Any]
    
    # Initialization
    def __init__(self, **data):
        super().__init__(**data)
        self._dirty_fields = set()
    
    # Properties
    @property
    def is_dirty(self) -> bool:
        return bool(self._dirty_fields)
    
    # Public methods
    def save(self) -> bool:
        pass
    
    # Protected methods
    def _validate(self) -> None:
        pass
    
    # Private methods
    def __track_change(self, field: str) -> None:
        pass
    
    # Class methods
    @classmethod
    def find(cls, id: Any) -> Optional['ActiveRecord']:
        pass
    
    # Static methods
    @staticmethod
    def generate_uuid() -> str:
        pass
    
    # Special methods
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id})"
```

## Error Handling

### Exception Design

```python
# Define specific exceptions
class DatabaseError(Exception):
    """Base exception for database operations."""
    pass

class RecordNotFound(DatabaseError):
    """Raised when a record cannot be found."""
    pass

# Use appropriate exception
def find_by_id(cls, id: Any) -> 'Model':
    result = cls.backend.fetch_one(...)
    if not result:
        raise RecordNotFound(f"No {cls.__name__} with id={id}")
    return cls(**result)
```

### Error Messages

```python
# Good: Specific and actionable
raise ValueError(f"Invalid age: {age}. Must be between 0 and 150.")

# Bad: Vague
raise ValueError("Invalid input")

# Include context
raise DatabaseError(
    f"Failed to connect to {config.database} at {config.host}:{config.port}"
)
```

## Testing Code Style

### Test Organization

```python
# tests/rhosocial/activerecord_test/module/test_feature.py
"""Test module for specific feature."""

import pytest
from rhosocial.activerecord import Model

# Fixtures at top
@pytest.fixture
def sample_model():
    return Model(name="test")

# Test classes for organization
class TestCRUDOperations:
    """Test CRUD functionality."""
    
    def test_create(self, sample_model):
        """Test record creation."""
        assert sample_model.save()
    
    def test_read(self, sample_model):
        """Test record retrieval."""
        pass

# Standalone tests for simple cases
def test_connection_timeout():
    """Test connection timeout handling."""
    pass
```

### Test Naming

```python
# Test method names should be descriptive
def test_save_with_valid_data_returns_true():
    pass

def test_save_with_invalid_email_raises_validation_error():
    pass

# Use parametrize for multiple scenarios
@pytest.mark.parametrize("age,expected", [
    (0, True),
    (150, True),
    (-1, False),
    (151, False),
])
def test_age_validation(age, expected):
    pass
```

## Comments and Code Clarity

### When to Comment

```python
# Good: Explain WHY, not WHAT
# Use version-specific feature only if available
if sys.version_info >= (3, 9):
    # dict merge operator available in Python 3.9+
    result = dict1 | dict2
else:
    result = {**dict1, **dict2}

# Good: Complex algorithm explanation
# Using binary search for performance with sorted data
# Time complexity: O(log n)
def find_in_sorted(items, target):
    pass

# Bad: Obvious comment
# Increment counter by 1
counter += 1
```

### Code Self-Documentation

```python
# Use descriptive names instead of comments
# Bad
d = (end - start).days  # days between dates

# Good
days_between_dates = (end_date - start_date).days

# Extract complex conditions
# Bad
if user.age >= 18 and user.country == "US" and user.verified:
    pass

# Good
is_eligible_us_adult = (
    user.age >= 18 
    and user.country == "US" 
    and user.verified
)
if is_eligible_us_adult:
    pass
```

## Performance Considerations

### Efficient Patterns

```python
# Use generators for large datasets
def process_records(cls):
    for record in cls.iterate():  # Generator
        yield process(record)

# Cache expensive computations
@property
def column_types(self):
    if self.__column_types_cache__ is None:
        self.__column_types_cache__ = self._compute_types()
    return self.__column_types_cache__

# Batch operations
def save_many(cls, records: List['Model']) -> int:
    # Single query instead of N queries
    return cls.backend.insert_many(records)
```

## Security Practices

### SQL Injection Prevention

```python
# Always use parameterized queries
# Good
backend.execute(
    "SELECT * FROM users WHERE id = ?",
    {"id": user_id}
)

# Bad - NEVER do this
backend.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### Sensitive Data

```python
# Never log sensitive information
def connect(self, password: str):
    # Bad
    logger.debug(f"Connecting with password: {password}")
    
    # Good
    logger.debug("Attempting database connection")
    
# Use __repr__ carefully
def __repr__(self):
    # Don't include sensitive fields
    return f"User(id={self.id}, username={self.username})"
    # Not: f"User(id={self.id}, password={self.password})"
```

## Common Patterns

### Builder Pattern

```python
class QueryBuilder:
    def where(self, **conditions) -> 'QueryBuilder':
        self.conditions.update(conditions)
        return self
    
    def order_by(self, field: str) -> 'QueryBuilder':
        self.order = field
        return self
    
    def limit(self, n: int) -> 'QueryBuilder':
        self.limit_value = n
        return self
```

### Context Managers

```python
@contextmanager
def transaction(backend: StorageBackend):
    """Database transaction context manager."""
    backend.begin()
    try:
        yield backend
        backend.commit()
    except Exception:
        backend.rollback()
        raise
```

### Mixin Classes

```python
class TimestampMixin:
    """Add timestamp fields to models."""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    def before_save(self):
        self.updated_at = datetime.now()
```

## Expression-Dialect System Coding Standards

### Expression Class Guidelines

1. **Proper Inheritance**:
   - All expression classes must inherit from `BaseExpression`
   - Value expressions inherit from `SQLValueExpression`
   - Predicate expressions inherit from `SQLPredicate`
   - Use appropriate mixins for functionality (e.g., `ArithmeticMixin`, `ComparisonMixin`)

2. **Protocol Implementation**:
   - Implement `ToSQLProtocol` with proper `to_sql()` method
   - Return `SQLQueryAndParams` type (SQL string and parameter tuple)
   - Never directly concatenate SQL strings in expression classes

3. **Dialect Delegation**:
   - Always delegate formatting to dialect methods
   - Use `self.dialect.format_*()` methods for all SQL formatting
   - Maintain separation between query structure and SQL generation

4. **Explicit Control**:
   - Expression classes should not maintain internal state
   - No hidden behaviors or automatic operations
   - Keep expressions stateless and pure
   - Unlike systems with complex object state management, our expressions are simple and predictable

### Dialect Class Guidelines

1. **Base Class Inheritance**:
   - All dialect classes must inherit from `SQLDialectBase`
   - Implement all required abstract methods

2. **Formatting Methods**:
   - Implement `format_*` methods for all SQL formatting needs
   - Handle identifier quoting appropriately
   - Properly handle parameter binding

3. **Database-Specific Logic**:
   - Include database-specific syntax variations
   - Handle version-specific features
   - Implement feature detection where needed

### Expression System Module Organization

Follow the established module structure:
- `bases.py`: Abstract base classes and protocols
- `core.py`: Core expressions (columns, literals, functions)
- `mixins.py`: Operator overloading capabilities
- `operators.py`: SQL operations
- `predicates.py`: Predicate expressions
- `query_parts.py`: Query clauses
- `statements.py`: DML/DDL statements
- `functions.py`: Factory functions
- `aggregates.py`: Aggregation expressions
- `advanced_functions.py`: Advanced SQL features
- `query_sources.py`: Data source expressions
- `graph.py`: Graph query expressions

### Example Expression Class

```python
from typing import TYPE_CHECKING
from . import bases, mixins

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import SQLDialectBase

class MyExpression(mixins.ArithmeticMixin, mixins.ComparisonMixin, bases.SQLValueExpression):
    """Represents a custom SQL expression."""
    def __init__(self, dialect: "SQLDialectBase", value: str):
        super().__init__(dialect)
        self.value = value

    def to_sql(self) -> 'bases.SQLQueryAndParams':
        # Delegate formatting to dialect
        formatted_value = self.dialect.format_string_literal(self.value)
        return formatted_value, (self.value,)
```

### Example Dialect Method

```python
def format_identifier(self, identifier: str) -> str:
    """Format identifier with proper quoting."""
    # Database-specific identifier formatting
    return f'"{identifier}"'  # Example for standard SQL
```

## Code Review Checklist

- [ ] Path comment at file start matches actual location
- [ ] All functions/classes have docstrings
- [ ] Type hints on all function signatures
- [ ] No line exceeds 100 characters
- [ ] Imports sorted and grouped correctly
- [ ] No commented-out code
- [ ] Exception messages are informative
- [ ] Test coverage for new code
- [ ] Security considerations addressed
- [ ] Performance implications considered
- [ ] Expression classes properly delegate to dialect
- [ ] Dialect methods handle formatting correctly
- [ ] Expression-dialect separation maintained
- [ ] Expression system module organization followed