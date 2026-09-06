# Auto-Retry and Deadlock Handling

## Overview

A SQL Server deadlock is a situation where two or more transactions are waiting for each other to release locks. SQL Server automatically detects deadlocks, selects one transaction as the **deadlock victim**, and rolls it back with error **1205**. The victim receives a `DeadlockError`.

## Deadlock Error Detection

The backend converts SQL Server error 1205 into a `DeadlockError`:

```python
from rhosocial.activerecord.backend.errors import DeadlockError
```

## Deadlock Handling Strategies

### 1. Using Transaction Retry Decorator

```python
from functools import wraps
import time
from rhosocial.activerecord.backend.errors import DeadlockError


def retry_on_deadlock(max_retries=3, delay=0.1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except DeadlockError as e:
                    last_exception = e
                    time.sleep(delay * (attempt + 1))
                    continue
            raise last_exception
        return wrapper
    return decorator


@retry_on_deadlock(max_retries=3)
def transfer_money(from_account, to_account, amount):
    with Account.transaction():
        # Debit and credit logic
        pass
```

### 2. Catching Deadlock Errors

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.errors import DeadlockError


backend = SQLServerBackend(
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    trust_server_certificate=True,
)
backend.connect()

try:
    with Account.transaction():
        first = Account.find_one(1)
        second = Account.find_one(2)
        # Transfer logic
except DeadlockError:
    print("Deadlock occurred, will retry")
    # Retry logic
finally:
    backend.disconnect()
```

## Deadlock Priority

Use `set_deadlock_priority()` to control which transaction becomes the victim when a deadlock occurs:

```python
# Low priority transactions are sacrificed first
backend.transaction_manager.set_deadlock_priority("LOW")     # LOW, NORMAL, HIGH
backend.transaction_manager.set_deadlock_priority(-5)         # or -10 to 10
```

## Lock Timeout

Set the lock-wait timeout for the current session (in milliseconds):

```python
# Wait at most 2000ms for a lock before erroring
backend.transaction_manager.set_lock_timeout(2000)
# -1 = wait indefinitely, 0 = do not wait
```

## Recommendations for Avoiding Deadlocks

1. **Access resources in a fixed order**: Always access tables and rows in the same order
2. **Use indexes whenever possible**: Reduce the number of rows locked
3. **Keep transactions small**: Reduce lock duration
4. **Use lower isolation levels when needed**: Use READ COMMITTED or READ UNCOMMITTED when appropriate
5. **Set deadlock priority**: Use LOW priority for background/batch tasks so user-facing transactions win

💡 *AI Prompt:* "What is a database deadlock? How is SQL Server's error 1205 deadlock victim selection different from MySQL's?"
