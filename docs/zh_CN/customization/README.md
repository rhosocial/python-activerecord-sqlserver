# 自定义

## 概述

rhosocial-activerecord 设计为可扩展的。你可以在多个级别自定义框架：

1. **自定义表达式** — 为 T-SQL 语法创建新的表达式类
2. **自定义数据类型** — 为自定义列类型定义新的 DataType 子类
3. **自定义类型适配器** — 注册 Python 对象和 SQL Server 值之间的转换器
4. **自定义方言扩展** — 向方言添加新的 `format_*()` 方法

## 自定义架构

框架使用**委托 + 组合**模式：

- **表达式**通过委托给其绑定方言的 `format_*()` 方法来生成 SQL
- **DataType**通过委托给 `dialect.format_data_type()` 来生成 DDL SQL
- **方言**由小型、专注的 mixin 组合而成（每个 mixin 为一个功能区域提供 `format_*()` 方法）
- **类型适配器**在 `TypeRegistry` 中注册，用于在 Python 值和数据库值之间进行转换

这意味着你可以在不修改核心库的情况下扩展任何层。

## 何时自定义

| 需求 | 方法 |
|------|------|
| SQL Server 有表达式库中没有的函数 | 自定义表达式 |
| SQL Server 有类型系统中没有的列类型 | 自定义 DataType |
| Python 对象需要自定义序列化 | 自定义类型适配器 |
| 新的 T-SQL 语法需要后端特定格式化 | 自定义方言 Mixin |

## 目录

- [自定义表达式](custom_expressions.md)：创建新的表达式类
- [自定义数据类型](custom_types.md)：定义新的 DataType 子类
- [自定义类型适配器](custom_adapters.md)：注册自定义转换器

## 另请参阅

- [Dialect 表达式](../backend_specific_features/dialect.md) — 表达式系统架构
- [字段类型](../backend_specific_features/field_types.md) — DataType 层次结构
- [类型适配器](../type_adapters/README.md) — 类型转换系统

💡 *AI 提示词：* "如何为表达式库中没有的 T-SQL 函数添加支持？"
