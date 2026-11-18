# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/conftest.py
"""Fixtures for the SQL Server native-type tests.

One table per family (testing plan §4.1), created from ``schema/native_types.sql``
inside the directory's own database (``test_backend_adapters_native``, which
``feature/backend/conftest.py`` creates). A test asks for exactly the tables it
needs, so a failure names the family instead of a shared row.

The helpers here deliberately speak literal SQL for the "foreign data" (S3)
step: a native INSERT must not go through any adapter, which is the whole point
of that assertion.
"""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration
import re
from pathlib import Path

import pytest

from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

DECLARATION = Declaration(
    parallel=True,
    purpose="SQL Server native-type round-trips in the directory-owned database.",
    passes_means="native values survive literal-SQL writes and adapted reads in their column family",
    fails_means="a native type is stored or returned in the wrong form",
)

DML = ExecutionOptions(stmt_type=StatementType.DML)


def _load_native_ddl():
    """Read ``schema/native_types.sql`` into ``{table name: CREATE TABLE ...}``.

    Full-line comments are dropped *before* the statements are split: the
    ROWVERSION note contains a semicolon, and splitting first would cut that
    note in two and leave its tail as if it were SQL.
    """
    text = (Path(__file__).parent / "schema" / "native_types.sql").read_text(encoding="utf-8")
    text = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("--")
    )
    tables = {}
    for chunk in text.split(";"):
        statement = chunk.strip()
        if not statement:
            continue
        match = re.search(r"CREATE\s+TABLE\s+([A-Za-z0-9_]+)", statement, re.IGNORECASE)
        if match is None:
            raise RuntimeError(f"cannot read a table name from: {statement!r}")
        tables[match.group(1)] = statement
    return tables


NATIVE_DDL = _load_native_ddl()


class NativeIO:
    """Literal-SQL helpers shared by the native-type tests."""

    def __init__(self, backend):
        self.backend = backend

    def insert(self, table, row):
        """INSERT one row whose values are already SQL literals.

        No adapter and no parameter binding are involved: this is how a value
        that another writer produced reaches the column.
        """
        columns = ", ".join(row)
        values = ", ".join(row.values())
        self.backend.execute(f"INSERT INTO {table} ({columns}) VALUES ({values})", (), options=DML)

    def raw(self, table, expression, row_id=1):
        """Read one column's stored form through a server expression."""
        row = self.backend.fetch_one(
            f"SELECT {expression} AS v FROM {table} WHERE id = {int(row_id)}", ()
        )
        return row["v"]

    def column_type(self, table, column):
        """The type name SQL Server records for one column."""
        row = self.backend.fetch_one(
            "SELECT typ.name AS v FROM sys.columns col "
            "JOIN sys.types typ ON col.user_type_id = typ.user_type_id "
            "WHERE col.object_id = OBJECT_ID(?) AND col.name = ?",
            (table, column),
        )
        return row["v"]

    def adapter(self, py_type, target_type):
        """The adapter the backend's registry resolves for one pair."""
        return self.backend.adapter_registry.get_adapter(py_type, target_type)


@pytest.fixture
def native_io(sqlserver_backend):
    return NativeIO(sqlserver_backend)


@pytest.fixture
def native_table(sqlserver_backend):
    """Create the named native tables for one test and drop them afterwards.

    The DDL runs on a second connection.  SQL Server answers some DDL with
    informational messages, pyodbc keeps those as pending results, and the
    next command on that connection is then refused with "Connection is busy
    with results for another command" -- which is what a model's first
    ``save()`` hit.  A dedicated DDL connection keeps the test's own
    connection free of them.
    """
    created = []
    ddl = type(sqlserver_backend)(connection_config=sqlserver_backend.config)
    ddl.connect()

    def create(*names):
        for name in names:
            if name not in NATIVE_DDL:
                raise KeyError(f"no DDL declared for {name!r}")
            # ``DROP TABLE IF EXISTS`` on a table that is not there also
            # answers with a message, so the drop only happens when the table
            # really exists.
            exists = ddl.fetch_one("SELECT OBJECT_ID(?) AS v", (name,))["v"]
            if exists is not None:
                ddl.execute(f"DROP TABLE {name}", (), options=DML)
            ddl.execute(NATIVE_DDL[name], (), options=DML)
            created.append(name)
        return names[0] if len(names) == 1 else names

    try:
        yield create
    finally:
        for name in reversed(created):
            ddl.execute(f"DROP TABLE IF EXISTS {name}", (), options=DML)
        ddl.disconnect()


@pytest.fixture
def native_model(sqlserver_backend):
    """Configure model classes against the directory's database."""
    configured = []

    def bind(*model_classes):
        for model_class in model_classes:
            model_class.configure(sqlserver_backend.config, type(sqlserver_backend))
            configured.append(model_class)
        return model_classes[0] if len(model_classes) == 1 else model_classes

    yield bind

    for model_class in configured:
        backend = getattr(model_class, "__backend__", None)
        if backend is not None:
            backend.disconnect()


