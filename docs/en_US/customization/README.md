# Customization

## Overview

rhosocial-activerecord is designed to be extensible. You can customize the framework at several levels:

1. **Custom Expressions** — Create new expression classes for T-SQL syntax
2. **Custom Data Types** — Define new DataType subclasses for custom column types
3. **Custom Type Adapters** — Register converters between Python objects and SQL Server values
4. **Custom Dialect Extensions** — Add new `format_*()` methods to the dialect

## Customization Architecture

The framework uses a **delegation + composition** pattern:

- **Expressions** produce SQL by delegating to their bound dialect's `format_*()` methods
- **DataTypes** produce DDL SQL by delegating to `dialect.format_data_type()`
- **Dialects** are composed from small, focused mixins (each providing `format_*()` methods for one feature area)
- **Type Adapters** convert between Python values and database values, registered in `TypeRegistry`

This means you can extend any layer without modifying the core library.

## When to Customize

| Need | Approach |
|------|----------|
| SQL Server has a function not in the expression library | Custom Expression |
| SQL Server has a column type not in the type system | Custom DataType |
| Python object needs custom serialization | Custom Type Adapter |
| New T-SQL syntax needs backend-specific formatting | Custom Dialect Mixin |

## Contents

- [Custom Expressions](custom_expressions.md): Creating new expression classes
- [Custom Data Types](custom_types.md): Defining new DataType subclasses
- [Custom Type Adapters](custom_adapters.md): Registering custom converters

## See Also

- [Dialect Expressions](../backend_specific_features/dialect.md) — expression system architecture
- [Field Types](../backend_specific_features/field_types.md) — DataType hierarchy
- [Type Adapters](../type_adapters/README.md) — type conversion system

💡 *AI Prompt:* "How do I add support for a T-SQL function that isn't in the expression library?"
