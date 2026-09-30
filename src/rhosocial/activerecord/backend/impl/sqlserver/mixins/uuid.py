# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/uuid.py
"""SQL Server UUID value expressions.

T-SQL has no ``gen_random_uuid()``. Its equivalent is ``NEWID()``, which has
existed since SQL Server 2005 and needs no extension, so unlike PostgreSQL
there is nothing version-dependent to resolve here.
"""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.uuid import (
        UUIDCastExpression,
        UUIDGenerationExpression,
    )


class SQLServerUUIDMixin:
    """UUID value support for SQL Server.

    Generation, the nil/max constants and casting are all fixed spellings
    here, so they sit in the inherited ``UUID_SQL`` table and need no
    overridden formatter.
    """

    UUID_SQL = {
        "generation": "NEWID()",
        "constant": {
            "nil": "CAST('00000000-0000-0000-0000-000000000000' AS UNIQUEIDENTIFIER)",
            "max": "CAST('ffffffff-ffff-ffff-ffff-ffffffffffff' AS UNIQUEIDENTIFIER)",
        },
        "cast": "CAST({inner} AS UNIQUEIDENTIFIER)",
    }

    def supports_uuid_generation(self) -> bool:
        """Whether the server can generate a UUID.

        True on every supported version: ``NEWID()`` shipped with SQL Server
        2005 and is a core function. The version gate is kept explicit rather
        than returning a constant so the answer has one place to change if a
        future deprecation lands.
        """
        return self.version >= (9, 0, 0)


__all__ = ["SQLServerUUIDMixin"]
