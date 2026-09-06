# 命令行界面

## 概述

每个 sqlserver 后端都包含一个用于数据库操作的命令行界面（CLI）。CLI 提供查询、内省和管理 SQL Server 数据库的命令，无需编写 Python 代码。

CLI 命令分为两类：

1. **后端特定命令** — SQL Server 独有操作（query、introspect、info、status）
2. **核心继承命令** — 所有后端共享（named-expression、named-procedure、named-migration、named-connection）

## 调用方式

安装包时 CLI 会注册为 `rhosocial-activerecord-sqlserver`：

```bash
pip install rhosocial-activerecord-sqlserver
```

然后直接调用命令：

```bash
rhosocial-activerecord-sqlserver <command> [options]
```

此命令在 `pyproject.toml` 中注册，等同于 `python -m rhosocial.activerecord.backend.impl.sqlserver`。

## 输出格式

CLI 通过 `-o` / `--output` 选项支持多种输出格式：

| 格式 | 描述 | 需要 Rich |
|------|------|----------|
| `table` | 带边框的人类可读表格（默认） | 是 |
| `json` | JSON 对象数组 | 否 |
| `csv` | 逗号分隔值 | 否 |
| `tsv` | 制表符分隔值 | 否 |

安装 Rich 时，`table` 格式提供带彩色边框的美化输出。未安装 Rich 时，CLI 自动回退到 `json` 格式。

### Rich 集成

CLI 与 [Rich](https://github.com/Textualize/rich) 库集成以增强终端输出：

- **彩色边框**：Unicode 绘图字符用于表格边框
- **ASCII 回退**：使用 `--rich-ascii` 强制 ASCII 边框（`+`、`-`、`|`）
- **自动检测**：如果未安装 Rich，自动回退到 JSON 输出

```bash
# 默认表格输出（Unicode 边框）
rhosocial-activerecord-sqlserver query ... "SELECT * FROM users"

# ASCII 边框（用于不支持 Unicode 的终端）
rhosocial-activerecord-sqlserver query ... --rich-ascii "SELECT * FROM users"

# 强制 JSON 输出
rhosocial-activerecord-sqlserver query ... -o json "SELECT * FROM users"
```

## 后端特定命令

这些命令由 sqlserver 后端实现，直接与 SQL Server 交互：

| 命令 | 描述 | 需要连接 |
|------|------|---------|
| `info` | 显示环境和协议信息 | 否 |
| `query` | 执行 SQL 查询 | 是 |
| `introspect` | 数据库内省（表、列、索引等） | 是 |
| `status` | 显示服务器状态和配置 | 是 |

### info

无需数据库连接即可显示环境信息：

```bash
rhosocial-activerecord-sqlserver info
```

### query

直接执行 SQL 查询：

```bash
rhosocial-activerecord-sqlserver query \
    --host localhost --port 1433 --database mydb \
    --user sa --password "YourStrong!Passw0rd" \
    "SELECT TOP 10 * FROM users"
```

### introspect

检查数据库元数据：

```bash
# 列出所有表
rhosocial-activerecord-sqlserver introspect tables \
    --host localhost --port 1433 --database mydb

# 描述特定表
rhosocial-activerecord-sqlserver introspect table users \
    --host localhost --port 1433 --database mydb

# 列出列
rhosocial-activerecord-sqlserver introspect columns users \
    --host localhost --port 1433 --database mydb
```

#### 内省类型

每个后端支持不同的内省类型：

| 类型 | 描述 |
|------|------|
| `tables` | 列出所有表 |
| `views` | 列出所有视图 |
| `table` | 描述特定表 |
| `columns` | 列出表的列 |
| `indexes` | 列出表的索引 |
| `foreign-keys` | 列出表的外键 |
| `triggers` | 列出触发器 |
| `database` | 数据库信息 |

SQL Server 特定类型：

| 额外类型 | 描述 |
|---------|------|
| `sequences` | 列出序列 |
| `procedures` | 列出存储过程 |
| `functions` | 列出用户定义函数 |

### status

显示服务器状态：

```bash
rhosocial-activerecord-sqlserver status \
    --host localhost --port 1433 --database mydb
```

## 核心继承命令

这些命令**从核心 `python-activerecord` 库继承**，在所有后端中工作方式完全相同：

### 为什么使用命名功能？

命名功能让你**将复杂配置编码为单个名称**，避免冗长的命令行参数，并启用无法通过 CLI 标志表达的参数组合。

**命名连接** — 封装所有连接参数：

```bash
# 不使用命名连接：长参数列表
rhosocial-activerecord-sqlserver query \
    --host prod-db.example.com --port 1433 --database myapp \
    --user readonly --password secret \
    --trusted-connection \
    "SELECT * FROM users"

# 使用命名连接：一个名称包含一切
rhosocial-activerecord-sqlserver query \
    --named-connection myapp.connections.prod_readonly \
    "SELECT * FROM users"
```

**命名表达式** — 封装复杂查询逻辑：

```bash
# 使用命名表达式：一个名称，类型安全参数
rhosocial-activerecord-sqlserver named-expression \
    myapp.queries.high_value_customers \
    --param since=2026-01-01 --param min_orders=5
```

**命名过程** — 封装多步工作流：

```bash
# 使用命名过程：一个命令，事务管理
rhosocial-activerecord-sqlserver named-procedure \
    myapp.workflows.place_order \
    --param user_id=42 --param product_id=100 --param quantity=3
```

**命名迁移** — 封装带依赖关系的版本化架构变更：

```bash
rhosocial-activerecord-sqlserver named-migration up add_users_table
rhosocial-activerecord-sqlserver named-migration down add_users_table
```

| 功能 | 优势 |
|------|------|
| 命名连接 | 将连接配置存储在可版本化的 Python 代码中；跨脚本共享 |
| 命名表达式 | 封装复杂 SQL；类型安全参数；跨工具重用 |
| 命名过程 | 带事务管理的多查询工作流；并行执行 |
| 命名迁移 | 带依赖跟踪的版本化架构变更；向上/向下支持 |

## 连接参数

所有需要数据库连接的命令接受以下通用参数：

| 参数 | 描述 |
|------|------|
| `--host` | 数据库服务器主机名 |
| `--port` | 数据库服务器端口（默认：1433） |
| `--database` | 数据库名称 |
| `--user` | 认证用户名 |
| `--password` | 认证密码 |
| `--async` | 使用异步后端 |
| `--named-connection` | 使用命名连接配置 |
| `--conn-param` | 附加连接参数 |
| `--log-level` | 设置日志级别（DEBUG、INFO、WARNING、ERROR） |

### SQL Server 特定连接参数

| 参数 | 描述 |
|------|------|
| `--trusted-connection` | 使用 Windows 身份验证（集成安全性） |
| `--driver` | ODBC 驱动名称（默认：ODBC Driver 17 for SQL Server） |
| `--encrypt` / `--no-encrypt` | 启用/禁用加密 |
| `--trust-server-certificate` | 信任服务器证书（跳过验证） |

## 全局选项

| 选项 | 描述 |
|------|------|
| `-h`, `--help` | 显示帮助消息并退出 |
| `--log-level` | 设置日志级别（DEBUG、INFO、WARNING、ERROR） |

## 另请参阅

- [安装指南](../installation_and_configuration/installation.md) — 设置说明
- [连接管理](../installation_and_configuration/pool.md) — 连接配置
- [核心命名功能](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US) — 命名连接、表达式、过程、迁移文档

💡 *AI 提示词：* "如何从命令行列出 SQL Server 数据库中的所有表？"
