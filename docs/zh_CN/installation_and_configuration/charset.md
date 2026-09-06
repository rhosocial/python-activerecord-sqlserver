# 字符集和排序规则

## 概述

SQL Server 支持 Unicode 和非 Unicode 字符类型。正确配置字符类型和排序规则对于处理多语言文本、表情符号以及确保排序行为符合预期至关重要。

## 字符类型

| 类型 | 编码 | Unicode | 说明 |
|------|----------|---------|-------|
| CHAR | 单字节代码页 | ❌ | 固定长度，非 Unicode |
| VARCHAR | 单字节代码页 | ❌ | 可变长度，非 Unicode |
| NCHAR | UTF-16 | ✅ | 固定长度，Unicode |
| NVARCHAR | UTF-16 | ✅ | 可变长度，Unicode（推荐） |
| NVARCHAR(MAX) | UTF-16 | ✅ | Unicode 大对象（最大 2GB） |

⚠️ **重要**：非 Unicode 的 `VARCHAR`/`CHAR` 类型会将服务器代码页之外的所有字符静默替换为 `?`。要获得完整的多语言和表情符号支持，请始终使用 `NVARCHAR`/`NCHAR`。

## 排序规则

SQL Server 中的排序规则控制排序和比较规则，组合多个后缀：

### 常用排序规则

| 排序规则 | 描述 |
|-----------|-------------|
| SQL_Latin1_General_CP1_CI_AS | 传统默认值，不区分大小写，区分重音 |
| Latin1_General_CI_AS | 现代，不区分大小写，区分重音 |
| Latin1_General_CS_AS | 区分大小写，区分重音 |
| Chinese_PRC_CI_AS | 简体中文，不区分大小写 |
| Japanese_CI_AS | 日语，不区分大小写 |

## 排序规则后缀含义

| 后缀 | 含义 |
|--------|---------|
| _CI | 不区分大小写 |
| _CS | 区分大小写 |
| _AI | 不区分重音 |
| _AS | 区分重音 |
| _BIN | 二进制排序顺序 |
| _KS | 假名敏感 |

## 配置方法

### 1. 连接级别（字符集）

为 ODBC 连接指定字符编码：

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

backend = SQLServerBackend(
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    charset='UTF-8',   # 默认是 UTF-8
)
```

### 2. 数据库级别排序规则

```sql
CREATE DATABASE myapp COLLATE Latin1_General_CI_AS;
```

### 3. 列级别配置

```sql
CREATE TABLE users (
    id INT PRIMARY KEY IDENTITY(1,1),
    name NVARCHAR(255) COLLATE Latin1_General_CI_AS,
    bio NVARCHAR(MAX)
);
```

## 最佳实践

1. **文本使用 NVARCHAR**：优先使用 Unicode `NVARCHAR` 而不是 `VARCHAR`，以避免多语言或表情符号内容的数据丢失
2. **保持字符集为 UTF-8**：默认的 `charset='UTF-8'` 适用于现代 pyodbc 驱动
3. **仔细选择排序规则**：将排序规则与你的排序需求匹配（区分大小写 vs 不区分，语言）
4. **保持一致**：在一列上使用相同的排序规则，以避免隐式转换带来的性能问题

💡 *AI 提示词：* "SQL Server 中 VARCHAR 和 NVARCHAR 有什么区别？我什么时候应该使用 NVARCHAR？"
