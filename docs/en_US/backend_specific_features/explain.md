# EXPLAIN Support

## Overview

SQL Server provides execution plan analysis through various methods.

## Execution Plans

### Estimated Execution Plan

```sql
-- Show estimated execution plan
SET SHOWPLAN_XML ON
SELECT * FROM users WHERE name = 'John'
SET SHOWPLAN_XML OFF
```

### Actual Execution Plan

```sql
-- Show actual execution plan
SET STATISTICS XML ON
SELECT * FROM users WHERE name = 'John'
SET STATISTICS XML ON
```

## Query Store

SQL Server 2016+ provides Query Store for performance monitoring:

```sql
-- Enable Query Store
ALTER DATABASE mydb SET QUERY_STORE = ON;

-- Query performance insights
SELECT * FROM sys.query_store_query;
```

## See Also

- [Troubleshooting](../troubleshooting/performance.md) — Performance optimization

💡 *AI Prompt:* "How to analyze query performance in SQL Server?"
