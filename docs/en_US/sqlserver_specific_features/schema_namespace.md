# docs/en_US/sqlserver_specific_features/schema_namespace.md

# SQL Server Schema Namespaces

> This page covers what is specific to this backend: what a `schema_name` names
> here, how a qualified name is rendered, why a column reference stops at two
> parts, what a table alias leaves to address a range by, which schema an
> unqualified name resolves against, and what the partitioning and schema DDL
> statements do with the value.
>
> The model-level API — declaring `__schema_name__`, when the schema reaches
> the SQL, the DDL boundary, the cross-backend support matrix — is documented in
> the core library guide `docs/modeling/schema_namespace.md`, which lives in the
> `python-activerecord` repository
> ([`docs/en_US/modeling/schema_namespace.md`][core-en]).

[core-en]: https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US/modeling/schema_namespace.md

## How this page was verified

Every SQL fragment below was rendered by the expression layer with
`SQLServerDialect(version=(16, 0, 0))` and no live server:

```
PYTHONPATH=src .venv3.14-ubuntu26.04/bin/python
```

Measured against the `fix/schema-name-propagation-gaps` core —
`rhosocial-activerecord` 1.0.0.dev30. The core matters: an installed
`python-activerecord` from `main` predates the rewrite below and still accepts
bare table-name strings in DDL and DML, so the fragments rendered against it
differ from the ones shown here.

Statements that describe the server rather than the renderer — error numbers,
the semantics of `DEFAULT_SCHEMA`, `CREATE SCHEMA` as a batch, cross-database
names — are SQL Server's own behaviour and were not exercised against a live
instance in this repository. Each is marked where it appears, and every point
left open by the absence of an instance says so in place.

## What a `schema_name` names here

`SQLServerDialect` implements the core `SchemaSupport` protocol, so a
`schema_name` is accepted everywhere the core expects one. What it *names* is
SQL Server's own: **a schema inside the current database**. One database holds
several, and each one owns its objects outright — `[app].[orders]` and
`[crm].[orders]` are two tables that happen to share a name, and a qualified
reference reaches exactly one of them.

The capability flags are not all `True`:

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

