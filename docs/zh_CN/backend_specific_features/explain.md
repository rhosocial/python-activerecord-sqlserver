# EXPLAIN 支持

## 概述

SQL Server 通过多种方式提供执行计划分析。

## 执行计划

### 预估执行计划

```sql
-- 显示预估执行计划
SET SHOWPLAN_XML ON
SELECT * FROM users WHERE name = 'John'
SET SHOWPLAN_XML OFF
```

### 实际执行计划

```sql
-- 显示实际执行计划
SET STATISTICS XML ON
SELECT * FROM users WHERE name = 'John'
SET STATISTICS XML OFF
```

## Query Store

SQL Server 2016+ 提供 Query Store 用于性能监控：

```sql
-- 启用 Query Store
ALTER DATABASE mydb SET QUERY_STORE = ON;

-- 查询性能洞察
SELECT * FROM sys.query_store_query;
```

## 另请参阅

- [故障排除](../troubleshooting/performance.md) — 性能优化

💡 *AI 提示：* "如何在 SQL Server 中分析查询性能？"
