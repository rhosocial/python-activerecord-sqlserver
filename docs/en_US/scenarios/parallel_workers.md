# Parallel Workers: Best Practices (SQL Server)

In data processing, task queues, and bulk import scenarios, developers often run multiple workers in parallel to improve throughput. This chapter focuses on parallel worker patterns for SQL Server.

For general patterns (multi-process lifecycle, async behavior, deadlock prevention principles, application separation), see [Core Parallel Worker Patterns](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/scenarios/parallel_workers.md).

> **Design principle throughout this chapter**: The synchronous `ActiveRecord` and asynchronous `AsyncActiveRecord` have **identical method names** — `configure()`, `backend()`, `transaction()`, `save()`, and so on. The async version simply requires `await` or `async with`.

## 1. SQL Server Concurrency Overview

SQL Server differs fundamentally from SQLite in how it handles concurrency:

| Feature | SQLite | SQL Server |
| --- | --- | --- |
| Lock granularity | File-level lock | Row-level lock |
| Concurrent writes | Serialized | Supported by default (different rows write simultaneously) |
| Async driver | `aiosqlite` (thread-pool) | `aioodbc` (async wrapper over pyodbc) |
| Deadlock handling | Timeout wait | Detection (error 1205), one victim rolled back |
| Connection type | File path | TCP network connection (host:port) |

### The Immutability of the Single-Connection Model

Regardless of SQL Server's concurrency advantages, **a single `ActiveRecord` class's `__backend__` remains a single connection**. In a multi-threaded environment, concurrent access to the same `__backend__` corrupts cursor state. pyodbc connections do not support concurrent multi-threaded use.

> **Do not share an ActiveRecord configuration across multiple threads.** Multi-process is the correct choice for parallel worker scenarios.

## 2. Multi-process: The Recommended Approach

Multi-process is the recommended approach for parallel worker scenarios. Each process has its own isolated memory space; `configure()` executes independently within each process, establishing a separate TCP connection.

**Sync (multiprocessing)**:

```python
import multiprocessing
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig
from models import Comment, Post, User

def worker(post_ids: list[int]):
    # 1. After the process starts, configure the connection inside the process.
    config = SQLServerConnectionConfig(
        host="localhost", port=1433, database="mydb",
        username="sa", password="secret",
        trust_server_certificate=True, autocommit=True,
    )
    User.configure(config, SQLServerBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    try:
        for post_id in post_ids:
            post = Post.find_one(post_id)
            if post is None:
                continue
            post.view_count = 1 + len([c for c in post.comments() if c.is_approved])
            post.save()
    finally:
        # 2. Disconnect before the process exits
        User.backend().disconnect()


if __name__ == "__main__":
    post_ids = list(range(1, 101))
    chunk_size = 25
    with multiprocessing.Pool(processes=4) as pool:
        chunks = [post_ids[i:i+chunk_size] for i in range(0, len(post_ids), chunk_size)]
        pool.map(worker, chunks)
```

**Key rules**:

- `configure()` must be called inside the child process, never before `fork`
- SQL Server connections are TCP connections; inheriting file descriptors after `fork` is dangerous
- Within a single process, async coroutines naturally access the database serially

## 3. Deadlocks: SQL Server Detection and Retry

SQL Server automatically detects deadlocks. When a deadlock is detected, one transaction is chosen as the **deadlock victim** and rolled back with error **1205**, allowing the other to continue. The victim receives `DeadlockError`.

### 3.1 Root Cause: Inconsistent Row Lock Order

```python
# ❌ Wrong: Different workers lock rows in opposite order
def worker_a():
    with Post.transaction():
        post1 = Post.find_one(1)  # locks id=1 first
        post2 = Post.find_one(2)  # requests id=2 (B holds it) → deadlock
```

### 3.2 Prevention: Consistent Lock Order

```python
# ✅ Correct: Always lock resources in ascending primary key order
def transfer_safe(from_id: int, to_id: int, amount: float):
    first_id, second_id = min(from_id, to_id), max(from_id, to_id)
    with Account.transaction():
        first  = Account.find_one(first_id)
        second = Account.find_one(second_id)
        debit, credit = (first, second) if from_id < to_id else (second, first)
        debit.balance  -= amount
        credit.balance += amount
        debit.save()
        credit.save()
```

### 3.3 SQL Server-Specific: Catch Deadlock and Retry

SQL Server exposes `set_deadlock_priority()` to influence which transaction becomes the victim:

```python
# Lower priority transactions become the victim first
backend.transaction_manager.set_deadlock_priority("LOW")   # LOW, NORMAL, HIGH, or -10..10
```

The recommended production pattern is to **catch error 1205 and retry**:

```python
import time
from rhosocial.activerecord.backend.errors import DeadlockError

def _is_deadlock(exc: Exception) -> bool:
    return isinstance(exc, DeadlockError)  # error 1205 in SQL Server

def claim_posts_with_retry(batch_size: int = 5, max_retry: int = 3) -> list:
    for attempt in range(max_retry):
        try:
            with Post.transaction():
                pending = (
                    Post.query()
                        .where(Post.c.status == "draft")
                        .order_by(Post.c.id)
                        .top(batch_size)      # TOP n instead of LIMIT
                        .all()
                )
                if not pending:
                    return []
                for post in pending:
                    post.status = "processing"
                    post.save()
                return pending
        except DeadlockError:
            if attempt < max_retry - 1:
                time.sleep(0.05 * (attempt + 1))  # exponential back-off
                continue
            raise
    return []
```

### 3.4 Five Prevention Principles

| Principle | Description |
| --- | --- |
| **Data partitioning** | Assign data by ID range or hash so workers never touch the same rows |
| **Consistent lock order** | Always request locks in a fixed order (e.g., ascending primary key) |
| **Short transactions** | Keep only necessary operations in a transaction |
| **Atomic claim** | Query and update task status inside one transaction |
| **Deadlock retry** | Catch `DeadlockError` (error 1205) and retry with back-off |

> **SQL Server vs MySQL**: MySQL uses `innodb_lock_wait_timeout` and errno 1213. SQL Server uses error 1205 for deadlock detection and `SET LOCK_TIMEOUT` (milliseconds) for lock-wait timeouts.

## 4. Example Code

The complete runnable examples for this chapter are in the `docs/examples/chapter_08_scenarios/parallel_workers/` directory of the MySQL backend docs, adapted for SQL Server.

## 5. Conclusion

1. **Multiprocessing is the correct approach for parallel workers**
2. **Deadlock retry recommended for production** — does not rely on data partitionability
3. **Data partitioning is most efficient** — no lock contention
4. **Use `set_deadlock_priority()`** to control which transactions are sacrificed in a deadlock
