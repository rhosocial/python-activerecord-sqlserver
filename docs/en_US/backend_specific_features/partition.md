# Table Partitioning

## Overview

SQL Server supports table partitioning for large tables.

## Partitioning Concepts

- **Partition Function**: Maps rows to partitions
- **Partition Scheme**: Maps partitions to filegroups
- **Partitioned Table**: Table that uses a partition scheme

## Creating Partitions

### Declarative Partition Spec (model level)

SQL Server RANGE partitioning can be declared on the model via
`SQLServerRangePartition`; the SQL Server dialect claims it at
`generate_create_table(dialect)` time (other backends ignore it) and renders
`ON [scheme] ([column])`:

```python
from rhosocial.activerecord.backend.impl.sqlserver.ddl_spec import (
    SQLServerRangePartition,
)

class Orders(ActiveRecord):
    __table_partition__ = [
        SQLServerRangePartition(
            column="created_at",
            partition_scheme="ps_orders",
            boundaries=["2026-01-01", "2027-01-01"],  # for the companion partition function
        ),
    ]

expr = Orders.generate_create_table(dialect)
```

The companion `CREATE PARTITION FUNCTION` / `CREATE PARTITION SCHEME`
statements are separate DDL (see the expression-level path below).

```sql
-- Create partition function (RANGE by year)
CREATE PARTITION FUNCTION pf_orders_by_year (INT)
AS RANGE LEFT FOR VALUES (2022, 2023, 2024);

-- Create partition scheme
CREATE PARTITION SCHEME ps_orders_by_year
AS PARTITION pf_orders_by_year ALL TO ([PRIMARY]);

-- Create partitioned table
CREATE TABLE orders (
    id INT NOT NULL,
    order_year INT NOT NULL,
    amount DECIMAL(10,2)
) ON ps_orders_by_year(order_year);
```

## Partition Management

```sql
-- Split to add new partition
ALTER PARTITION FUNCTION pf_orders_by_year()
SPLIT RANGE (2025);

-- Merge to remove partition
ALTER PARTITION FUNCTION pf_orders_by_year()
MERGE RANGE (2022);

-- Switch partition
ALTER TABLE orders SWITCH PARTITION 1 TO orders_archive;
```

## Querying Partitions

```python
# Query partition metadata
# SELECT * FROM sys.partitions WHERE object_id = OBJECT_ID('orders')
```

## See Also

- [Performance](../troubleshooting/performance.md) — Query optimization

💡 *AI Prompt:* "When should I use table partitioning in SQL Server?"
