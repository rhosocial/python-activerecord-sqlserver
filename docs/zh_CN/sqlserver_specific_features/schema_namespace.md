# docs/zh_CN/sqlserver_specific_features/schema_namespace.md

# SQL Server Schema 命名空间

> 本文只讲本后端特有的部分：`schema_name` 在这里指向什么、限定名如何渲染、列引用
> 为什么止于两段、取了表别名之后用什么去标识一个范围、不加限定的名字落在哪个 schema
> 上，以及分区与 schema DDL 各自怎么使用这个值。
>
> 模型层的通用部分——怎么在模型上声明 `__schema_name__`、schema 何时进入 SQL、
> DDL 的边界、各后端支持矩阵——由核心库（`python-activerecord` 仓库）的
> `docs/modeling/schema_namespace.md` 讲，见
> [`docs/zh_CN/modeling/schema_namespace.md`][core-zh]。

[core-zh]: https://github.com/rhosocial/python-activerecord/tree/main/docs/zh_CN/modeling/schema_namespace.md

## 本文结论的验证方式

文中每一段 SQL 都由 `SQLServerDialect(version=(16, 0, 0))` 配合表达式层渲染
得出，没有连接真实服务端：

```
PYTHONPATH=src .venv3.14-ubuntu26.04/bin/python
```

对应的核心库是 `fix/schema-name-propagation-gaps` 分支上的
`rhosocial-activerecord` 1.0.0.dev30。核心库这一项很关键：从 `main` 安装的
`python-activerecord` 早于下面描述的这套改写，DDL 与 DML 仍然接受裸的表名字符串，用它
渲染出来的片段与文中所写并不相同。

描述服务端而非渲染器的部分——错误号、`DEFAULT_SCHEMA` 的语义、`CREATE SCHEMA`
必须独占一个批处理、跨 database 的名字——来自 SQL Server 自身的行为，本仓库没有
在真实实例上验证过。凡属此类内容均在正文中标明；因缺少实例而无法确认的每一点，都在
所在位置写明未验证。

## `schema_name` 在这里指向什么

`SQLServerDialect` 实现了核心库的 `SchemaSupport` 协议，凡是核心库期待出现
`schema_name` 的地方都能接受。至于这个值**指向什么**，按 SQL Server 自己的定义
来：当前 database 里的一个 schema。一个 database 里可以同时存在多个 schema，
各自完整地拥有自己的对象——`[app].[orders]` 与 `[crm].[orders]` 是两张同名表，
一条带限定的引用只会走到其中一张。

schema 这一组能力标志并非全为 `True`：

```python
dialect.supports_schema()                # True
dialect.supports_create_schema()         # True
dialect.supports_drop_schema()           # True
dialect.supports_schema_authorization()  # True
dialect.supports_index_schema_qualification()  # True

dialect.supports_schema_if_not_exists()  # False
dialect.supports_schema_if_exists()      # False
dialect.supports_schema_cascade()        # False
```

