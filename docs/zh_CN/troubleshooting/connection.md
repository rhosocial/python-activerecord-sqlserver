# 常见连接错误

## 概述

本节介绍常见的 SQL Server 连接错误及其解决方案。

## 连接被拒绝

### 错误消息
```
pyodbc.OperationalError: ('08001', '[08001] [Microsoft][ODBC Driver 17 for SQL Server]'
  'SQL Server Network Interfaces: Error Locating Server/Instance Specified')
```

### 原因
- SQL Server 服务未运行
- 端口错误（默认 1433）
- 防火墙阻止了端口 1433
- 主机名错误

### 解决方案
```bash
# 检查 SQL Server 是否可访问
telnet localhost 1433

# 检查 ODBC 驱动
odbcinst -q -d
```

## 身份验证失败

### 错误消息
```
pyodbc.ProgrammingError: ('28000', '[28000] [Microsoft][ODBC Driver 17 for SQL Server]'
  '[SQL Server]Login failed for user \'sa\'.')
```

### 原因
- 用户名或密码错误
- 禁用了 SQL Server 身份验证
- 用户没有访问数据库的权限

### 解决方案
```sql
-- 启用 SQL Server 身份验证（通过 SSMS 或 sqlcmd）
-- 创建登录并授予访问权限
CREATE LOGIN app_user WITH PASSWORD = 'StrongPassword!';
CREATE USER app_user FOR LOGIN app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON DATABASE::myapp TO app_user;
```

## 加密/证书错误

### 错误消息
```
pyodbc.OperationalError: ('08001', '[08001] [Microsoft][ODBC Driver 18 for SQL Server]'
  'SSL Provider: The certificate chain was issued by an authority that is not trusted.')
```

### 原因
- SQL Server 使用自签名证书
- 客户端不信任服务器证书

### 解决方案
```python
config = SQLServerConnectionConfig(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='secret',
    trust_server_certificate=True,  # 仅限开发
)
```

## 连接丢失与自动恢复

### 概述

SQL Server 后端实现了双层的保护机制，确保在连接丢失时自动恢复。

### 连接错误代码

后端识别以下连接错误代码以进行自动恢复：

| 错误代码 | 描述 |
|------------|-------------|
| 53 | 找不到 SQL Server 网络名称 |
| 64 | 网络连接错误 |
| 232 | 管道已断开 |
| 233 | 连接打开/关闭错误 |
| 18456 | 登录失败 |
| 4060 | 无法打开数据库 |
| 40197 | 服务错误（Azure） |
| 40501 | 服务繁忙（Azure） |
| 40613 | 数据库不可用（Azure） |
| 11001 | 找不到主机 |

### 自动恢复机制

后端实现了两层的自动恢复：

#### 方案 A：查询前连接检查

在每次查询执行前，后端使用轻量级的 `SELECT 1` 检查连接健康状态：

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
        # 连接丢失，重新连接
        self.disconnect()
        self.connect()
    return self._connection.cursor()
```

#### 方案 B：Ping / 重新连接

使用 `ping()` 进行显式的健康检查：

```python
# 检查连接状态，不自动重新连接
is_alive = backend.ping(reconnect=False)

# 检查连接状态，断开时自动重新连接
is_alive = backend.ping(reconnect=True)
```

### 最佳实践

#### 1. 在开发中信任服务器证书

```python
config = SQLServerConnectionConfig(
    host='localhost',
    database='mydb',
    username='sa',
    password='secret',
    trust_server_certificate=True,  # 仅限开发
)
```

#### 2. 多进程 Worker 场景

每个 worker 进程应有自己的后端实例：

```python
def worker_process(worker_id, config):
    """Worker 进程入口点"""
    backend = SQLServerBackend(connection_config=config)
    backend.connect()
    try:
        do_work(backend)
    finally:
        backend.disconnect()
```

💡 *AI 提示词：* "如何排查 SQL Server 连接错误？后端如何自动恢复连接？"
