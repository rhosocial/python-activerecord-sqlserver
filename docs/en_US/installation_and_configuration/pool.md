# Connection Management

## Overview

Both `SQLServerBackend` (synchronous) and `AsyncSQLServerBackend` (asynchronous) maintain a **single persistent connection** per backend instance. The `pool_size` and `pool_timeout` configuration fields are recognised by the config class but are **not yet consumed** by either backend — they are reserved for a future connection-pool implementation.

> 💡 **AI Prompt:** "My FastAPI application uses `AsyncSQLServerBackend`. How should I manage the database connection lifecycle to avoid connection leaks or stale connections?"

---

## Current Behaviour

### Synchronous Backend (`SQLServerBackend`)

`SQLServerBackend.connect()` calls `pyodbc.connect()` with the built ODBC connection string. The `pool_size` and `pool_timeout` fields are silently skipped.

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig

config = SQLServerConnectionConfig(
    host="localhost",
    port=1433,
    database="myapp",
    username="sa",
    password="secret",
    pool_size=10,      # ← accepted by config, ignored by backend
)
backend = SQLServerBackend(connection_config=config)
backend.connect()     # opens one persistent connection
```

### Asynchronous Backend (`AsyncSQLServerBackend`)

`AsyncSQLServerBackend.connect()` calls `aioodbc.connect()` with the same connection string. Pool-related kwargs are also skipped, so a single connection object is stored in `self._connection`.

```python
import asyncio
from rhosocial.activerecord.backend.impl.sqlserver import (
    AsyncSQLServerBackend, SQLServerConnectionConfig,
)

config = SQLServerConnectionConfig(
    host="localhost",
    port=1433,
    database="myapp",
    username="sa",
    password="secret",
)

async def main():
    backend = AsyncSQLServerBackend(connection_config=config)
    await backend.connect()     # opens one persistent async connection
    # ... use the backend ...
    await backend.disconnect()

asyncio.run(main())
```

---

## Connection Lifecycle Guidelines

### One Backend Per Process

Configure your models once at application startup (not inside request handlers). Each call to `Model.configure(config, backend_class)` creates a new backend instance and a new underlying connection.

```python
# application startup (e.g., FastAPI lifespan)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from rhosocial.activerecord.backend.impl.sqlserver import (
    AsyncSQLServerBackend, SQLServerConnectionConfig,
)
from myapp.models import User, Order

_config = SQLServerConnectionConfig(
    host="db.prod.internal",
    port=1433,
    database="myapp",
    username="sa",
    password="secret",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: configure once, connect once
    User.configure(_config, AsyncSQLServerBackend)
    Order.configure(_config, AsyncSQLServerBackend)
    await User.backend().connect()
    await Order.backend().connect()
    yield
    # Shutdown: disconnect cleanly
    await User.backend().disconnect()
    await Order.backend().disconnect()

app = FastAPI(lifespan=lifespan)
```

### Do NOT Configure Inside Request Handlers

```python
# ❌ Anti-pattern — creates a new connection on every request
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    User.configure(_config, AsyncSQLServerBackend)   # ← wrong
    await User.backend().connect()
    user = await User.find(user_id)
    await User.backend().disconnect()
    return user

# ✅ Correct — connection already open from lifespan
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return await User.find(user_id)
```

---

## Connection Timeout Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `int` | `30` | Seconds before a connection attempt is abandoned |
| `query_timeout` | `int` | `0` | Seconds before a query times out (0 = no limit) |

```python
config = SQLServerConnectionConfig(
    host="localhost",
    port=1433,
    database="myapp",
    username="sa",
    password="secret",
    timeout=5,
    query_timeout=30,
)
```

---

## Reserved Pool Configuration Fields

These fields are parsed by `SQLServerConnectionConfig` and stored on the config object, but are currently **not forwarded** to the underlying driver:

| Field | Type | Default | Reserved Purpose |
|-------|------|---------|-----------------|
| `pool_size` | `int` | `5` | Number of connections in the pool |
| `pool_timeout` | `int` | `30` | Seconds to wait for a free connection |

---

## See Also

- [Connection Configuration](configuration.md) — full list of `SQLServerConnectionConfig` options
- [Troubleshooting: Connection Issues](../troubleshooting/connection.md) — diagnosing connection errors
