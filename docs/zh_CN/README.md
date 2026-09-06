# rhosocial-activerecord SQL Server 后端文档

> **AI 学习助手**：本文档中关键概念旁标有 AI 提示词标记。遇到不理解的概念时，可以直接向 AI 助手提问。
>
> **示例：** "SQL Server 后端如何处理 OUTPUT 子句？与 PostgreSQL 的 RETURNING 有什么区别？"

## 目录

1. **[简介](introduction/README.md)**
    *   **[SQL Server 后端概述](introduction/README.md)**: 架构、同步/异步对等和快速示例
    *   **[与核心库的关系](introduction/relationship.md)**: 后端如何与 rhosocial-activerecord 集成
    *   **[支持版本](introduction/supported_versions.md)**: SQL Server、Python 和依赖版本矩阵

2. **[安装与配置](installation_and_configuration/README.md)**
    *   **[安装指南](installation_and_configuration/installation.md)**: pip 安装和驱动设置
    *   **[连接配置](installation_and_configuration/configuration.md)**: 主机、端口、数据库、凭据和高级选项
    *   **[SSL/TLS 配置](installation_and_configuration/ssl.md)**: 安全连接设置
    *   **[连接管理](installation_and_configuration/pool.md)**: 单连接生命周期、连接池支持和 FastAPI 模式
    *   **[字符集/编码](installation_and_configuration/charset.md)**: 编码配置和最佳实践

3. **[SQL Server 特定功能](backend_specific_features/README.md)**
    *   **[字段类型](backend_specific_features/field_types.md)**: SQL Server 特定数据类型（NVARCHAR、DATETIME2、HIERARCHYID 等）
    *   **[Dialect 表达式](backend_specific_features/dialect.md)**: T-SQL 语法、运算符、函数和 DDL 扩展
    *   **[索引](backend_specific_features/indexing.md)**: 索引类型、创建和优化策略
    *   **[EXPLAIN](backend_specific_features/explain.md)**: 查询执行计划分析
    *   **[内省](backend_specific_features/introspection.md)**: 数据库元数据查询和架构检查
    *   **[分区](backend_specific_features/partition.md)**: 表分区策略和生命周期管理

4. **[DDL 操作](ddl/README.md)**
    *   **[DDL 概览](ddl/README.md)**: 架构管理、支持的操作和后端特定 DDL 扩展

5. **[事务支持](transaction_support/README.md)**
    *   **[事务概览](transaction_support/README.md)**: 事务管理器 API 和保存点
    *   **[隔离级别](transaction_support/isolation_level.md)**: SQL Server 特定的隔离语义
    *   **[保存点](transaction_support/savepoint.md)**: 嵌套事务和条件回滚
    *   **[死锁处理](transaction_support/deadlock.md)**: SQL Server 死锁检测、错误代码和重试策略

6. **[类型适配器](type_adapters/README.md)**
    *   **[类型映射](type_adapters/mapping.md)**: SQL Server 到 Python 类型转换表
    *   **[自定义适配器](type_adapters/custom.md)**: 使用自定义适配器扩展类型支持
    *   **[时区处理](type_adapters/timezone.md)**: DATETIMEOFFSET 和时区配置

7. **[测试](testing/README.md)**
    *   **[测试配置](testing/configuration.md)**: SQL Server 特定的测试设置
    *   **[本地测试](testing/local.md)**: 基于 Docker 的本地测试环境

8. **[故障排除](troubleshooting/README.md)**
    *   **[连接错误](troubleshooting/connection.md)**: 错误代码、诊断和自动恢复
    *   **[性能问题](troubleshooting/performance.md)**: 慢查询分析和优化

9. **[场景实战](scenarios/README.md)**
    *   **[并行 Worker](scenarios/parallel_workers.md)**: SQL Server 特定的并发特性和模式

10. **[自定义](customization/README.md)**
    *   **[自定义表达式](customization/custom_expressions.md)**: 为 T-SQL 语法创建新的表达式类
    *   **[自定义数据类型](customization/custom_types.md)**: 为自定义列类型定义新的 DataType 子类
    *   **[自定义类型适配器](customization/custom_adapters.md)**: 注册 Python 和 SQL Server 值之间的自定义转换器

11. **[命令行界面](cli/README.md)**
    *   **[CLI 概览](cli/README.md)**: 查询、内省和管理 SQL Server 的命令

> **核心库文档**：要了解 ActiveRecord 框架的完整功能（建模、查询、关系、性能、Worker 池），请参考 [rhosocial-activerecord 文档](https://github.com/Rhosocial/python-activerecord/tree/main/docs/zh_CN)。
