# 表分区

## 概述

SQL Server 支持表分区用于大表。

## 分区概念

- **分区函数**：将行映射到分区
- **分区方案**：将分区映射到文件组
- **分区表**：使用分区方案的表

## 创建分区

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
