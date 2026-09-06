# 与核心库的关系

## 架构概述

rhosocial-activerecord 采用模块化设计，核心库（`rhosocial-activerecord`）提供与数据库无关的 ActiveRecord 实现，而数据库后端作为独立的扩展包存在。

SQL Server 后端的命名空间位于 `rhosocial.activerecord.backend.impl.sqlserver`，与其他后端（如 `sqlite`、`mysql`、`dummy`）处于同一级别。这意味着：

- 后端不参与 ActiveRecord 层的变更
- 后端严格遵循后端接口协议
- 后端更新与核心库的 ActiveRecord 功能解耦

```
rhosocial.activerecord
├── backend.impl.sqlite    # SQLite 后端
├── backend.impl.dummy     # 用于测试的 Dummy 后端
├── backend.impl.mysql     # MySQL 后端
└── backend.impl.sqlserver # SQL Server 后端（本包）
    ├── SQLServerBackend
    ├── AsyncSQLServerBackend
    └── ...
```

## 后端职责

SQL Server 后端负责以下内容：

### 1. T-SQL 方言生成

将通用查询构建器转换为 SQL Server 特定的 SQL 语句：

```python
# 核心库：通用查询构建
query = User.query().where(User.c.age >= 18).order_by(User.c.created_at)

# SQL Server 后端：转换为 T-SQL
# SELECT * FROM [users] WHERE [age] >= ? ORDER BY [created_at]
```

方言处理的 SQL Server 差异：
- `TOP n` 代替 `LIMIT n`
- 方括号引用 `[column]` 代替反引号
- `?` 参数占位符（pyodbc 约定）
- `OUTPUT` 子句代替 `RETURNING`
- `OFFSET ... FETCH` 用于分页（SQL Server 2012+）

### 2. 数据类型映射

处理 SQL Server 特定的数据类型，包括：

- TINYINT, SMALLINT, INT, BIGINT
- FLOAT, REAL, DECIMAL, MONEY
- CHAR, VARCHAR, NCHAR, NVARCHAR, NVARCHAR(MAX)
- DATE, TIME, DATETIME, DATETIME2, DATETIMEOFFSET
- BINARY, VARBINARY, IMAGE
- UNIQUEIDENTIFIER, XML, HIERARCHYID
- 存储为 NVARCHAR(MAX) 的 JSON

### 3. 连接管理

通过 pyodbc 提供 SQL Server 连接的建立、断开等底层操作。

### 4. 事务控制

实现 SQL Server 的事务逻辑：`BEGIN/COMMIT/ROLLBACK TRANSACTION`、保存点和隔离级别。

## 快速开始

### 1. 安装

```bash
pip install rhosocial-activerecord
pip install rhosocial-activerecord-sqlserver
```

### 2. 定义模型

```python
import uuid
from typing import ClassVar
from pydantic import Field
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, DefaultTimestampMixin


class User(UUIDMixin, DefaultTimestampMixin, ActiveRecord):
    username: str = Field(..., max_length=50)
    email: str

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'users'
```

### 3. 配置后端

```python
from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)

# 配置 SQL Server 连接
config = SQLServerConnectionConfig(
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    trust_server_certificate=True,
)

# 为模型配置后端
User.configure(config, SQLServerBackend)
```

### 4. CRUD 操作

```python
# 创建
user = User(username='tom', email='tom@example.com')
user.save()

# 读取
user = User.query().where(User.c.username == 'tom').one()

# 更新
user.email = 'tom.new@example.com'
user.save()

# 删除
user.delete()
```

💡 *AI 提示词：* "什么是 ActiveRecord 模式？它有什么优缺点？"
