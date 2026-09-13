# src/rhosocial/activerecord/backend/impl/sqlserver/reserved_words.py
"""
SQL Server reserved words list.

Source: SQL Server 2022 Documentation
"""

SQLSERVER_RESERVED_WORDS = frozenset({
    "add", "all", "alter", "and", "any", "as", "asc", "authorization",
    "between", "bigint", "binary", "bit", "both", "break", "browse",
    "bulk", "by", "cascade", "case", "cast", "catch", "char",
    "character", "check", "checkpoint", "close", "clustered", "coalesce",
    "collate", "column", "commit", "compute", "constraint", "contains",
    "containstable", "continue", "convert", "create", "cross", "current",
    "current_date", "current_time", "current_timestamp", "current_user",
    "cursor", "date", "day", "dbcc", "deallocate", "dec", "decimal",
    "declare", "default", "delete", "deny", "desc", "disk", "distinct",
    "distributed", "double", "drop", "dump", "else", "end", "errlvl",
    "except", "exec", "execute", "exists", "exit", "external", "fetch",
    "file", "fillfactor", "float", "for", "foreign", "freetext",
    "freetexttable", "from", "full", "function", "goto", "grant", "group",
    "having", "holdlock", "identity", "if", "in", "index", "inner",
    "insert", "int", "integer", "intersect", "into", "is", "isnull",
    "join", "key", "kill", "left", "like", "lineno", "load", "merge",
    "national", "natural", "next", "nocheck", "nonclustered", "not",
    "null", "nullif", "of", "off", "offsets", "on", "only", "open",
    "option", "or", "order", "outer", "over", "percent", "pivot",
    "plan", "primary", "print", "proc", "procedure", "public", "raiserror",
    "read", "reconfigure", "references", "replication", "restore", "restrict",
    "return", "revert", "revoke", "right", "rollback", "rowcount",
    "rowguidcol", "rule", "save", "schema", "select", "session_user",
    "set", "setuser", "shutdown", "some", "static", "statistics", "sum",
    "system_user", "table", "tablesample", "text", "then", "time",
    "timestamp", "to", "top", "tran", "transaction", "trigger", "truncate",
    "try", "tsequal", "union", "unique", "unpivot", "update", "updatetext",
    "user", "using", "values", "varying", "view", "waitfor", "when",
    "where", "while", "with", "writetext",
})
