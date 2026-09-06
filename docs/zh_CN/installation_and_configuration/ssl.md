# SSL/TLS 配置

## 概述

SQL Server 在现代配置中默认加密连接。后端通过 `encrypt` 和 `trust_server_certificate` 选项控制连接加密行为。

## 基本用法

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

# 默认启用加密（encrypt=True）
backend = SQLServerBackend(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
)
backend.connect()
```

## SSL 配置参数

| 参数 | 类型 | 默认值 | 描述 |
|-----------|------|---------|-------------|
| encrypt | bool | True | 加密连接 |
| trust_server_certificate | bool | False | 信任服务器证书（跳过验证） |
| driver | str | ODBC Driver 17 for SQL Server | ODBC 驱动（17/18 驱动的加密默认值不同） |

## 自签名证书

对于使用自签名证书的开发环境，你必须信任服务器证书：

```python
config = SQLServerConnectionConfig(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    encrypt=True,
    trust_server_certificate=True,  # 仅限开发——禁用证书验证
)
backend = SQLServerBackend(connection_config=config)
```

⚠️ **警告**：`trust_server_certificate=True` 会禁用证书验证，**不建议用于生产环境**。当组合使用 `encrypt=True` 和 `trust_server_certificate=True` 时，配置类会发出 `UserWarning`。

## 生产环境最佳实践

对于生产环境，请使用受信任 CA 签发的证书并保持验证启用：

```python
config = SQLServerConnectionConfig(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    encrypt=True,               # 加密连接
    trust_server_certificate=False,  # 验证服务器证书
)
```

## 验证 SSL 连接

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

backend = SQLServerBackend(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    encrypt=True,
)
backend.connect()
print(f"已连接到: {backend.config.host}:{backend.config.port}")
backend.disconnect()
```

💡 *AI 提示词：* "SQL Server 连接中的 `encrypt` 和 `trust_server_certificate` 有什么区别？"
