# rhosocial-activerecord-sqlserver

SQL Server backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord).

## Documentation / 文档

Please select your language / 请选择语言：

- [English Documentation](en_US/README.md)
- [中文文档 (Chinese)](zh_CN/README.md)

## Overview

The SQL Server backend brings the ActiveRecord pattern to Microsoft SQL Server through the
`pyodbc` driver. It supports `OUTPUT` in place of `RETURNING`, temporal tables,
memory-optimized and columnstore tables, and SQL Server's two-part
`<schema>.<object>` naming rules.

For the main ActiveRecord framework documentation, please visit the
[python-activerecord docs](https://github.com/rhosocial/python-activerecord/tree/docs/docs).