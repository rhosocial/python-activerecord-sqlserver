# SQL Server 特定功能

本节介绍与其他后端不同的 SQL Server 特定功能。rhosocial-activerecord 对许多功能使用两层架构：**核心层**提供通用接口和默认实现，而每个后端的**方言层**覆盖格式化并添加后端特定功能。

当你遇到本节中的功能时，请检查它是后端特定扩展还是具有后端特定格式化的核心功能——文档将指示适用的层。

## 目录

- [Dialect 表达式](dialect.md)：两层表达式系统——通用核心和 T-SQL 特定覆盖
- [字段类型](field_types.md)：核心 DataType 层次结构和 SQL Server 特定类型扩展
- [索引](indexing.md)：SQL Server 特定索引类型和优化策略
- [EXPLAIN](explain.md)：查询执行计划分析（SET STATISTICS IO/TIME）
- [内省](introspection.md)：数据库元数据查询和架构检查
- [分区](partition.md)：使用分区方案和函数的表分区

## 功能亮点

| 功能 | 通用层 | SQL Server 特定层 |
|------|--------|-------------------|
| 表达式 | 核心表达式类（Column、Literal、FunctionCall 等） | T-SQL 覆盖和 SQL Server 特定表达式类（OUTPUT、OPENJSON、PIVOT） |
| 类型系统 | 核心 DataType 层次结构（IntegerType、VarCharType 等） | SQL Server 特定 DataType 子类（NVarCharType、DateTime2Type、HierarchyIdType） |
| EXPLAIN | ExplainExpression 接口 | SET STATISTICS IO/TIME 语法 |
| 内省 | Introspector 接口 | SQL Server 元数据查询（INFORMATION_SCHEMA、sys.） |

## SQL Server 特定表达式类

| 表达式 | 用途 |
|--------|------|
| `SQLServerOutputInsertedExpression` | OUTPUT INSERTED 用于返回插入的行 |
| `SQLServerOutputDeletedExpression` | OUTPUT DELETED 用于返回删除的行 |
| `SQLServerTableHintClause` | WITH（NOLOCK、ROWLOCK 等）表提示 |
| `SQLServerTemporalPeriodDefinition` | FOR SYSTEM_TIME 时态查询 |
| `SQLServerSystemVersioningClause` | 系统版本控制 DDL |
| `SQLServerOpenJsonExpression` | OPENJSON 用于 JSON 展开 |
| `SQLServerNextValueForExpression` | NEXT VALUE FOR 序列访问 |
| `SQLServerTryCastExpression` | TRY_CAST 带错误处理 |
| `SQLServerTryConvertExpression` | TRY_CONVERT 带错误处理 |
| `SQLServerContainsPredicate` | CONTAINS 全文谓词 |
| `SQLServerFreetextPredicate` | FREETEXT 全文谓词 |
| `SQLServerPivotExpression` | PIVOT 行转列变换 |
| `SQLServerUnpivotExpression` | UNPIVOT 列转行变换 |
| `SQLServerColumnstoreIndexExpression` | 列存储索引 DDL |

## 相关主题

- [类型适配器](../type_adapters/README.md) — 类型映射和自定义适配器
- [DDL 操作](../ddl/README.md) — 架构管理
- [核心：表达式系统](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/backend/expression)
- [核心：后端系统](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/backend)
