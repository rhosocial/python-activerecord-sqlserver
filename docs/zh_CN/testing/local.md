# 本地 SQL Server 测试

## 概述

本节介绍如何使用 Docker 搭建本地 SQL Server 测试环境。

## 使用 Docker 运行 SQL Server

```bash
# 运行 SQL Server 2022 容器
docker run -d \
  --name sqlserver-test \
  -e ACCEPT_EULA=Y \
  -e MSSQL_SA_PASSWORD='Password123!' \
  -p 1433:1433 \
  mcr.microsoft.com/mssql/server:2022-latest
```

> **注意**：`ACCEPT_EULA=Y` 环境变量用于接受 SQL Server 许可条款。SA 密码必须满足 SQL Server 的复杂度要求（至少 8 个字符，涵盖 4 种类别中的 3 种）。

## 使用 Docker Compose

项目提供了 `docker-compose.yml`，可在不同端口上运行三个 SQL Server 版本：

```yaml
# docker-compose.yml
services:
  sqlserver_2019:
    image: mcr.microsoft.com/mssql/server:2019-latest
    ports:
      - "11433:1433"
    environment:
      ACCEPT_EULA: Y
      MSSQL_SA_PASSWORD: Password123!

  sqlserver_2022:
    image: mcr.microsoft.com/mssql/server:2022-latest
    ports:
      - "11434:1433"
    environment:
      ACCEPT_EULA: Y
      MSSQL_SA_PASSWORD: Password123!

  sqlserver_2025:
    image: mcr.microsoft.com/mssql/server:2025-latest
    ports:
      - "11435:1433"
    environment:
      ACCEPT_EULA: Y
      MSSQL_SA_PASSWORD: Password123!
```

```bash
docker-compose up -d
```

## 运行测试

```bash
# 设置环境变量
export SQLSERVER_HOST=localhost
export SQLSERVER_PORT=1433
export SQLSERVER_DATABASE=test
export SQLSERVER_USER=sa
export SQLSERVER_PASSWORD='Password123!'

# 运行测试
PYTHONPATH=tests pytest
```

## 运行 Testsuite 测试

```bash
cd python-activerecord-sqlserver
PYTHONPATH=tests .venv3.14-ubuntu26.04/bin/pytest \
    ../python-activerecord-testsuite/src/rhosocial/activerecord/testsuite/feature/relation/
```

> **重要**：SQL Server 测试必须串行运行。不要使用 `pytest -n auto` 或并行执行。

💡 *AI 提示词：* "Docker 和 Docker Compose 之间有什么区别？"