后三个 `False` 说的是语句语法，不是命名空间能力：`IF NOT EXISTS`、`IF EXISTS`
与 `CASCADE` 这三种子句都不是 T-SQL 的写法，参见
[创建与删除 schema](#创建与删除-schema)。

`supports_index_schema_qualification()` 回答的是另一个问题——索引**名**能不能带命名
空间——SQL Server 答 `True`，因为它的 `CREATE INDEX` 接受带限定的索引名。语法上禁止
这一形式的方言答 `False`，并在渲染时抛 `UnsupportedFeatureError`。见
[索引各自选择命名空间](#索引各自选择命名空间)。

渲染用方括号，每一段各自成为一个带方括号的标识符：

| 表达式 | SQL |
|---|---|
| `TableExpression(d, "orders", schema_name="app")` | `[app].[orders]` |
| `TableExpression(d, "orders")` | `[orders]` |
| `TableExpression(d, "orders", schema_name="app", alias="o")` | `[app].[orders] AS [o]` |

### 加引号的方式

`format_identifier` 默认加方括号，并把值里自带的方括号写成两个，因此本该提前闭合
引用的字符仍留在同一个标识符内部：

```python
TableExpression(d, "orders", schema_name="app]x").to_sql()[0]
# [app]]x].[orders]

TableExpression(d, "orders", schema_name="My Schema").to_sql()[0]
# [My Schema].[orders]
```

schema 名里带空格不需要额外转义，保留字也和其他名字一样加方括号：

```python
TableExpression(d, "user", schema_name="dbo").to_sql()[0]
# [dbo].[user]
```

方括号原样保留名字；`[My Schema]` 与 `[my schema]` 是否指向同一个 schema，由
database 的排序规则决定，与框架无关。

值里写点号同样不构成分隔符——每一段各自加引号，点号留在段内，见
[常见错误](#常见错误)。

## 在模型上声明

```python
from typing import ClassVar, Optional

class Order(ActiveRecord):
    __table_name__ = "orders"
    __schema_name__ = "shop"                # -> [shop].[orders]
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    customer_id: Optional[int] = None
    total: Optional[float] = None
```

`__schema_name__` 可选，不写就是 `None`，即不加限定。一旦设上，模型构造出的每一条
语句都带上这个命名空间，其中的列引用仍然保持两段：

```python
Order.query().select(Order.c.id).to_sql()[0]
# SELECT [orders].[id] FROM [shop].[orders]

Order.query().where(Order.c.id > 1).to_sql()[0]
# SELECT * FROM [shop].[orders] WHERE [orders].[id] > ?

Order.query().group_by(Order.c.customer_id).order_by(Order.c.id).limit(5).to_sql()[0]
# SELECT * FROM [shop].[orders] GROUP BY [orders].[customer_id]
#   ORDER BY [orders].[id] ASC OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY

Order.query().group_by(Order.c.customer_id).having(Order.c.total > 10).to_sql()[0]
# SELECT * FROM [shop].[orders] GROUP BY [orders].[customer_id]
#   HAVING [orders].[total] > ?
```

`ORDER BY`、`GROUP BY` 与 `HAVING` 遵从与 `SELECT` 相同的规则：schema 只出现在
`FROM` 里的范围上，不会再出现在别处。

不设 `__schema_name__` 的模型渲染为不加限定，由连接决定落在哪里：

```python
PlainOrder.query().select(PlainOrder.c.id).to_sql()[0]
# SELECT [plain_orders].[id] FROM [plain_orders]
```

命名空间只读一次，入口是 `schema_name()`，随每个列表达式构造时一并带下去。事后再改
`__schema_name__`，已经建好的表达式不会跟着变——重建条件，或改完再新建。这条绑定
规则在核心库文档里有完整说明。

## 列引用最多两段

这是 SQL Server 与 PostgreSQL 最实质的一处差别。

T-SQL 把列的前缀解析成表名或关联名，绝不会解析成 `schema.table`。因此
`[shop].[orders].[id]` 不是 `[shop].[orders]` 的某一列，而是语法错误。`FROM` 里的
范围已经带了 `[shop]`，`[id]` 直接绑定到它：

| `FROM` 里的范围 | 列引用 | 服务端响应 |
|---|---|---|
| `[app].[orders]` | `[orders].[id]` | 接受 |
| `[app].[orders]` | `[app].[orders].[id]` | 语法错误 |
| `[app].[orders] AS [o]` | `[o].[id]` | 接受 |
| `[app].[orders] AS [o]` | `[orders].[id]` | 不在作用域内 |

左列是渲染器的产出，右列是服务端的回答，后者没有在真实实例上验证过。

PostgreSQL 对不带别名的范围同时接受 `"orders"."id"` 与 `"app"."orders"."id"`，并且
默认渲染成三段式。T-SQL 没有可对应的形式，因此本后端的方言覆盖了 `format_column`，
把每个列引用上的 schema 都去掉：

```python
Column(d, "id", table="orders", schema_name="app").to_sql()[0]   # [orders].[id]
Column(d, "id", table="o", schema_name="app").to_sql()[0]        # [o].[id]
```

去掉 schema 这一步发生在渲染层而不是构造阶段，所以手工构造的 `Column` 在这里没有
风险：通过表达式层拼不出三段式的列引用。这也正是 SQL Server 的文档不能照抄
PostgreSQL 三段式示例的原因——那些示例描述的是 T-SQL 拒绝的 SQL。

两条边界仍然生效。只带 schema 而不带表的列依旧被拒绝，因为没有可用来解析前缀的
对象：

```
ValueError: SQL Server: cannot qualify column 'id' with schema 'app' because no
table was given; a column reference needs a table (or an alias) to be
schema-qualified
```

另外，`schema_name` 为 `""` 的 `Column` 仍然被拒绝：覆盖只在值可用时才去掉 schema，
空串会一路传到核心层的校验那里，见
[空串，以及它在哪一步被拦下](#空串以及它在哪一步被拦下)。

`SELECT *` 无需限定，渲染时也不带任何限定：

```python
Order.query().to_sql()[0]
# SELECT * FROM [shop].[orders]
```

唯一没有应用两段式规则的地方是手工构造的通配符。`WildcardExpression` 由核心层的
渲染器格式化，本方言没有覆盖它，因此同时传入表名与 schema 会得到三段式：

```python
WildcardExpression(d, table="orders", schema_name="app").to_sql()[0]
# [app].[orders].*
```

查询层构造的每一个 `WildcardExpression` 都是裸的，框架不会走到这个形态；只有手工
构造才会。服务端是否接受三段式通配符，此处未经验证——渲染结果已实测，服务端的回答
尚未测试。

## 别名

取了别名的范围只能用别名标识，别名本身和其他标识符一样加方括号：

```python
Order.query().join(
    Customer, on=Order.c.customer_id == Customer.c.with_table_alias("u").id, alias="u"
).select(Order.c.id, Customer.c.with_table_alias("u").name).to_sql()[0]
# SELECT [orders].[id], [u].[name] FROM [shop].[orders]
#   JOIN [crm].[customers] AS [u] ON [orders].[customer_id] = [u].[id]
```

范围上的 schema 保留不变，变的只是列的前缀。自连接与其它后端一样，两侧都要取别名：

```python
Order.query().join(
    Order,
    on=Order.c.with_table_alias("c").id == Order.c.with_table_alias("p").customer_id,
    alias="p",
).select(Order.c.with_table_alias("c").id, Order.c.with_table_alias("p").id).to_sql()[0]
# SELECT [c].[id], [p].[id] FROM [shop].[orders]
#   JOIN [shop].[orders] AS [p] ON [c].[id] = [p].[customer_id]
```

只给列这一侧取别名，范围仍然没有别名，结果是服务端拒绝的 SQL，而不是框架提前报错的
SQL：

```python
Order.query().select(Order.c.with_table_alias("o").id).to_sql()[0]
# SELECT [o].[id] FROM [shop].[orders]        <- [o] 不在作用域内
```

范围的别名与列访问器要用同一个名字，并与 `join(..., alias=...)` 配对使用。

### 同名的两个范围

两段式规则带来一个 PostgreSQL 没有的后果。两个模型绑定到不同 schema 下的同一张表名
时，列前缀渲染出来完全相同，T-SQL 无法分辨：

```python
ShopOrder.query().join(CrmOrder, on=ShopOrder.c.user_id == CrmOrder.c.id).to_sql()[0]
# SELECT * FROM [shop].[orders] JOIN [crm].[orders] ON [orders].[user_id] = [orders].[id]
```

`FROM` 没有歧义——每一段都带方括号，每个 schema 里各有一张 `orders`——但连接条件两
侧都写着 `[orders]`。SQL Server 拒绝这样的语句（错误号 1013），要求给出关联名，所以
上面这条查询按原样无法执行：

```python
ShopOrder.query().join(
    CrmOrder, on=ShopOrder.c.user_id == CrmOrder.c.with_table_alias("c").id, alias="c"
).select(ShopOrder.c.id, CrmOrder.c.with_table_alias("c").id).to_sql()[0]
# SELECT [orders].[id], [c].[id] FROM [shop].[orders]
#   JOIN [crm].[orders] AS [c] ON [orders].[user_id] = [c].[id]
```

框架对不加别名的写法不会抛出异常，只是把有歧义的前缀渲染出来，把判断留给服务端。凡
是表名在这条语句里不唯一的范围，都给它一个关联名；或者让这些表的名字彼此不同。

## 集合操作

`UNION`、`INTERSECT` 与 `EXCEPT` 本身不指称任何对象，没有可限定的东西。每个分支各
自带自己的命名空间：

```python
Order.query().select(Order.c.id).union(Customer.query().select(Customer.c.id)).to_sql()[0]
# SELECT [orders].[id] FROM [shop].[orders]
#   UNION
#   SELECT [customers].[id] FROM [crm].[customers]
```

## CTE

CTE 的名字是给同一查询里后续语句用的，不属于 database，因此它自己的名字不加限定；
它内部的查询仍然带着模型的 schema：

```python
from rhosocial.activerecord.query.cte_query import CTEQuery

CTEQuery(backend).with_cte(
    "recent_orders", Order.query().select(Order.c.id)
).from_cte("recent_orders").select("id").to_sql()[0]
# WITH [recent_orders] AS (SELECT [orders].[id] FROM [shop].[orders])
#   SELECT [id] FROM [recent_orders]
```

## DDL 单独传 schema

凡是**指名一张表**的语句，收的都是 `TableExpression`；凡是涉及带 schema 对象的语句，
都接受属于自己的 `schema_name`，不必再手工拼限定名。传裸字符串会被拒绝——而且是在
**构造期**就拒绝，不是渲染期：

| 表达式 | 参数 |
|---|---|
| `CreateTableExpression` | `table` |
| `DropTableExpression` | `table` |
| `TruncateExpression` | `table` |
| `AlterTableExpression` | `table` |
| `CreateIndexExpression` | `table` |
| `DropIndexExpression` | `table`（可为 `None`） |
| `CreateFulltextIndexExpression` | `table` |
| `DropFulltextIndexExpression` | `table` |
| `CreateTriggerExpression` | `table`、`function_name`（可为 `None`） |
| `DropTriggerExpression` | `table`（可为 `None`） |
| `InsertExpression` | `into` |
| `DeleteExpression` | `tables`（单个或 list，逐元素检查） |
| `UpdateExpression` | `table` |
| `MergeExpression` | `target_table` |

报错信息会指明是哪个参数，而且每条都不一样：

```
TypeError: table must be a TableExpression, got str
TypeError: into must be a TableExpression, got str
TypeError: tables must be a TableExpression, got str
TypeError: every table in tables must be a TableExpression, got str
TypeError: target_table must be a TableExpression, got str
TypeError: function_name must be a TableExpression, got str
```

`DropTableExpression` 与 `TruncateExpression` **根本没有** `schema_name` 参数。
`TruncateExpression(d, "orders", schema_name="app")` 会以
`TypeError: ... got an unexpected keyword argument 'schema_name'` 失败——这两条语句
的命名空间只有一个落点，就是传进去的表引用。

```python
DropTableExpression(d, TableExpression(d, "orders", schema_name="app"),
                    if_exists=True).to_sql()[0]
# DROP TABLE IF EXISTS [app].[orders]

TruncateExpression(d, TableExpression(d, "orders", schema_name="app")).to_sql()[0]
# TRUNCATE TABLE [app].[orders]

DropIndexExpression(d, "idx_orders_id", schema_name="app").to_sql()[0]
# DROP INDEX [app].[idx_orders_id]

CreateViewExpression(d, "v_orders", Order.query().select(Order.c.id),
                     schema_name="app", replace=True).to_sql()[0]
# CREATE OR ALTER VIEW [app].[v_orders] AS SELECT [orders].[id] FROM [shop].[orders]

DropViewExpression(d, "v_orders", schema_name="app", if_exists=True).to_sql()[0]
# DROP VIEW IF EXISTS [app].[v_orders]
```

### 索引各自选择命名空间

索引语句上的 `schema_name` 只限定**索引名**。表由它自己的 `TableExpression` 限定，
两者互不影响，渲染器允许它们不同：

```python
CreateIndexExpression(
    d, "idx_shared",
    TableExpression(d, "orders", schema_name="sales"),
    ["id"], schema_name="app",
).to_sql()[0]
# CREATE INDEX [app].[idx_shared] ON [sales].[orders] ([id])
```

SQL Server 在这一点上比 Oracle 宽松：T-SQL 允许**非聚集**索引建在与它的表不同的
schema 里，所以上面这条语句服务端是接受的——同样一句放到 Oracle 上则会被拒绝。这是
SQL Server 文档化的行为，此处没有在真实实例上验证；两种情况下的渲染结果都是实测的。
两个命名空间仍然是各自独立的字段，把一个字符串同时给两者才会产出服务端拒绝的语句。
模型工厂的 `index_schema_name` 就是用来单独挪动索引的：

```python
Order.build_create_index_statement(
    dialect, "idx_orders_id", ["id"], index_schema_name="ops").to_sql()[0]
# CREATE INDEX [ops].[idx_orders_id] ON [shop].[orders] ([id])
```

### 从模型构建 DDL

```python
class Order(ActiveRecord):
    __table_name__ = "orders"
    __schema_name__ = "shop"

Order.build_table_reference(dialect).to_sql()[0]       # [shop].[orders]
Order.build_table_reference(dialect, alias="o").to_sql()[0]
# [shop].[orders] AS [o]

Order.build_truncate_statement(dialect).to_sql()[0]
# TRUNCATE TABLE [shop].[orders]

Order.build_create_index_statement(
    dialect, "idx_orders_id", ["id"]).to_sql()[0]
# CREATE INDEX [shop].[idx_orders_id] ON [shop].[orders] ([id])

Order.build_create_index_statement(
    dialect, "idx_orders_id", ["id"], index_schema_name="ops").to_sql()[0]
# CREATE INDEX [ops].[idx_orders_id] ON [shop].[orders] ([id])

Order.build_drop_index_statement(dialect, "idx_orders_id").to_sql()[0]
# DROP INDEX [shop].[idx_orders_id] ON [shop].[orders]
```

七个工厂全都经由 `build_table_reference()`，因此一次迁移不可能把一条语句限定在模型
的 schema 里、下一条却限定在别处。完整签名见核心库文档。

注意最后一行里的 `ON [shop].[orders]`：T-SQL 的 `DROP INDEX` 要指名表，工厂因此把模型
的范围一并传给了它。不传表的 `DropIndexExpression` 渲染出的是裸名，那同样是合法的
T-SQL：

```python
DropIndexExpression(d, "idx_orders_id", schema_name="app").to_sql()[0]
# DROP INDEX [app].[idx_orders_id]
```

**手工拼装的语句不会白拿 `__schema_name__`。** 模型上的 `build_*` 工厂会读它，
除此之外没有别的地方读；自己拼的语句必须自己把命名空间递进去。

DML 语句的限定方式相同，传入带限定的 `TableExpression` 即可：

```python
InsertExpression(d, TableExpression(d, "users", schema_name="app"), source,
                 columns=["id", "name"]).to_sql()[0]
# INSERT INTO [app].[users] ([id], [name]) VALUES (?, ?)

UpdateExpression(d, TableExpression(d, "users", schema_name="app"),
                 {"name": value}).to_sql()[0]
# UPDATE [app].[users] SET [name] = ?

DeleteExpression(d, TableExpression(d, "users", schema_name="app")).to_sql()[0]
# DELETE FROM [app].[users]
```

软删除的 `restore()` 会针对模型的范围重新构造一条 `UPDATE`，因此与 `delete()` 同样
带着命名空间；这条路径在核心库文档里有说明。

### 分区：方案与它引用的分区函数共用一个 schema

分区方案与它引用的分区函数必须建在同一个 schema 里，SQL Server 会强制这一点。
`SQLServerPartitionSchemeExpression` 因此用同一个 `schema_name` 限定两个名字：

```python
SQLServerPartitionFunctionExpression(
    d, "pf_orders", "DATE", ["2024-01-01"], schema_name="app",
).to_sql()[0]
# CREATE PARTITION FUNCTION [app].[pf_orders] (DATE) AS RANGE RIGHT FOR VALUES ('2024-01-01')

SQLServerPartitionSchemeExpression(
    d, "ps_orders", "pf_orders", ["PRIMARY"], schema_name="app",
).to_sql()[0]
# CREATE PARTITION SCHEME [app].[ps_orders] AS PARTITION [app].[pf_orders] TO ([PRIMARY])
```

两个表达式各自接收 schema，需要保持一致；不存在只限定方案而不限定其函数的写法。

表上的分区子句是例外：`SQLServerPartitionByRangeClause` 把方案名当作裸字符串接收，
没有存放 schema 的位置。

```python
SQLServerPartitionByRangeClause(d, [Column(d, "created_at")], "ps_orders").to_sql()[0]
#  ON [ps_orders] ([created_at])
```

服务端如何解析这个裸名字——按会话的默认 schema、按表自身的 schema，还是仅当它就是
默认 schema 时才解析——此处未经验证；位于默认 schema 之外的分区方案，也无法通过这个
表达式以限定名引用。

在本后端，这是仅剩两处「本该放命名空间的地方却收字符串」之一，而且两处都不是表目标。
另一处是 `Column.table`——用来限定列的**名字**，类型是 `str`，与同一表达式的
`schema_name` 配对。凡是指名一张表的表达式都要求 `TableExpression`，见
[DDL 单独传 schema](#ddl-单独传-schema)。

### 创建与删除 schema

在这两条语句里，schema 不是限定符，它本身就是对象：

```python
CreateSchemaExpression(d, "ar_crm").to_sql()[0]
# CREATE SCHEMA [ar_crm]

CreateSchemaExpression(d, "ar_crm", authorization="app_user").to_sql()[0]
# CREATE SCHEMA [ar_crm] AUTHORIZATION [app_user]

DropSchemaExpression(d, "ar_crm").to_sql()[0]
# DROP SCHEMA [ar_crm]
```

T-SQL 有两条约束决定了这两条语句该怎么下发，渲染器都不做检查：

- `CREATE SCHEMA` 必须独占一个批处理。要做条件创建就得借助 `EXEC`：
  `IF SCHEMA_ID('ar_crm') IS NULL EXEC('CREATE SCHEMA [ar_crm]')`。直接写
  `IF ... CREATE SCHEMA` 会在关键字附近报语法错误。
- `DROP SCHEMA` 要求该 schema 已经清空，先删除其中的对象。

`IF NOT EXISTS`、`IF EXISTS` 与 `CASCADE` 在能力标志上属于不支持——上面三个标志都是
`False`——而本方言覆盖了这两个渲染器，覆盖后的实现是**拒绝这个标志**而不是把它丢掉。
否则设了标志的调用方拿到的是一条在 schema 不存在时失败的语句，而不是他要的空操作：

```python
CreateSchemaExpression(d, "ar_crm", if_not_exists=True).to_sql()[0]
# UnsupportedFeatureError: 'SQL Server' dialect does not support CREATE SCHEMA
#   IF NOT EXISTS.
#   Suggestion: SQL Server has no IF NOT EXISTS clause for CREATE SCHEMA. Drop
#   the flag, or guard the call yourself.

DropSchemaExpression(d, "ar_crm", if_exists=True).to_sql()[0]
# UnsupportedFeatureError: 'SQL Server' dialect does not support DROP SCHEMA
#   IF EXISTS.
#   Suggestion: SQL Server has no IF EXISTS clause for DROP SCHEMA. Drop the flag,
#   or guard the call yourself.

DropSchemaExpression(d, "ar_crm", cascade=True).to_sql()[0]
# UnsupportedFeatureError: 'SQL Server' dialect does not support DROP SCHEMA
#   CASCADE.
#   Suggestion: SQL Server cannot drop a schema together with its contents. Empty
#   it first, or drop the flag.
```

`DROP SCHEMA` 先检查 `if_exists` 再检查 `cascade`，因此两个一起传时只报第一个：

```
DropSchemaExpression(d, "ar_crm", if_exists=True, cascade=True).to_sql()[0]
# UnsupportedFeatureError: 'SQL Server' dialect does not support DROP SCHEMA IF EXISTS.
```

要做条件判断，请用 `EXEC` 配合 `SCHEMA_ID(...)`，不要依赖守卫标志。

## 不加限定的名字落在哪个 schema

SQL Server 总会把不加限定的名字解析到某个默认 schema 上。是哪一个，属于服务端登录名
或数据库用户上的状态，不是连接参数：

```sql
ALTER USER app_user WITH DEFAULT_SCHEMA = ar_crm
```

改动对改动之后建立的那些连接生效。以下几点是 SQL Server 文档化的行为，而非框架行为，
此处没有在真实实例上验证：用户的默认 schema 用 `SCHEMA_NAME()` 读取；它与谁创建了哪
个 schema 无关——`sa` 建了 `ar_crm` 之后，以 `sa` 登录的会话默认读到的仍然是 `dbo`。
命名空间之间的隔离来自渲染出来的限定引用，而不是连接背后的身份。

后端通过 `SCHEMA_NAME()` 读取它：

```python
backend.get_current_schema()
```

渲染出来是

```sql
SELECT SCHEMA_NAME()
```

括号必须写。`SCHEMA_NAME` 是函数，不带括号时 T-SQL 会把这个记号当作列引用，
`SELECT SCHEMA_NAME` 因此无法解析。框架总是输出带括号的形式；不带括号的形式只会出现
在手写的 SQL 里。

与 PostgreSQL 不同，这里的结果不会是 `None`：SQL Server 总有一个默认 schema，
没有另行设置时就是 `dbo`。

连接层面没有可设置的位置。`SQLServerConnectionConfig` 没有任何与 schema 相关的字段，
既没有 `search_path` 的对应项，也没有 `default_schema`。因此命名空间要么通过在偏离
服务端默认值的模型上声明 `__schema_name__` 来选择，要么通过修改用户的 `DEFAULT_SCHEMA`
来改变。配置里的 `options` 字典不能替代它：该字典按 `KEY=value` 的形式原样追加到
ODBC 连接字符串，那是驱动参数的入口，而不是 schema 设置。

## 跨 database 的名字

限定引用除了 schema 还可以指明 database，本后端的 README 因此指向 `database.schema.object`
这一三段式写法，用来访问另一个 database。本后端不产出这种形式：

- `TableExpression` 只有表名、schema 与别名，没有 database 或 catalog 字段，也没有
  会补上它的方言钩子。
- schema 恰好渲染为一个带方括号的段。带点号的值留在单个标识符内部——
  `schema_name="app.public"` 渲染成 `[app.public].[orders]`，那是一个名字就叫
  `app.public` 的 schema。

因此 `schema_name` 指向的是当前连接所附着 database 内的 schema。要换 database，
改的是 `SQLServerConnectionConfig.database`。服务端是否接受三段式的列引用，以及跨
database 的对象如何表现，此处未经验证——本仓库没有可用的 SQL Server 实例。

## 空串，以及它在哪一步被拦下

`""` 是笔误，不表示「不加限定」——那才是 `None` 的含义。空串会被拒绝，但**不是在
构造表达式的时候**：那一刻表达式只收集参数，方言甚至可能还没定下来，严格校验因此
推迟到渲染阶段，那时语句才算是完整的。失败比预期来得晚：

```python
class Bad(ActiveRecord):
    __table_name__ = "empties"
    __schema_name__ = ""

Bad.schema_name()                        # ''           -- 未报错
Bad.c.id                                 # Column       -- 未报错
Bad.query()                              # ActiveQuery  -- 未报错
Bad.query().select(Bad.c.id)             # ActiveQuery  -- 未报错
Bad.query().select(Bad.c.id).to_sql()    # ValueError   -- 到这里才报错
```

报错信息会指明是哪个表达式：

```
ValueError: Column.schema_name must be a non-empty string; use None for an
unqualified reference
```

```
ValueError: TableExpression.schema_name must be a non-empty string; use None for
an unqualified reference
```

纯空白的字符串与空串同样被拒绝——校验先去掉空白，因此 `"   "` 也会被拒绝。非字符串值
另有一条报错信息：

```
ValueError: TableExpression.schema_name must be a string or None, not int
```

之所以拒绝而不是把 `""` 当作没传，是因为 `format_table` 用
`bool(expr.schema_name)` 判断是否限定，空串为假，于是走不加限定的分支。明明要求
`[app].[orders]` 的调用方拿到的是 `[orders]`——不报错、不告警，连受影响行数都看不出
异常。在 SQL Server 上那就是用户默认 schema 里的表，没有另行设置时是 `dbo`；语句照样
执行，数据写到了别处。

## 常见错误

**`__table_name__` 里的点号不是命名空间。** 整串会被当作一个标识符加引号：

```python
class User(ActiveRecord):
    __table_name__ = "app.users"

User.query().select(User.c.id).to_sql()[0]
# SELECT [app.users].[id] FROM [app.users]    -- 一张名字就叫 "app.users" 的表
```

要限定就设 `__schema_name__`，或者给需要限定的语句传入带限定的 `TableExpression`。

**`__schema_name__` 里的点号同样不是命名空间。** 每一段各自加引号，点号留在段内：

```python
TableExpression(d, "orders", schema_name="app.public").to_sql()[0]
# [app.public].[orders]     -- 一个名字就叫 "app.public" 的 schema
```

**指望三段式的列引用。** PostgreSQL 对不带别名的范围可以用 `"schema"."table"."column"`
寻址，T-SQL 拒绝这种形式，本后端也不会生成它。`FROM [app].[orders]` 之下正确的写法
是 `[orders].[id]`，见[列引用最多两段](#列引用最多两段)。

**连接同名表时不给关联名。** 列前缀渲染出来完全相同，服务端会拒绝这条语句，见
[同名的两个范围](#同名的两个范围)。

**给 DDL 或 DML 语句传一个裸表名。** 它在构造期抛 `TypeError`，报错信息会指明是哪个
参数——`table`、`into`、`tables` 或 `target_table`。解法是传入带限定的
`TableExpression`，而不是字符串。

**给 `DropTableExpression` 或 `TruncateExpression` 传 `schema_name`。** 这两个没有这个
参数，会因为收到未知关键字而抛 `TypeError`。命名空间要放在作为表传进去的
`TableExpression` 上。

**手工拼 DDL 并指望 `__schema_name__` 自己流进去。** 只有模型上的 `build_*` 工厂读这个
声明。手工拼装的表达式只带着你给它的命名空间。

**把索引语句上的 `schema_name` 当成表的命名空间。** 它只限定索引名；表的命名空间来自
它自己的 `TableExpression`，两者互相独立，见
[索引各自选择命名空间](#索引各自选择命名空间)。

**指望构造时报错。** 表目标是例外：那里传裸字符串会在**构造期**抛 `TypeError`。但不合法的
`schema_name` 值不是这样——在语句渲染出来之前没有任何环节会拒绝它，模型上的这类错误能
一路存活到查询构建完成的那一刻，在拼装 SQL 时才失败，见
[空串，以及它在哪一步被拦下](#空串以及它在哪一步被拦下)。

**用 `IF ... CREATE SCHEMA` 做条件创建。** `CREATE SCHEMA` 必须独占一个批处理，
要用 `EXEC`，见[创建与删除 schema](#创建与删除-schema)。

**依赖 `if_not_exists`、`if_exists` 或 `cascade`。** 在 `CREATE SCHEMA` 与
`DROP SCHEMA` 上这些标志会抛 `UnsupportedFeatureError`——它们是被拒绝，而不是被接受
后丢弃，见[创建与删除 schema](#创建与删除-schema)。

**把默认 schema 当成连接设置。** 它是服务端用户上的属性，需要在服务端修改，本后端的
连接配置没有对应字段，见[不加限定的名字落在哪个 schema](#不加限定的名字落在哪个-schema)。

## 建议的分层方式

让服务端的默认 schema 承担常规场景，`__schema_name__` 只留给例外：

- **只有一个 schema** —— 干脆不设 `__schema_name__`。不加限定的名字能让 DML、DDL 与
  内省保持一致，也不必去推理带限定的范围。
- **多个 schema** —— 只在偏离默认值的模型上设 `__schema_name__`。例外面越小，踩中上面
  这些错误的机会越少。
- **跨 schema 连接** —— 各自限定自己的范围，无需额外配置：

  ```python
  Order.query().join(
      Customer, on=Order.c.customer_id == Customer.c.id
  ).select(Order.c.id, Customer.c.name)
  # SELECT [orders].[id], [customers].[name] FROM [shop].[orders]
  #   JOIN [crm].[customers] ON [orders].[customer_id] = [customers].[id]
  ```

  只要这条语句里两个表名不唯一，就给其中任意一侧取别名。