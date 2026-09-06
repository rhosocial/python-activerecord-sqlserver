# 连接管理

## 概述

`SQLServerBackend`（同步）和 `AsyncSQLServerBackend`（异步）都为每个后端实例维护**一个持久连接**。`pool_size` 和 `pool_timeout` 配置字段会被配置类识别，但**目前尚未被任一后端使用**——它们是为未来的连接池实现预留的。

> 💡 **AI 提示词：** "我的 FastAPI 应用使用 `AsyncSQLServerBackend`。我应该如何管理数据库连接生命周期以避免连接泄漏或过期连接？"

---

## 当前行为

### 同步后端（`SQLServerBackend`）

`SQLServerBackend.connect()` 使用构建的 ODBC 连接字符串调用 `pyodbc.connect()`。`pool_size` 和 `pool_timeout` 字段会被静默跳过。

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig

config = SQLServerConnectionConfig(
    host="localhost",
    port=1433,
    database="myapp",
    username="sa",
    password="secret",
    pool_size=10,      # ← 配置接受，后端忽略
)
backend = SQLServerBackend(connection_config=config)
backend.connect()     # 打开一个持久连接
```

### 异步后端（`AsyncSQLServerBackend`）

`AsyncSQLServerBackend.connect()` 使用相同的连接字符串调用 `aioodbc.connect()`。连接池相关的 kwargs 也会被跳过，因此会在 `self._connection` 中存储单个连接对象。

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
    await backend.connect()     # 打开一个持久异步连接
    # ... 使用后端 ...
    await backend.disconnect()

asyncio.run(main())
```

---

## 连接生命周期指南

### 每个进程一个后端

在应用程序启动时配置模型一次（不要在请求处理器内配置）。每次调用 `Model.configure(config, backend_class)` 都会创建新的后端实例和新的底层连接。

```python
# 应用程序启动（例如 FastAPI lifespan）
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
    # 启动：配置一次，连接一次
    User.configure(_config, AsyncSQLServerBackend)
    Order.configure(_config, AsyncSQLServerBackend)
    await User.backend().connect()
    await Order.backend().connect()
    yield
    # 关闭：干净地断开连接
    await User.backend().disconnect()
    await Order.backend().disconnect()

app = FastAPI(lifespan=lifespan)
```

### 不要在请求处理器内配置

```python
# ❌ 反模式——每次请求都创建新连接
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    User.configure(_config, AsyncSQLServerBackend)   # ← 错误
    await User.backend().connect()
    user = await User.find(user_id)
    await User.backend().disconnect()
    return user

# ✅ 正确——连接已在 lifespan 中打开
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return await User.find(user_id)
```

---

## 连接超时配置

| 参数 | 类型 | 默认值 | 描述 |
|-----------|------|---------|-------------|
| `timeout` | `int` | `30` | 连接尝试被放弃前的秒数 |
| `query_timeout` | `int` | `0` | 查询超时秒数（0 = 无限制） |

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

## 预留的连接池配置字段

这些字段会被 `SQLServerConnectionConfig` 解析并存储在配置对象上，但目前**不会转发**给底层驱动：

| 字段 | 类型 | 默认值 | 预留用途 |
|-------|------|---------|-----------------|
| `pool_size` | `int` | `5` | 连接池中的连接数 |
| `pool_timeout` | `int` | `30` | 等待空闲连接的秒数 |

---

## 另请参阅

- [连接配置](configuration.md) — `SQLServerConnectionConfig` 选项的完整列表
- [故障排查：连接问题](../troubleshooting/connection.md) — 诊断连接错误
