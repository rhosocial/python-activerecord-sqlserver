# 测试配置

## 概述

本节介绍如何配置 SQL Server 后端的测试环境。

有关通用测试策略（DummyBackend、SQLite 集成测试），请参阅[核心后端测试指南](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/testing/backend_testing.md)。

## 使用 SQL Server 后端进行端到端测试

为了完整测试 SQL Server 行为，请使用 SQL Server 后端：

```python
import os
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig


class User(ActiveRecord):
    name: str
    email: str

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'users'


# 从环境变量读取配置
config = SQLServerConnectionConfig(
    host=os.environ.get('SQLSERVER_HOST', 'localhost'),
    port=int(os.environ.get('SQLSERVER_PORT', 1433)),
    database=os.environ.get('SQLSERVER_DATABASE', 'test'),
    username=os.environ.get('SQLSERVER_USER', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', ''),
    trust_server_certificate=True,  # 仅限开发
)
User.configure(config, SQLServerBackend)
```

## 测试 Fixture

```python
import pytest
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig


@pytest.fixture
def sqlserver_config():
    return SQLServerConnectionConfig(
        host='localhost',
        port=1433,
        database='test',
        username='sa',
        password='Password123!',
        trust_server_certificate=True,
    )


@pytest.fixture
def sqlserver_backend(sqlserver_config):
    backend = SQLServerBackend(connection_config=sqlserver_config)
    backend.connect()
    yield backend
    backend.disconnect()


def test_connection(sqlserver_backend):
    version = sqlserver_backend.get_server_version()
    assert version is not None
```

## 基于场景的配置

SQL Server 测试套件使用 YAML 场景文件，这些文件映射到正在运行的 SQL Server 实例：

```yaml
# tests/config/sqlserver_scenarios.yaml
scenarios:
  sqlserver_2019:
    host: localhost
    port: 11433
    username: sa
    password: Password123!
    trust_server_certificate: true

  sqlserver_2022:
    host: localhost
    port: 11434
    username: sa
    password: Password123!
    trust_server_certificate: true

  sqlserver_2025:
    host: localhost
    port: 11435
    username: sa
    password: Password123!
    trust_server_certificate: true
```

设置 `SQLSERVER_SCENARIOS_CONFIG_PATH` 指向场景文件，否则默认使用 `tests/config/sqlserver_scenarios.yaml`。

## 测试注意事项

- **测试必须串行运行** —— 不要使用 `pytest -n auto` 或并行执行
- SQL Server 使用 `?` 作为参数占位符（pyodbc 约定）
- `SQLServerUnicodeDialect` 将 VARCHAR/CHAR 渲染为 NVARCHAR/NCHAR，以保证与 Unicode 测试数据的兼容性

💡 *AI 提示词：* "单元测试、集成测试和端到端测试之间有什么区别？"