The three `False` flags are properties of the statement grammar rather than of
the namespace layer: `CREATE SCHEMA IF NOT EXISTS`, `DROP SCHEMA IF EXISTS` and
`DROP SCHEMA CASCADE` are not T-SQL. See
[`CREATE SCHEMA` / `DROP SCHEMA`](#create-schema--drop-schema).

`supports_index_schema_qualification()` answers a separate question — whether an
index *name* may carry a namespace — and SQL Server answers `True`, because its
`CREATE INDEX` accepts a qualified index name. A dialect whose grammar forbids it
answers `False` and raises `UnsupportedFeatureError` while rendering. See
[Indexes choose a namespace](#indexes-choose-a-namespace).

Rendering uses square brackets, one bracketed identifier per segment:

| Expression | SQL |
|---|---|
| `TableExpression(d, "orders", schema_name="app")` | `[app].[orders]` |
| `TableExpression(d, "orders")` | `[orders]` |
| `TableExpression(d, "orders", schema_name="app", alias="o")` | `[app].[orders] AS [o]` |

### Quoting

`format_identifier` brackets by default and escapes an embedded bracket by
doubling it, so a name that would otherwise terminate the reference stays
inside one identifier:

```python
TableExpression(d, "orders", schema_name="app]x").to_sql()[0]
# [app]]x].[orders]

TableExpression(d, "orders", schema_name="My Schema").to_sql()[0]
# [My Schema].[orders]
```

A schema name containing a space needs no further escaping, and a reserved word
is bracketed the same way as any other name:

```python
TableExpression(d, "user", schema_name="dbo").to_sql()[0]
# [dbo].[user]
```

Brackets preserve the name as written; whether `[My Schema]` and `[my schema]`
denote the same schema is decided by the collation of the database, not by the
framework.

A dot inside a value is not a separator — each segment is quoted on its own, so
the dot stays inside the segment. See
[Common mistakes](#common-mistakes).

## Declaring one on a model

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

`__schema_name__` is optional and defaults to `None`, which means unqualified.
When it is set, every statement the model builds carries the namespace, and the
column references inside it stay two-part:

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

`ORDER BY`, `GROUP BY` and `HAVING` are subject to the same rule as `SELECT`:
the schema is on the range in `FROM` and nowhere else.

A model without `__schema_name__` renders unqualified and leaves the choice to
the connection:

```python
PlainOrder.query().select(PlainOrder.c.id).to_sql()[0]
# SELECT [plain_orders].[id] FROM [plain_orders]
```

The namespace is read once, through `schema_name()`, and reaches each column
expression as it is built. Changing `__schema_name__` afterwards does not
rewrite an expression that already exists — rebuild the condition, or build it
after the change. The core guide describes the binding in full.

## Columns take at most two parts

This is the one rule that makes SQL Server differ from PostgreSQL.

T-SQL resolves a column prefix as a table name or a correlation name — never as
`schema.table`. So `[shop].[orders].[id]` is not a column of `[shop].[orders]`;
it is a syntax error. The `FROM` range already carries `[shop]`, and `[id]`
binds against it:

| Range in `FROM` | Column reference | Server response |
|---|---|---|
| `[app].[orders]` | `[orders].[id]` | accepted |
| `[app].[orders]` | `[app].[orders].[id]` | syntax error |
| `[app].[orders] AS [o]` | `[o].[id]` | accepted |
| `[app].[orders] AS [o]` | `[orders].[id]` | not in scope |

The left-hand column is what the renderer produces; the right-hand column is the
server's answer, and was not exercised against a live instance here.

PostgreSQL permits both `"orders"."id"` and `"app"."orders"."id"` for an
unaliased range, and its renderer produces the three-part form. T-SQL has no
equivalent form to produce, so this backend's dialect overrides `format_column`
and drops the schema from every column reference:

```python
Column(d, "id", table="orders", schema_name="app").to_sql()[0]   # [orders].[id]
Column(d, "id", table="o", schema_name="app").to_sql()[0]        # [o].[id]
```

Because the drop happens in the renderer rather than at construction, a
hand-built `Column` is safe here where it is not on PostgreSQL: there is no way
to assemble a three-part column reference through the expression layer. This is
also why a SQL Server page must not repeat PostgreSQL's three-part examples —
they describe SQL that T-SQL rejects.

Two boundaries remain in force. A column that carries a schema but no table is
still refused, because there is nothing to resolve the prefix against:

```
ValueError: SQL Server: cannot qualify column 'id' with schema 'app' because no
table was given; a column reference needs a table (or an alias) to be
schema-qualified
```

And a `Column` whose `schema_name` is `""` is still rejected. The override drops
the schema only when it is a usable value, so an empty one reaches the core
validator — see [The empty string](#the-empty-string-and-when-it-is-caught).

`SELECT *` needs no qualification and is rendered without any:

```python
Order.query().to_sql()[0]
# SELECT * FROM [shop].[orders]
```

One place the two-part rule is not applied is a wildcard built by hand.
`WildcardExpression` is formatted by the core renderer, which this dialect does
not override, so passing it a table and a schema produces the three-part form:

```python
WildcardExpression(d, table="orders", schema_name="app").to_sql()[0]
# [app].[orders].*
```

No query built by the framework reaches that shape — every `WildcardExpression`
the query layer creates is bare — but a hand-built one does. Whether the server
accepts a three-part wildcard was not verified here; treat the rendering as
measured and the server's answer as untested.

## Aliases

An aliased range is addressed by its alias alone, and the alias is bracketed like
any other identifier:

```python
Order.query().join(
    Customer, on=Order.c.customer_id == Customer.c.with_table_alias("u").id, alias="u"
).select(Order.c.id, Customer.c.with_table_alias("u").name).to_sql()[0]
# SELECT [orders].[id], [u].[name] FROM [shop].[orders]
#   JOIN [crm].[customers] AS [u] ON [orders].[customer_id] = [u].[id]
```

The range keeps its schema; only the column prefix changes. A self-join aliases
both sides, as on any backend:

```python
Order.query().join(
    Order,
    on=Order.c.with_table_alias("c").id == Order.c.with_table_alias("p").customer_id,
    alias="p",
).select(Order.c.with_table_alias("c").id, Order.c.with_table_alias("p").id).to_sql()[0]
# SELECT [c].[id], [p].[id] FROM [shop].[orders]
#   JOIN [shop].[orders] AS [p] ON [c].[id] = [p].[customer_id]
```

Aliasing only the column side leaves the range unaliased, and the result is SQL
the server rejects rather than SQL the framework refuses:

```python
Order.query().select(Order.c.with_table_alias("o").id).to_sql()[0]
# SELECT [o].[id] FROM [shop].[orders]        <- [o] is not in scope
```

Build the range alias and the column accessor from the same name, and pair them
with `join(..., alias=...)`.

### Two ranges that expose the same name

The two-part rule has a consequence that PostgreSQL does not share. Two models
bound to the same table name in different schemas render column prefixes that
are textually identical, and T-SQL cannot tell them apart:

```python
ShopOrder.query().join(CrmOrder, on=ShopOrder.c.user_id == CrmOrder.c.id).to_sql()[0]
# SELECT * FROM [shop].[orders] JOIN [crm].[orders] ON [orders].[user_id] = [orders].[id]
```

`FROM` is unambiguous — each segment is bracketed and each schema holds one
`orders` — but the join condition names `[orders]` on both sides. SQL Server
rejects a statement whose ranges share an exposed name (error 1013) and requires
correlation names instead, so this query cannot run as written:

```python
ShopOrder.query().join(
    CrmOrder, on=ShopOrder.c.user_id == CrmOrder.c.with_table_alias("c").id, alias="c"
).select(ShopOrder.c.id, CrmOrder.c.with_table_alias("c").id).to_sql()[0]
# SELECT [orders].[id], [c].[id] FROM [shop].[orders]
#   JOIN [crm].[orders] AS [c] ON [orders].[user_id] = [c].[id]
```

The framework does not raise for the unaliased form; it renders the ambiguous
prefix and leaves the diagnosis to the server. Give any range whose table name
is not unique in the statement a correlation name, or give the tables distinct
names.

## Set operations

`UNION`, `INTERSECT` and `EXCEPT` name no object of their own, so there is
nothing for them to qualify. Each branch keeps its own namespace:

```python
Order.query().select(Order.c.id).union(Customer.query().select(Customer.c.id)).to_sql()[0]
# SELECT [orders].[id] FROM [shop].[orders]
#   UNION
#   SELECT [customers].[id] FROM [crm].[customers]
```

## CTEs

A CTE is named for the rest of the query, not for the database, so its own name
is bare. The query inside it still carries the model's schema:

```python
from rhosocial.activerecord.query.cte_query import CTEQuery

CTEQuery(backend).with_cte(
    "recent_orders", Order.query().select(Order.c.id)
).from_cte("recent_orders").select("id").to_sql()[0]
# WITH [recent_orders] AS (SELECT [orders].[id] FROM [shop].[orders])
#   SELECT [id] FROM [recent_orders]
```

## DDL takes a schema of its own

Every statement that names a table takes a `TableExpression`, and every statement
that names a schema-bearing object accepts a `schema_name` of its own, so
qualification no longer has to be assembled by hand. A bare string is refused —
at construction, not at render time:

| Expression | Argument |
|---|---|
| `CreateTableExpression` | `table` |
| `DropTableExpression` | `table` |
| `TruncateExpression` | `table` |
| `AlterTableExpression` | `table` |
| `CreateIndexExpression` | `table` |
| `DropIndexExpression` | `table` (may be `None`) |
| `CreateFulltextIndexExpression` | `table` |
| `DropFulltextIndexExpression` | `table` |
| `CreateTriggerExpression` | `table`, `function_name` (may be `None`) |
| `DropTriggerExpression` | `table` (may be `None`) |
| `InsertExpression` | `into` |
| `DeleteExpression` | `tables` (one or a list, checked element by element) |
| `UpdateExpression` | `table` |
| `MergeExpression` | `target_table` |

The message names the argument at fault, and each one reads differently:

```
TypeError: table must be a TableExpression, got str
TypeError: into must be a TableExpression, got str
TypeError: tables must be a TableExpression, got str
TypeError: every table in tables must be a TableExpression, got str
TypeError: target_table must be a TableExpression, got str
TypeError: function_name must be a TableExpression, got str
```

`DropTableExpression` and `TruncateExpression` have no `schema_name` parameter at
all — `TruncateExpression(d, "orders", schema_name="app")` fails with
`TypeError: ... got an unexpected keyword argument 'schema_name'`, because the
namespace has exactly one home on those two, and it is the table reference.

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

A hand-assembled expression does not get `__schema_name__` for free. The model's
`build_*` factories read it and nothing else does — see
[DDL built from a model](#ddl-built-from-a-model).

### Indexes choose a namespace

`schema_name` on an index statement qualifies **the index name**. The table is
qualified by its own `TableExpression`, and the renderer lets the two differ:

```python
CreateIndexExpression(
    d, "idx_shared",
    TableExpression(d, "orders", schema_name="sales"),
    ["id"], schema_name="app",
).to_sql()[0]
# CREATE INDEX [app].[idx_shared] ON [sales].[orders] ([id])
```

SQL Server is more permissive here than Oracle. T-SQL lets a **nonclustered**
index be created in a schema other than its table's, so the statement above is
one the server accepts — unlike the same statement on Oracle, which refuses it.
That is SQL Server's documented behaviour and was not exercised against a live
instance here; the rendering is measured either way. The two namespaces remain
independent fields, and the model factory's `index_schema_name` is what moves an
index on its own:

```python
Order.build_create_index_statement(
    dialect, "idx_orders_id", ["id"], index_schema_name="ops").to_sql()[0]
# CREATE INDEX [ops].[idx_orders_id] ON [shop].[orders] ([id])
```

### DDL built from a model

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

Every one of the seven factories goes through `build_table_reference()`, so a
migration cannot qualify one statement in the model's schema and the next in
another. The full signatures are in the core guide.

Note the `ON [shop].[orders]` on that last line: T-SQL's `DROP INDEX` names the
table, and the factory supplies the model's range for it. `DropIndexExpression`
handed no table renders the bare name, which is also valid T-SQL:

```python
DropIndexExpression(d, "idx_orders_id", schema_name="app").to_sql()[0]
# DROP INDEX [app].[idx_orders_id]
```

The DML statements qualify the same way, taking a qualified `TableExpression`:

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

Because soft delete rebuilds an `UPDATE` against the model's range, `restore()`
carries the namespace down the same way `delete()` does; the core guide covers
that path.

### Partitioning: one schema for the scheme and its function

A partition scheme and the partition function it references have to live in the
same schema, and SQL Server enforces it. `SQLServerPartitionSchemeExpression`
therefore qualifies both names from its single `schema_name`:

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

The two expressions take the schema independently and have to agree; there is
no form that qualifies the scheme without also qualifying its function.

The partition clause on a table is the exception: `SQLServerPartitionByRangeClause`
names the scheme as a bare string, with no slot for a schema.

```python
SQLServerPartitionByRangeClause(d, [Column(d, "created_at")], "ps_orders").to_sql()[0]
#  ON [ps_orders] ([created_at])
```

How the server resolves that bare name — against the session's default schema,
against the table's own schema, or only when it is the default one — was not
verified here, and a partition scheme outside the default schema cannot be
referred to by a qualified name through this expression.

On this backend this is one of only two places left where a string is accepted
where a namespace would otherwise go, and neither of them is a table target. The
other is `Column.table` — the *name* used to qualify a column, which is a `str`
and pairs with the same expression's `schema_name`. Everything that names a table
requires a `TableExpression`; see
[DDL takes a schema of its own](#ddl-takes-a-schema-of-its-own).

### `CREATE SCHEMA` / `DROP SCHEMA`

There, the schema is not a qualifier — it *is* the object:

```python
CreateSchemaExpression(d, "ar_crm").to_sql()[0]
# CREATE SCHEMA [ar_crm]

CreateSchemaExpression(d, "ar_crm", authorization="app_user").to_sql()[0]
# CREATE SCHEMA [ar_crm] AUTHORIZATION [app_user]

DropSchemaExpression(d, "ar_crm").to_sql()[0]
# DROP SCHEMA [ar_crm]
```

Two T-SQL constraints shape how these are issued, and neither is enforced by the
renderer:

- `CREATE SCHEMA` must be the only statement in its batch. A guarded creation
  therefore has to go through `EXEC`:
  `IF SCHEMA_ID('ar_crm') IS NULL EXEC('CREATE SCHEMA [ar_crm]')`. A bare
  `IF ... CREATE SCHEMA` is a syntax error near the keyword.
- `DROP SCHEMA` requires the schema to be empty. Drop its objects first.

`IF NOT EXISTS`, `IF EXISTS` and `CASCADE` are reported as unsupported — the three
flags above answer `False` — and this dialect overrides both formatters to
**refuse the flag** rather than drop it. A caller who set `if_exists` would
otherwise get a statement that fails on a missing schema instead of the no-op it
asked for:

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

`DROP SCHEMA` checks `if_exists` before `cascade`, so asking for both reports only
the first:

```
DropSchemaExpression(d, "ar_crm", if_exists=True, cascade=True).to_sql()[0]
# UnsupportedFeatureError: 'SQL Server' dialect does not support DROP SCHEMA IF EXISTS.
```

To make either statement conditional, test the namespace with `SCHEMA_ID(...)`
inside an `EXEC` rather than relying on a guard flag.

## Which schema an unqualified name resolves against

SQL Server always resolves an unqualified name against a default schema. Which
one is server-side state on the login or database user, not a connection
parameter:

```sql
ALTER USER app_user WITH DEFAULT_SCHEMA = ar_crm
```

The change applies to that user's connections made after it. The following
statements are SQL Server's documented behaviour rather than framework behaviour,
and were not exercised against a live instance here: a user's default schema is
read with `SCHEMA_NAME()`, and it is independent of who created which schema —
a session logged in as `sa` still reads `dbo` by default after `sa` has created
`ar_crm`. Isolation between namespaces comes from the rendered reference, not
from the identity behind the connection.

The backend reads it through `SCHEMA_NAME()`:

```python
backend.get_current_schema()
```

which renders

```sql
SELECT SCHEMA_NAME()
```

The parentheses are required. `SCHEMA_NAME` is a function, and without them
T-SQL reads the token as a column reference, so `SELECT SCHEMA_NAME` fails to
resolve. The framework always emits the call form; the bare form only appears
in SQL written by hand.

Unlike PostgreSQL, the result is never `None`: SQL Server always has a default
schema, `dbo` unless the user has one of their own.

There is nothing on the connection to set. `SQLServerConnectionConfig` has no
schema field — no `search_path` counterpart and no `default_schema` — so a
namespace is chosen by declaring `__schema_name__` on the models that deviate
from the server default, or by changing `DEFAULT_SCHEMA` on the user. The
config's `options` dict is not a substitute: it is appended verbatim to the ODBC
connection string as `KEY=value` keywords, which is the driver's escape hatch
rather than a schema setting.

## Names that span databases

A qualified reference can name a database as well as a schema, and the backend's
README points at the three-part form `database.schema.object` for reaching
another database. Nothing in this backend produces one:

- `TableExpression` carries a name, a schema and an alias. There is no database
  or catalog field, and no dialect hook that would add one.
- The schema is rendered as exactly one bracketed segment. A dotted value stays
  inside a single identifier — `schema_name="app.public"` renders
  `[app.public].[orders]`, which is a schema literally named `app.public`.

So `schema_name` addresses a schema in the database the connection is already
attached to. Changing which database that is means changing
`SQLServerConnectionConfig.database`. Whether the server accepts a three-part
column reference, and how a cross-database object behaves, was not verified here
— this repository has no live SQL Server instance.

## The empty string, and when it is caught

`""` is a mistake, not a way of saying "unqualified" — that is what `None`
means. It is rejected, but **not when the expression is built**. An expression
only collects parameters at that point — its dialect may not even be settled
yet — so strict validation happens while the statement is rendered, where the
statement is known to be whole. The failure therefore arrives later than you
would expect:

```python
class Bad(ActiveRecord):
    __table_name__ = "empties"
    __schema_name__ = ""

Bad.schema_name()                        # ''           -- no error
Bad.c.id                                 # Column       -- no error
Bad.query()                              # ActiveQuery  -- no error
Bad.query().select(Bad.c.id)             # ActiveQuery  -- no error
Bad.query().select(Bad.c.id).to_sql()    # ValueError   -- here
```

The message names the expression at fault:

```
ValueError: Column.schema_name must be a non-empty string; use None for an
unqualified reference
```

```
ValueError: TableExpression.schema_name must be a non-empty string; use None for
an unqualified reference
```

A blank string is rejected the same way as an empty one — the check strips
whitespace first, so `"   "` is refused too. A non-string is rejected with its
own message:

```
ValueError: TableExpression.schema_name must be a string or None, not int
```

The reason to reject rather than treat `""` as absent: `format_table` decides
whether to qualify from `bool(expr.schema_name)`, which is false for `""`, and
takes the unqualified branch. A caller who asked for `[app].[orders]` would get
`[orders]` with no error, no warning and no affected-row count to notice it by.
On SQL Server that is the table in the user's default schema — `dbo` unless the
user has one of their own — so the statement runs and writes to the wrong place.

## Common mistakes

**A dot in `__table_name__` is not a namespace.** The identifier is quoted as a
single unit:

```python
class User(ActiveRecord):
    __table_name__ = "app.users"

User.query().select(User.c.id).to_sql()[0]
# SELECT [app.users].[id] FROM [app.users]    -- a table named literally "app.users"
```

Use `__schema_name__`, or pass a qualified `TableExpression` to the statement
that needs one.

**A dot in `__schema_name__` is not a namespace either.** Each segment is quoted
separately, so a dot inside one stays inside that one:

```python
TableExpression(d, "orders", schema_name="app.public").to_sql()[0]
# [app.public].[orders]     -- a schema literally named "app.public"
```

**Expecting a three-part column reference.** On PostgreSQL an unaliased range may
be addressed as `"schema"."table"."column"`. T-SQL rejects that form, and this
backend never emits it. `[orders].[id]` under `FROM [app].[orders]` is the
correct spelling; see [Columns take at most two parts](#columns-take-at-most-two-parts).

**Joining two ranges that share a table name without correlation names.** The
column prefixes come out identical and the server refuses the statement. See
[Two ranges that expose the same name](#two-ranges-that-expose-the-same-name).

**Expecting construction to raise for a bad `schema_name`.** A table *target* is
the exception — a bare string there raises `TypeError` at construction. A bad
`schema_name` value is not: nothing rejects it until the statement renders, so a
model-level mistake survives every step up to and including query building and
fails at the point the SQL is assembled. See
[The empty string](#the-empty-string-and-when-it-is-caught).

**Handing a DDL or DML statement a bare table name.** It raises `TypeError` at
construction, and the message names the argument at fault — `table`, `into`,
`tables` or `target_table`. The fix is a qualified `TableExpression`, not a
string.

**Passing `schema_name` to `DropTableExpression` or `TruncateExpression`.** Those
two have no such parameter and raise `TypeError` for the unexpected keyword. Put
the namespace on the `TableExpression` you pass as the table.

**Building DDL by hand and expecting `__schema_name__` to reach it.** Only the
model factories read the declaration. An expression assembled at a call site
carries whatever namespaces it was given.

**Reading a `schema_name` on an index statement as the table's namespace.** It
qualifies the index name only; the table's namespace comes from its own
`TableExpression`, and the two are independent. See
[Indexes choose a namespace](#indexes-choose-a-namespace).

**Guarding `CREATE SCHEMA` with `IF ... CREATE SCHEMA`.** `CREATE SCHEMA` must be
alone in its batch; use `EXEC`. See
[`CREATE SCHEMA` / `DROP SCHEMA`](#create-schema--drop-schema).

**Relying on `if_not_exists`, `if_exists` or `cascade`.** On `CREATE SCHEMA` and
`DROP SCHEMA` these flags raise `UnsupportedFeatureError` — they are refused, not
accepted and dropped. See
[`CREATE SCHEMA` / `DROP SCHEMA`](#create-schema--drop-schema).

**Treating the default schema as a connection setting.** It is a property of the
user, changed on the server, and this backend's connection config has no field
for it. See
[Which schema an unqualified name resolves against](#which-schema-an-unqualified-name-resolves-against).

## Recommended layering

Let the server's default schema carry the common case and reserve
`__schema_name__` for the exception:

- **Single schema** — set no `__schema_name__` at all. Unqualified names keep
  DML, DDL and introspection consistent with one another, and there is no
  qualified range to reason about.
- **Several schemas** — set `__schema_name__` only on the models that deviate
  from the default. The smaller the exceptional surface, the fewer chances of
  hitting the mistakes above.
- **Cross-schema joins** — each side qualifies its own range, so this works
  without extra configuration:

  ```python
  Order.query().join(
      Customer, on=Order.c.customer_id == Customer.c.id
  ).select(Order.c.id, Customer.c.name)
  # SELECT [orders].[id], [customers].[name] FROM [shop].[orders]
  #   JOIN [crm].[customers] ON [orders].[customer_id] = [customers].[id]
  ```

  Alias either side whenever the two table names are not distinct in the
  statement.