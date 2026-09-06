# Common Connection Errors

## Overview

This section covers common SQL Server connection errors and their solutions.

## Connection Refused

### Error Message
```
pyodbc.OperationalError: ('08001', '[08001] [Microsoft][ODBC Driver 17 for SQL Server]'
  'SQL Server Network Interfaces: Error Locating Server/Instance Specified')
```

### Causes
- SQL Server service is not running
- Incorrect port (default 1433)
- Firewall blocking port 1433
- Wrong hostname

### Solutions
```bash
# Check if SQL Server is reachable
telnet localhost 1433

# Check the ODBC driver
odbcinst -q -d
```

## Authentication Failed

### Error Message
```
pyodbc.ProgrammingError: ('28000', '[28000] [Microsoft][ODBC Driver 17 for SQL Server]'
  '[SQL Server]Login failed for user \'sa\'.')
```

### Causes
- Incorrect username or password
- SQL Server authentication disabled
- User does not have access to the database

### Solutions
```sql
-- Enable SQL Server authentication (via SSMS or sqlcmd)
-- Create a login and grant access
CREATE LOGIN app_user WITH PASSWORD = 'StrongPassword!';
CREATE USER app_user FOR LOGIN app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON DATABASE::myapp TO app_user;
```

## Encryption/Certificate Error

### Error Message
```
pyodbc.OperationalError: ('08001', '[08001] [Microsoft][ODBC Driver 18 for SQL Server]'
  'SSL Provider: The certificate chain was issued by an authority that is not trusted.')
```

### Causes
- SQL Server uses a self-signed certificate
- Server certificate not trusted by the client

### Solutions
```python
config = SQLServerConnectionConfig(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='secret',
    trust_server_certificate=True,  # Development only
)
```

## Connection Loss and Automatic Recovery

### Overview

The SQL Server backend implements a dual-layer protection mechanism to ensure automatic recovery when connections are lost.

### Connection Error Codes

The backend recognizes these connection error codes for automatic recovery:

| Error Code | Description |
|------------|-------------|
| 53 | SQL Server network name not found |
| 64 | Network connection error |
| 232 | Pipe broken |
| 233 | Connection open/close error |
| 18456 | Login failed |
| 4060 | Cannot open database |
| 40197 | Service error (Azure) |
| 40501 | Service busy (Azure) |
| 40613 | Database unavailable (Azure) |
| 11001 | Host not found |

### Automatic Recovery Mechanism

The backend implements two layers of automatic recovery:

#### Plan A: Pre-Query Connection Check

Before each query execution, the backend checks the connection health with a lightweight `SELECT 1`:

```python
def _get_cursor(self):
    if not self._connection:
        self.connect()
    try:
        cursor = self._connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
    except (PyODBCError, InterfaceError):
        # Connection lost, reconnect
        self.disconnect()
        self.connect()
    return self._connection.cursor()
```

#### Plan B: Ping / Reconnect

Use `ping()` for explicit health checks:

```python
# Check connection status without auto-reconnect
is_alive = backend.ping(reconnect=False)

# Check connection status with auto-reconnect if disconnected
is_alive = backend.ping(reconnect=True)
```

### Best Practices

#### 1. Trust Server Certificate in Development

```python
config = SQLServerConnectionConfig(
    host='localhost',
    database='mydb',
    username='sa',
    password='secret',
    trust_server_certificate=True,  # development only
)
```

#### 2. Multi-Process Worker Scenarios

Each worker process should have its own backend instance:

```python
def worker_process(worker_id, config):
    """Worker process entry point"""
    backend = SQLServerBackend(connection_config=config)
    backend.connect()
    try:
        do_work(backend)
    finally:
        backend.disconnect()
```

💡 *AI Prompt:* "How to troubleshoot SQL Server connection errors? How does the backend automatically recover connections?"
