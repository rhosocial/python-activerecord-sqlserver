# Character Set and Collation

## Overview

SQL Server supports Unicode and non-Unicode character types. Correctly configuring character types and collations is essential for handling multilingual text, emojis, and ensuring sorting behavior meets expectations.

## Character Types

| Type | Encoding | Unicode | Notes |
|------|----------|---------|-------|
| CHAR | Single-byte codepage | ❌ | Fixed-length, non-Unicode |
| VARCHAR | Single-byte codepage | ❌ | Variable-length, non-Unicode |
| NCHAR | UTF-16 | ✅ | Fixed-length, Unicode |
| NVARCHAR | UTF-16 | ✅ | Variable-length, Unicode (recommended) |
| NVARCHAR(MAX) | UTF-16 | ✅ | Unicode large object (up to 2GB) |

⚠️ **Important**: Non-Unicode `VARCHAR`/`CHAR` types silently replace characters outside the server's codepage with `?`. For full multilingual and emoji support, always use `NVARCHAR`/`NCHAR`.

## Collations

Collations in SQL Server control sorting and comparison rules, combining multiple suffixes:

### Common Collations

| Collation | Description |
|-----------|-------------|
| SQL_Latin1_General_CP1_CI_AS | Legacy default, case-insensitive, accent-sensitive |
| Latin1_General_CI_AS | Modern, case-insensitive, accent-sensitive |
| Latin1_General_CS_AS | Case-sensitive, accent-sensitive |
| Chinese_PRC_CI_AS | Chinese Simplified, case-insensitive |
| Japanese_CI_AS | Japanese, case-insensitive |

## Collation Suffix Meanings

| Suffix | Meaning |
|--------|---------|
| _CI | Case Insensitive |
| _CS | Case Sensitive |
| _AI | Accent Insensitive |
| _AS | Accent Sensitive |
| _BIN | Binary sort order |
| _KS | Kana Sensitive |

## Configuration Methods

### 1. Connection-Level (Character Set)

Specify the character encoding for the ODBC connection:

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

backend = SQLServerBackend(
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    charset='UTF-8',   # Default is UTF-8
)
```

### 2. Database-Level Collation

```sql
CREATE DATABASE myapp COLLATE Latin1_General_CI_AS;
```

### 3. Column-Level Configuration

```sql
CREATE TABLE users (
    id INT PRIMARY KEY IDENTITY(1,1),
    name NVARCHAR(255) COLLATE Latin1_General_CI_AS,
    bio NVARCHAR(MAX)
);
```

## Best Practices

1. **Use NVARCHAR for text**: Prefer Unicode `NVARCHAR` over `VARCHAR` to avoid data loss with multilingual or emoji content
2. **Keep charset as UTF-8**: The default `charset='UTF-8'` works with modern pyodbc drivers
3. **Choose collation carefully**: Match collation to your sorting requirements (case-sensitive vs insensitive, language)
4. **Be consistent**: Use the same collation across a column to avoid implicit conversion performance issues

💡 *AI Prompt:* "What is the difference between VARCHAR and NVARCHAR in SQL Server? When should I use NVARCHAR?"
