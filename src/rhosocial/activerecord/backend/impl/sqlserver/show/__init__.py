# src/rhosocial/activerecord/backend/impl/sqlserver/show/__init__.py
"""
SQL Server SHOW compatibility module.

SQL Server has no ``SHOW ...`` statement, so this package carries no SQL at
all: it is the *inbound* half of the MySQL vocabulary -- it reads result rows
whose column names follow MySQL's SHOW spellings and turns them into the typed
result dataclasses the shared ``show()`` API returns. There is nothing here to
route through an expression node, because nothing here builds a statement;
whoever needs the rows asks the catalogue through nodes
(``..query_nodes``) and hands the result to these parsers.

Usage:
    from rhosocial.activerecord.backend.impl.sqlserver.show.functionality import (
        SQLServerShowFunctionality,
    )

    show = SQLServerShowFunctionality(backend)
    columns = show._parse_columns_result(result)
"""

from .functionality import SQLServerShowFunctionality

__all__ = [
    "SQLServerShowFunctionality",
]
