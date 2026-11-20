# docs/examples/02_declarative_model_crud.py
"""Declarative ActiveRecord model backed by SQL Server.

This script binds a model to this backend, creates its table, saves a row and
runs a typed query. It also previews the generated T-SQL without executing it.
Run against a scratch database (see docs/examples/README.md).
"""
import os
from typing import Annotated, ClassVar

from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import SQLServerNVarCharType
from rhosocial.activerecord.base import FieldProxy, UseSqlType
from rhosocial.activerecord.field import DefaultTimestampMixin, IntegerPKMixin
from rhosocial.activerecord.model import ActiveRecord


class User(IntegerPKMixin, DefaultTimestampMixin, ActiveRecord):
    """A SQL Server-backed model using Unicode text columns.

    ``IntegerPKMixin`` renders the auto-increment key as ``INT IDENTITY`` on
    this backend, and ``SQLServerNVarCharType`` pins the columns to ``NVARCHAR``
    rather than the collation-dependent ``VARCHAR``.
    """

    c: ClassVar[FieldProxy] = FieldProxy()

    name: Annotated[str, UseSqlType(SQLServerNVarCharType(length=100))]
    email: Annotated[str, UseSqlType(SQLServerNVarCharType(length=255))]
    age: int = 0

    @classmethod
    def table_name(cls) -> str:
        return "example_users"


def main() -> None:
    config = SQLServerConnectionConfig(
        host=os.environ.get("SQLSERVER_HOST", "localhost"),
        port=int(os.environ.get("SQLSERVER_PORT", "1433")),
        database=os.environ.get("SQLSERVER_DATABASE", "test_db"),
        username=os.environ.get("SQLSERVER_USERNAME", "sa"),
        password=os.environ.get("SQLSERVER_PASSWORD", ""),
        driver=os.environ.get("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
    )

    # Bind the model to this backend and create the table from the declaration.
    User.configure(config, SQLServerBackend)
    User.create_table()

    # Create: the key is assigned by SQL Server and returned via OUTPUT.
    alice = User(name="Alice", email="alice@example.com", age=30)
    alice.save()
    print("Inserted id:", alice.id)

    # Query with the type-safe field proxy.
    adults = User.query().where(User.c.age >= 18).all()
    print("Adults:", [user.name for user in adults])

    # Preview the generated T-SQL before it runs.
    sql, params = User.query().where(User.c.age >= 18).to_sql()
    print("SQL:", sql)
    print("Params:", params)


if __name__ == "__main__":
    main()
