# BackendGroup 和 BackendManager（SQL Server）

本文档介绍如何在 SQL Server 后端中使用 `BackendGroup` 和 `BackendManager`。有关详细的 API 文档，请参阅[核心库文档](../../../rhosocial-activerecord/docs/en_US/connection/connection_management.md)。

## 快速示例

```python
from rhosocial.activerecord.connection import BackendGroup
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    name: str
    email: str


# 使用上下文管理器
with BackendGroup(
    name="main",
    models=[User],
    config=SQLServerConnectionConfig(
        host="localhost",
        port=1433,
        database="myapp",
        username="sa",
        password="secret",
    ),
    backend_class=SQLServerBackend,
) as group:
    user = User(name="John", email="john@example.com")
    user.save()

# 通过 BackendManager 使用多个组
from rhosocial.activerecord.connection import BackendManager

manager = BackendManager()
manager.create_group(
    name="main",
    models=[User],
    config=SQLServerConnectionConfig(host="localhost", database="main_db", username="sa", password="secret"),
    backend_class=SQLServerBackend,
)
manager.create_group(
    name="stats",
    config=SQLServerConnectionConfig(host="localhost", database="stats_db", username="sa", password="secret"),
    backend_class=SQLServerBackend,
)

main_backend = manager.get_group("main").get_backend()
stats_backend = manager.get_group("stats").get_backend()
```

## SQL Server 特定功能

### 身份验证模式

SQL Server 支持两种身份验证模式：

```python
# Windows 身份验证
config = SQLServerConnectionConfig(
    host="localhost",
    database="myapp",
    trusted_connection=True,
)

# SQL Server 身份验证
config = SQLServerConnectionConfig(
    host="localhost",
    database="myapp",
    username="sa",
    password="secret",
)
```

### SSL/加密配置

```python
config = SQLServerConnectionConfig(
    host="sqlserver.example.com",
    port=1433,
    database="myapp",
    username="sa",
    password="secret",
    encrypt=True,
    trust_server_certificate=False,
)
```

### 连接字符串

配置会自动构建 ODBC 连接字符串：

```python
conn_str = config.build_connection_string()
# DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=myapp;UID=sa;PWD=secret;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30
```

## 另请参阅

- [连接配置](configuration.md) — `SQLServerConnectionConfig` 选项的完整列表
- [连接管理](pool.md) — 单连接生命周期和连接池
