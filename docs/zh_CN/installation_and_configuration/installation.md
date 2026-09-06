# 安装指南

## 系统要求

- Python 3.9+
- SQL Server 2016 及更高版本（参见[支持的版本](../introduction/supported_versions.md)）
- 用于 SQL Server 的 ODBC 驱动（例如 ODBC Driver 17/18）
- pip 或 poetry

## 安装步骤

### 1. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

### 2. 安装核心库和 SQL Server 后端

```bash
# 安装核心库
pip install rhosocial-activerecord

# 安装 SQL Server 后端
pip install rhosocial-activerecord-sqlserver
```

### 3. 安装异步支持（可选）

异步后端需要 `aioodbc`：

```bash
pip install rhosocial-activerecord-sqlserver[async]
# 或
pip install aioodbc
```

> **注意**：异步组件是惰性加载的。如果在没有安装 `aioodbc` 的情况下导入 `AsyncSQLServerBackend`，你将收到 `ImportError`。

### 4. 安装 ODBC 驱动

后端需要在系统上安装用于 SQL Server 的 ODBC 驱动：

```bash
# Ubuntu / Debian（Microsoft ODBC Driver 18）
curl https://packages.microsoft.com/keys/microsoft.asc | tee /etc/apt/trusted.gpg.d/microsoft.asc
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

## 验证安装

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

backend = SQLServerBackend(
    host='localhost',
    port=1433,
    database='test_db',
    username='sa',
    password='password',
    trust_server_certificate=True,
)
backend.connect()
print(f"SQL Server 版本: {backend.get_server_version()}")
backend.disconnect()
```

💡 *AI 提示词：* "什么是 ODBC？为什么访问 SQL Server 需要 ODBC 驱动？"
