# 表分区

## 概述

SQL Server 支持表分区用于大表。

## 分区概念

- **分区函数**：将行映射到分区
- **分区方案**：将分区映射到文件组
- **分区表**：使用分区方案的表

## 创建分区

### 声明式分区 Spec（模型级）

SQL Server RANGE 分区可在模型上通过 `SQLServerRangePartition` 声明；
SQL Server 方言在 `generate_create_table(dialect)` 时认领（其他后端忽略），
渲染 `ON [scheme] ([column])`：

```python
from rhosocial.activerecord.backend.impl.sqlserver.ddl_spec import (
    SQLServerRangePartition,
)

class Orders(ActiveRecord):
    __table_partition__ = [
        SQLServerRangePartition(
            column="created_at",
            partition_scheme="ps_orders",
            boundaries=["2026-01-01", "2027-01-01"],  # 供配套分区函数使用
        ),
    ]

expr = Orders.generate_create_table(dialect)
```

配套的 `CREATE PARTITION FUNCTION` / `CREATE PARTITION SCHEME` 语句是独立 DDL
（见下方表达式层路径）。

```sql
-- 创建分区函数（按年份 RANGE）
CREATE PARTITION FUNCTION pf_orders_by_year (INT)
AS RANGE LEFT FOR VALUES (2022, 2023, 2024);

-- 创建分区方案
CREATE PARTITION SCHEME ps_orders_by_year
AS PARTITION pf_orders_by_year ALL TO ([PRIMARY]);

-- 创建分区表
CREATE TABLE orders (
    id INT NOT NULL,
    order_year INT NOT NULL,
    amount DECIMAL(10,2)
) ON ps_orders_by_year(order_year);
```

## 分区管理

```sql
-- 拆分添加新分区
ALTER PARTITION FUNCTION pf_orders_by_year()
SPLIT RANGE (2025);

-- 合并删除分区
ALTER PARTITION FUNCTION pf_orders_by_year()
MERGE RANGE (2022);

-- 切换分区
ALTER TABLE orders SWITCH PARTITION 1 TO orders_archive;
```

## 查询分区

```python
# 查询分区元数据
# SELECT * FROM sys.partitions WHERE object_id = OBJECT_ID('orders')
```

## 另请参阅

- [性能](../troubleshooting/performance.md) — 查询优化

💡 *AI 提示：* "何时应该在 SQL Server 中使用表分区？"
