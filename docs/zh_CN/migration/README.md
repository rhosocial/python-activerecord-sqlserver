# SQL Server 上的迁移

> 📖 **范围**：本页**仅介绍在本后端上运行 ActiveRecord 迁移时特有的内容** —— 配置 SQL Server（pyodbc）后端、事务性 DDL 行为、版本门控，以及两种编写 API 如何接入本后端的 CLI。
>
> 迁移**系统本身** —— 两套 API、术语、排序与依赖校验、版本记录、试运行的 SQL 捕获、异常层级以及核心的 `migrate` CLI —— 属于[核心库迁移章节](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md)。此处**不再重复**。如果你刚接触迁移，请先阅读该章节。
>
> 本页及[docs/examples/migration/](../../examples/migration/README.md)中的所有示例均使用 SQL Server。

目录：

1. [配置后端](#1-configuring-the-backend)
2. [SQL Server 上的事务性 DDL](#2-transactional-ddl-on-sql-server)
3. [版本门控的特性与类型](#3-version-gated-features-and-types)
4. [函数式迁移（run_migration_group）](#4-function-style-migrations-run_migration_group)
5. [类式迁移与 named-migration CLI](#5-class-style-migrations-and-the-named-migration-cli)
6. [本地示例](#6-local-examples)

> 💡 **AI 提示词：** "我有一个由 `@migration` 装饰的函数。请演示如何针对 SQL Server 先以试运行（dry run）方式执行它，再真正执行它，但不要重复讲解迁移系统的工作原理。"

<a id="1-configuring-the-backend"></a>

## 1. 配置后端

迁移与任何其他操作使用相同的后端和连接配置。构造 `SQLServerConnectionConfig`，将其传给 `SQLServerBackend`，建立连接，并刷新检测到的服务器版本：

```python
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

config = SQLServerConnectionConfig(
    host="localhost",
    port=1433,
    database="myapp",
    username="sa",
    password="...",            # or trusted_connection=True
    driver="ODBC Driver 18 for SQL Server",
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()   # refresh the detected version before any version gate
```

本后端特有的要点：

- 同步路径通过 `SQLServerBackend` 使用 `pyodbc`；异步路径通过 `AsyncSQLServerBackend` 使用 `aioodbc`，并配合 `run_migration_group_async()`。完整的配置接口（包括 Windows 身份验证、ODBC 驱动与 TLS）见[连接配置](../../en_US/installation/configuration.md)。
- 不要硬编码凭据。示例从 `SQLSERVER_*` 环境变量读取连接信息；CLI 则支持 `--named-connection` 来达到同样目的。
- 在应用代码中渲染受版本门控的 DDL 之前，先调用 `backend.introspect_and_adapt()`。门控依据的是*检测到的*服务器版本，版本过时会导致门控按错误的版本底线作答。本后端的 CLI 在进入时会执行该调用；脚本必须自行调用。
- 连接的 `autocommit` 设置保持默认值即可。迁移组的事务边界由 `transaction_mode` 决定（见下一节），而非连接级别的标志。

<a id="2-transactional-ddl-on-sql-server"></a>

## 2. SQL Server 上的事务性 DDL

**SQL Server 通常支持事务性 DDL。** 普通的模式语句 —— `CREATE TABLE`、`ALTER TABLE`、`DROP TABLE`、`CREATE INDEX` 等 —— 都会参与用户事务，并在事务回滚时一并回滚。因此，迁移组默认的 `TransactionMode.AUTO` 在本后端上提供原子性的组：中途失败不会应用任何内容，也不会写入版本记录。SQL Server 方言没有 `supports_transactional_ddl()` 覆盖实现，因此运行器报告 DDL 为事务性（默认值），这与上述行为一致。

编写迁移时需要注意的几点：

- **并非所有语句都能出现在显式事务中。** 服务器级与数据库级操作，例如 `CREATE DATABASE`、`DROP DATABASE`、`RESTORE DATABASE` 以及若干 `DBCC` 命令，在事务中会被拒绝。请勿将此类语句放入迁移组，或显式地在事务之外执行它们；不要以为"DDL 是事务性的"就能让每条 `CREATE ...` 都安全。
- **耗时较长的 DDL 会持有锁。** 迁移可能因等待排他架构锁而阻塞。请通过连接配置中的 `query_timeout` 限定运行时长（默认值 `0` 表示无限制），而不要依赖客户端超时。
- **`SNAPSHOT` 不会自动生效。** 如果为迁移事务选择快照隔离，数据库必须已经启用 `ALLOW_SNAPSHOT_ISOLATION ON`；本后端不会替你修改该设置。隔离级别映射、保存点与死锁重试见[事务](../../en_US/transactions/README.md)。

`TransactionMode.AUTO` / `STEP` / `NONE` 的含义、版本记录的写入以及失败元数据（`transactional_ddl`、`executed` 等）均在核心章节中说明；本页只陈述这些模式在本后端上的*实际效果*。

<a id="3-version-gated-features-and-types"></a>

## 3. 版本门控的特性与类型

方言通过 `supports_*` 探测和 `version_at_least(...)` 回答能力问题，版本底线常量位于 `mixins/version_constants.py`。以下是常见的影响 DDL 的版本底线：

- 序列（sequence）—— 2012（`SQL_SERVER_2012`）
- JSON 函数 / `supports_json_type()` —— 2016（`SQL_SERVER_2016`）
- 时态表（temporal table）/ `supports_system_versioning()` —— 2016
- SQL Graph（node/edge 表）/ `supports_sql_graph()` —— 2017（`SQL_SERVER_2017`）
- 图最短路径 —— 2019（`SQL_SERVER_2019`）
- 列存储索引上的 `ORDER (...)` —— 2022（`SQL_SERVER_2022`）

在生成受版本门控的 DDL **之前**先检查门控；门控关闭意味着表达式不会渲染（或抛出 `UnsupportedFeatureError`，由迁移层转换为 `MigrationDialectError`）：

```python
from rhosocial.activerecord.backend.impl.sqlserver.mixins.version_constants import SQL_SERVER_2016

backend.introspect_and_adapt()
dialect = backend.dialect

if dialect.supports_system_versioning() and dialect.version_at_least(SQL_SERVER_2016):
    ...  # safe to emit version-gated DDL
else:
    ...  # take a deliberate fallback, or fail deliberately
```

请注意，门控回答的是"能否向*服务器*提出该问题"，而不是当前登录名是否拥有相应权限。完整的版本底线表以及"门控关闭、版本底线、永久不支持的语句"之间的区别，见[能力门控](../../en_US/capabilities/README.md)。

<a id="4-function-style-migrations-run_migration_group"></a>

## 4. 函数式迁移（run_migration_group）

新工作应使用函数式 API。本后端只提供连接与方言；装饰器、组运行器、记录存储、排序规则和试运行语义全部是核心特性，详见[核心迁移章节](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md)。

SQL Server 上的最小形态如下：

```python
@migration("v001_create_users", description="create the initial users table")
def create_users(ctx):
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(User.create_table_statement(backend=ctx.backend))
    else:
        ctx.apply(User.drop_table_statement(if_exists=True, backend=ctx.backend))


backend = SQLServerBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()

# dry run — renders T-SQL through this backend's dialect, writes nothing
preview = run_migration_group(backend, [f"{__name__}:create_users"], dry_run=True)
print(preview.dry_run_sql, preview.dry_run_total)

# real run — applies the DDL inside a transaction and writes a version record
result = run_migration_group(backend, [f"{__name__}:create_users"], record_store=store)
```

由于 DDL 由本后端的方言渲染，你检查的试运行 SQL 就是即将执行的真实 T-SQL —— 包括带 `[方括号]` 的标识符、`IDENTITY(1,1)` 以及该服务器的类型写法。本后端没有专用的试运行标志；`dry_run=True` 与核心章节所述的选项完全一致。

完整且通过语法检查的脚本见 [`01_function_migration.py`](../../examples/migration/01_function_migration.py)。

<a id="5-class-style-migrations-and-the-named-migration-cli"></a>

## 5. 类式迁移与 named-migration CLI

类式（`NamedMigration`）路径为兼容旧版而保留。本后端通过 [`cli/named_migration.py`](../../../src/rhosocial/activerecord/backend/impl/sqlserver/cli/named_migration.py) 将其接入自身 CLI：该子命令使用共享的连接参数构造 `SQLServerBackend`，并在委托给核心的 `handle_named_migration` 之前调用 `introspect_and_adapt()`。

```bash
python -m rhosocial.activerecord.backend.impl.sqlserver named-migration \
    myapp.migrations.v001.CreateUsersTable \
    --host localhost --database myapp --user sa --password '...' \
    --direction up --record-store ./migrations.json --dry-run
```

该解析器接受以点分隔的 `module.Class` 限定名（不是函数 API 使用的 `module:function` 形式），以及 `--direction up|down`、`--record-store`、`--dry-run`、`--describe`、`--list`、`--param KEY=VALUE`、`--all`、`--single-transaction` 和 `--async`。连接信息也可以来自 `--named-connection`。`--single-transaction` 会将整批操作包在一个事务中，并只在最终提交后写入记录 —— 鉴于 SQL Server 可以回滚普通 DDL，这个选项在该场景下很有用。

这里有两条值得重申的接线规则：

- 将 `NamedMigration` 类的 FQN 传给*函数式* API（`run_migration_group` 或核心的 `migrate` CLI）会报错，并提示改用本后端的 `named-migration` 命令。请依据[核心对比表](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md#1-two-apis-two-entry-points)选择对应的 API。
- 对于 `MigrationRunner`（类式 API），`dry_run_sql` 仅由命名表达式回调组装；函数式运行器则能捕获两条语句路径。这是核心层面的注意事项，此处再次提示，以免在选择 API 时遗漏。

完整的类式演示见 [`02_named_migration.py`](../../examples/migration/02_named_migration.py)。

<a id="6-local-examples"></a>

## 6. 本地示例

| 脚本 | 演示内容 |
|---|---|
| [`01_function_migration.py`](../../examples/migration/01_function_migration.py) | SQL Server 配置 + `@migration` + `run_migration_group`：试运行 → 真正执行 UP → 回滚 DOWN，并使用 `JSONFileMigrationRecordStore` |
| [`02_named_migration.py`](../../examples/migration/02_named_migration.py) | 由 `MigrationRunner` 在 SQL Server 上驱动 `NamedMigration` 子类，以及 `named-migration` CLI 接线方式 |

这些脚本已通过语法检查，但执行时需要可连接的 SQL Server；连接所需的环境变量见 [docs/examples/README.md](../../examples/README.md)。
