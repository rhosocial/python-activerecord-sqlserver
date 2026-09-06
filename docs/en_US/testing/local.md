# Local SQL Server Testing

## Overview

This section describes how to set up a local SQL Server testing environment using Docker.

## Running SQL Server with Docker

```bash
# Run a SQL Server 2022 container
docker run -d \
  --name sqlserver-test \
  -e ACCEPT_EULA=Y \
  -e MSSQL_SA_PASSWORD='Password123!' \
  -p 1433:1433 \
  mcr.microsoft.com/mssql/server:2022-latest
```

> **Note**: The `ACCEPT_EULA=Y` environment variable is required to accept the SQL Server license terms. The SA password must meet SQL Server's complexity requirements (at least 8 chars, 3 of 4 categories).

## Using Docker Compose

The project provides a `docker-compose.yml` that runs three SQL Server versions on different ports:

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

## Running Tests

```bash
# Set environment variables
export SQLSERVER_HOST=localhost
export SQLSERVER_PORT=1433
export SQLSERVER_DATABASE=test
export SQLSERVER_USER=sa
export SQLSERVER_PASSWORD='Password123!'

# Run tests
PYTHONPATH=tests pytest
```

## Running Testsuite Tests

```bash
cd python-activerecord-sqlserver
PYTHONPATH=tests .venv3.14-ubuntu26.04/bin/pytest \
    ../python-activerecord-testsuite/src/rhosocial/activerecord/testsuite/feature/relation/
```

> **Important**: SQL Server tests must run serially. Do not use `pytest -n auto` or parallel execution.

💡 *AI Prompt:* "What is the difference between Docker and Docker Compose?"
