# 测试

本节介绍 sqlserver 后端的测试。

## 目录

- [测试配置](configuration.md)：SQL Server 特定的测试设置
- [本地测试](local.md)：基于 Docker 的本地测试环境

## 测试原则

### 同步/异步对等

所有具有 IO 操作的后端必须为等效场景准备**配对的同步和异步测试**：

```python
# 同步测试
def test_create_user():
    user = User(name="Alice").create()
    assert user.id is not None

# 异步测试 — 相同逻辑，异步 API
async def test_async_create_user():
    user = await AsyncUser(name="Alice").create()
    assert user.id is not None
```

如果后端仅支持同步或仅支持异步，则只准备相应的测试。

### 表达式类 — 无 IO

表达式测试不涉及数据库 IO——它们只构建 SQL 并验证生成的 SQL：

```python
def test_expression_sql():
    expr = Eq(User.name, "Alice")
    assert expr.to_sql(dialect) == "[name] = ?"
    assert expr.params == ["Alice"]
```

表达式测试不需要异步对应测试。

### ActiveRecord 测试 — 使用测试套件

ActiveRecord 功能测试（模型 CRUD、关系、查询）使用**测试套件**：

```
python-activerecord-testsuite/
└── src/rhosocial/activerecord/testsuite/feature/
    ├── basic/      # 级别 1 — 必须首先通过
    ├── relation/   # 级别 1 — 必须首先通过
    ├── query/      # 级别 1 — 必须首先通过
    ├── events/     # 级别 2 — 扩展行为
    ├── mixins/     # 级别 2
    ├── interface/  # 级别 2
    └── examples/   # 级别 2
```

每个后端提供**提供者实现**，将测试连接到其特定数据库。测试逻辑是共享的；只有提供者层在每个后端之间变化。

**运行测试套件测试：**

```bash
cd python-activerecord-sqlserver
PYTHONPATH=tests .venv3.14-ubuntu26.04/bin/pytest \
    ../python-activerecord-testsuite/src/rhosocial/activerecord/testsuite/feature/relation/
```

### 测试类别摘要

| 测试内容 | 方法 | IO？ | 异步？ |
|---------|------|------|--------|
| 表达式类（方言 SQL 生成） | 单元测试，无数据库 | 否 | 否 |
| 类型适配器（类型转换） | 单元测试，无数据库 | 否 | 否 |
| 命名功能（连接、表达式、过程、迁移） | 后端 CLI 脚本 | 是 | 如果支持 |
| ActiveRecord 功能（CRUD、关系、查询） | 测试套件 + 提供者 | 是 | 是 |
| 后端特定功能（唯一类型、语法） | 项目特定测试 | 是 | 是 |

### SQL Server 测试注意事项

- **测试必须串行运行** — 不要使用 `pytest -n auto` 或并行执行
- SQL Server 使用 `?` 作为参数占位符（pyodbc 约定）
- `SQLServerUnicodeDialect` 将 VARCHAR/CHAR 渲染为 NVARCHAR/NCHAR，以兼容 Unicode 测试数据

## 另请参阅

- [核心后端测试指南](backend_testing.md)
- [核心测试套件提供者指南](provider_guide.md)
