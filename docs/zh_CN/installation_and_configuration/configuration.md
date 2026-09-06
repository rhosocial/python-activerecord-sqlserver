# 连接配置

## 基本配置选项

| 参数 | 类型 | 默认值 | 描述 |
|-----------|------|---------|-------------|
| host | str | localhost | SQL Server 主机名或 IP |
| port | int | 1433 | SQL Server 端口 |
| database | str | - | 数据库名称 |
| username | str | - | 用户名（SQL 身份验证） |
| password | str | - | 密码（SQL 身份验证） |
| trusted_connection | bool | False | 使用 Windows 身份验证 |
| driver | str | ODBC Driver 17 for SQL Server | ODBC 驱动名称 |
| encrypt | bool | True | 加密连接 |
| trust_server_certificate | bool | False | 信任服务器证书 |
| timeout | int | 30 | 连接超时（秒） |
| query_timeout | int | 0 | 查询超时（0 = 无限制） |
| autocommit | bool | True | 自动提交模式 |
| charset | str | UTF-8 | 字符编码 |
| pool_size | int | 5 | 预留的连接池大小 |
| pool_timeout | int | 30 | 预留的连接池超时 |

## 高级配置选项

```python
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

config = SQLServerConnectionConfig(
    # 基本配置
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='mypassword',

    # 身份验证
    trusted_connection=False,

    # SSL/加密
    driver='ODBC Driver 18 for SQL Server',
    encrypt=True,
    trust_server_certificate=False,

    # 超时
    timeout=30,
    query_timeout=60,
    autocommit=True,

    # 编码
    charset='UTF-8',
)
```

## 身份验证模式

### SQL Server 身份验证

```python
config = SQLServerConnectionConfig(
    host='localhost',
    database='myapp',
    username='sa',
    password='secret',
)
```

### Windows 身份验证

```python
config = SQLServerConnectionConfig(
    host='localhost',
    database='myapp',
    trusted_connection=True,
)
```

## 使用 YAML 配置

```yaml
# sqlserver_scenarios.yaml
scenarios:
  production:
    host: db.example.com
    port: 1433
    database: myapp_prod
    username: app_user
    password: ${SQLSERVER_PASSWORD}
    encrypt: true
    autocommit: true

  development:
    host: localhost
    port: 1433
    database: myapp_dev
    username: sa
    password: dev_password
    encrypt: false
    autocommit: true
```

## 连接字符串

配置可以直接构建 ODBC 连接字符串：

```python
conn_str = config.build_connection_string()
# DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=myapp;UID=sa;PWD=mypassword;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30
```

💡 *AI 提示词：* "SQL Server 身份验证和 Windows 身份验证（受信任连接）有什么区别？"
