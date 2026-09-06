# Timezone Handling

## Overview

The SQL Server backend maintains the original form returned by the database, but for `DATETIMEOFFSET` and `datetime2` values it returns timezone-aware `datetime` objects.

## Difference Between DATETIME and DATETIMEOFFSET

SQL Server has several date/time types with different timezone behavior:

- **DATETIME / DATETIME2**: Store date/time **without timezone information**, similar to "calendar time"
- **DATETIMEOFFSET**: Stores date, time, **and timezone offset** (e.g., `+08:00`)

```sql
-- Create table with specific types
CREATE TABLE events (
    id INT PRIMARY KEY IDENTITY(1,1),
    name NVARCHAR(255),
    created_at DATETIME2,           -- No timezone
    scheduled_at DATETIMEOFFSET     -- With timezone offset
);
```

## Timezone-Aware Adapters

The backend provides separate adapters:

| Adapter | SQL Server Type | Python Result |
|---------|-----------------|---------------|
| `SQLServerDateTimeAdapter` | datetime2, datetime, smalldatetime | `datetime` (naive values treated as UTC) |
| `SQLServerDateTimeOffsetAdapter` | datetimeoffset | `datetime` (timezone-aware) |

The `SQLServerDateTimeOffsetAdapter` ensures the returned `datetime` preserves its timezone offset.

## Python Side Handling

It is recommended to use UTC or local timezone on the Python side:

```python
from datetime import datetime, timezone, timedelta


def to_utc(dt: datetime) -> datetime:
    """Convert to UTC time"""
    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime) -> datetime:
    """Convert to local time"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_tz = datetime.now().astimezone().tzinfo
    return dt.astimezone(local_tz)
```

## datetime2 Precision Normalization

ODBC delivers `datetime2` values as strings with seven fractional digits (100ns precision). The `SQLServerDateTimeAdapter` normalizes these to six digits for Python's `datetime.fromisoformat` and returns them as timezone-aware UTC `datetime` objects:

```python
# ODBC string: '2026-08-09 05:25:26.5205700'
# Python result: datetime(2026, 8, 9, 5, 25, 26, 520570, tzinfo=datetime.timezone.utc)
```

## Best Practices

1. **Store in UTC**: It is recommended to store UTC time in the database
2. **Use DATETIMEOFFSET when needed**: For applications spanning multiple timezones, prefer `DATETIMEOFFSET`
3. **Convert at the frontend**: Perform timezone conversion at the application layer or frontend
4. **Avoid mixing**: Do not mix times from different timezones in the same system

```python
from datetime import datetime, timezone


class Event(ActiveRecord):
    name: str
    scheduled_at: datetime  # DATETIMEOFFSET column

    @property
    def scheduled_at_utc(self) -> datetime:
        if self.scheduled_at.tzinfo is None:
            return self.scheduled_at.replace(tzinfo=timezone.utc)
        return self.scheduled_at.astimezone(timezone.utc)
```

💡 *AI Prompt:* "Why is it recommended to store time in UTC instead of local timezone? When should I use DATETIMEOFFSET?"
