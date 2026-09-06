# 类型适配器

## 概述

类型适配器处理 SQL Server 数据类型和 Python 类型之间的转换。rhosocial-activerecord 为常见类型提供内置适配器，并允许你为特殊用例创建自定义适配器。

## 架构：类型转换如何工作

rhosocial-activerecord 使用**两层类型系统**在 Python 类型和 SQL 类型之间进行转换：

### 第一层：核心 DataType 层次结构

核心库在 `rhosocial.activerecord.backend.expression.types` 中定义泛型 `DataType` 类：

```python
from rhosocial.activerecord.backend.expression.types import (
    IntegerType,
    VarCharType,
    BooleanType,
    TimestampType,
    JsonType,
)
```

这些核心类型是**后端无关**的——它们定义逻辑类型而不指定确切的 SQL 语法。

### 第二层：SQL Server 特定 DataType 子类

SQL Server 用数据库特定行为扩展核心类型：

| 核心类型 | SQL Server 类型 | 行为 |
|---------|----------------|------|
| `IntegerType` | `SQLServerTinyIntType` | 映射到 TINYINT（0-255） |
| `IntegerType` | `SQLServerBitType` | 映射到 BIT（0/1） |
| `VarCharType` | `SQLServerNVarCharType` | Unicode NVARCHAR |
| `VarCharType` | `SQLServerNCharType` | Unicode NCHAR |
| `VarCharType` | `SQLServerNVarCharMaxType` | NVARCHAR(MAX) |
| `BinaryType` | `SQLServerVarBinaryType` | VARBINARY(n) |
| `BinaryType` | `SQLServerVarBinaryMaxType` | VARBINARY(MAX) |
| `XmlType` | `SQLServerXmlType` | 原生 XML 类型 |

### 转换流程

```
Python 字段声明
    ↓
核心 DataType（如 IntegerType）
    ↓
Dialect.suggest_column_type() → 映射到后端特定类型
    ↓
SQL Server DataType（如 SQLServerNVarCharType）
    ↓
Dialect.format_data_type() → 生成 SQL 类型字符串
    ↓
NVARCHAR(255)
```

## 目录

- [类型映射](mapping.md)：SQL Server 到 Python 类型转换表
- [自定义适配器](custom.md)：使用自定义适配器扩展类型支持
- [时区处理](timezone.md)：DATETIMEOFFSET 和时区配置

## 另请参阅

- [后端特定功能：字段类型](../backend_specific_features/field_types.md) — DataType 层次结构和后端特定类型
- [Dialect 表达式](../backend_specific_features/dialect.md) — 功能检测和协议系统
- [核心：自定义类型](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/modeling/custom_types)

💡 *AI 提示词：* "类型系统如何在 Python 类型和 SQL Server 类型之间进行转换？"
