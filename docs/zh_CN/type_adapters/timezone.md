# 时区处理

## 概述

SQL Server 后端保持数据库返回的原始形式，但对于 `DATETIMEOFFSET` 和 `datetime2` 值，它返回时区感知的 `datetime` 对象。

## DATETIME 和 DATETIMEOFFSET 的区别

SQL Server 有几种时区行为不同的日期/时间类型：

- **DATETIME / DATETIME2**：存储**不含时区信息**的日期/时间，类似于"日历时间"
- **DATETIMEOFFSET**：存储日期、时间**和时区偏移**（例如 `+08:00`）

```sql
-- 创建具有特定类型的表
CREATE TABLE events (
    id INT PRIMARY KEY IDENTITY(1,1),
    name NVARCHAR(255),
    created_at DATETIME2,           -- 无时区
    scheduled_at DATETIMEOFFSET     -- 带时区偏移
);
```

## 时区感知适配器

后端提供单独的适配器：

| 适配器 | SQL Server 类型 | Python 结果 |
|---------|-----------------|---------------|
| `SQLServerDateTimeAdapter` | datetime2, datetime, smalldatetime | `datetime`（naive 值视为 UTC） |
| `SQLServerDateTimeOffsetAdapter` | datetimeoffset | `datetime`（时区感知） |

`SQLServerDateTimeOffsetAdapter` 确保返回的 `datetime` 保留其时区偏移。

## Python 端处理

建议在 Python 端使用 UTC 或本地时区：

```python
from datetime import datetime, timezone, timedelta


def to_utc(dt: datetime) -> datetime:
    """转换为 UTC 时间"""
    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime) -> datetime:
    """转换为本地时间"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_tz = datetime.now().astimezone().tzinfo
    return dt.astimezone(local_tz)
```

## datetime2 精度规范化

ODBC 以带七位小数位（100ns 精度）的字符串形式传递 `datetime2` 值。`SQLServerDateTimeAdapter` 会将它们规范化为六位以适配 Python 的 `datetime.fromisoformat`，并返回时区感知的 UTC `datetime` 对象：

```python
# ODBC 字符串: '2026-08-09 05:25:26.5205700'
# Python 结果: datetime(2026, 8, 9, 5, 25, 26, 520570, tzinfo=datetime.timezone.utc)
```

## 最佳实践

1. **以 UTC 存储**：建议在数据库中存储 UTC 时间
2. **需要时使用 DATETIMEOFFSET**：对于跨多个时区的应用，优先使用 `DATETIMEOFFSET`
3. **在前端转换**：在应用程序层或前端进行时区转换
4. **避免混用**：不要在同一系统中混用不同时区的时间

```python
from datetime import datetime, timezone


class Event(ActiveRecord):
    name: str
    scheduled_at: datetime  # DATETIMEOFFSET 列

    @property
    def scheduled_at_utc(self) -> datetime:
        if self.scheduled_at.tzinfo is None:
            return self.scheduled_at.replace(tzinfo=timezone.utc)
        return self.scheduled_at.astimezone(timezone.utc)
```

💡 *AI 提示词：* "为什么建议以 UTC 而不是本地时区存储时间？我什么时候应该使用 DATETIMEOFFSET？"
