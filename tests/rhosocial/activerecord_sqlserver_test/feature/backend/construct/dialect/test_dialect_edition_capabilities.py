# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/dialect/test_dialect_edition_capabilities.py
"""Edition-gated capability answers, fully offline.

Table partitioning (partition functions/schemes) and ``ONLINE`` index creation
are Enterprise-only. Developer and Evaluation are licensed for the same
feature set, so they answer yes; Standard, Express, Web, Personal and Azure
SQL Database answer no. An unknown edition (``None``) keeps the pre-edition
optimistic answer instead of regressing, and the 2008 partition floor still
applies whatever the edition says.

The adapt tests use backends whose server probes are overridden, so no server
is contacted; the dialect they install is the real adapted one.
"""
import asyncio

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.backend.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.impl.sqlserver.dialect import (
    SQL_SERVER_2022,
    SQLServerDialect,
)

SQL_SERVER_2005 = (9, 0, 0)

#: Edition labels whose servers lack the Enterprise feature set.
NON_ENTERPRISE_EDITIONS = [
    "Standard Edition",
    "SQL Server 2019 Standard Edition (64-bit)",
    "Express Edition",
    "Web Edition",
    "Personal Edition",
    "Azure SQL Database",
]

#: Edition labels whose servers carry it, matched case-insensitively.
ENTERPRISE_EDITIONS = [
    "Enterprise Edition",
    "Enterprise Edition: Core-based Licensing (64-bit)",
    "SQL Server Enterprise",
    "Developer Edition",
    "Evaluation Edition",
    "developer edition (64-bit)",
]


def _config() -> SQLServerConnectionConfig:
    return SQLServerConnectionConfig(
        host="localhost",
        database="master",
        username="sa",
        password="",
    )


class TestEditionCapabilityProbes:
    @pytest.mark.parametrize("edition", NON_ENTERPRISE_EDITIONS)
    def test_non_enterprise_edition_refuses_both_capabilities(self, edition):
        d = SQLServerDialect(SQL_SERVER_2022, edition=edition)
        assert d.supports_table_partitioning() is False
        assert d.supports_partition_function() is False
        assert d.supports_concurrent_index() is False

    @pytest.mark.parametrize("edition", ENTERPRISE_EDITIONS)
    def test_enterprise_feature_set_claims_both_capabilities(self, edition):
        d = SQLServerDialect(SQL_SERVER_2022, edition=edition)
        assert d.supports_table_partitioning() is True
        assert d.supports_partition_function() is True
        assert d.supports_concurrent_index() is True

    def test_unknown_edition_keeps_the_optimistic_answers(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert d.edition is None
        assert d.supports_table_partitioning() is True
        assert d.supports_concurrent_index() is True

    @pytest.mark.parametrize(
        ("edition", "concurrent"),
        [
            (None, True),
            ("Standard Edition", False),
            ("Enterprise Edition", True),
            ("Developer Edition", True),
        ],
    )
    def test_partition_version_floor_still_applies(self, edition, concurrent):
        """2005 predates partitioning, so no edition can make the probe true."""
        d = SQLServerDialect(SQL_SERVER_2005, edition=edition)
        assert d.supports_table_partitioning() is False
        assert d.supports_partition_function() is False
        # ONLINE creation has no such version floor; the edition decides it.
        assert d.supports_concurrent_index() is concurrent


class _ProbeBackendMixin:
    """Backend whose server probes answer from test data, not a connection."""

    _probe_edition = ""
    _probe_version = SQL_SERVER_2022
    _constructor_version = (15, 0, 0)

    def __init__(self, **kwargs):
        super().__init__(
            connection_config=_config(),
            version=self._constructor_version,
            **kwargs,
        )
        # Truthy, so introspect_and_adapt does not try to open a connection.
        self._connection = object()

    def get_server_version(self):
        return self._probe_version

    def get_edition(self):
        return self._probe_edition


def _make_probe_backend(
    edition,
    *,
    constructor_version=(15, 0, 0),
    probe_version=SQL_SERVER_2022,
) -> SQLServerBackend:
    class _Backend(_ProbeBackendMixin, SQLServerBackend):
        _probe_edition = edition
        _probe_version = probe_version
        _constructor_version = constructor_version

    return _Backend()


class TestAdaptRecordsTheEdition:
    def test_sync_adapt_records_the_edition_of_the_dialect_it_builds(self):
        backend = _make_probe_backend("Standard Edition")
        backend.introspect_and_adapt()

        assert backend.dialect.edition == "Standard Edition"
        assert backend.dialect.supports_table_partitioning() is False
        assert backend.dialect.supports_concurrent_index() is False

    def test_sync_adapt_records_the_edition_when_the_version_is_unchanged(self):
        """An unchanged version must not leave the edition unknown."""
        backend = _make_probe_backend(
            "Standard Edition",
            constructor_version=SQL_SERVER_2022,
        )
        dialect_before = backend.dialect
        backend.introspect_and_adapt()

        assert backend.dialect is dialect_before
        assert backend.dialect.edition == "Standard Edition"
        assert backend.dialect.supports_concurrent_index() is False

    def test_sync_adapt_treats_an_empty_answer_as_unknown(self):
        backend = _make_probe_backend("")
        backend.introspect_and_adapt()

        assert backend.dialect.edition is None
        assert backend.dialect.supports_concurrent_index() is True

    def test_async_adapt_records_the_edition(self):
        pytest.importorskip("aioodbc")
        from rhosocial.activerecord.backend.impl.sqlserver.backend.async_backend import (
            AsyncSQLServerBackend,
        )

        class _Backend(_ProbeBackendMixin, AsyncSQLServerBackend):
            _probe_edition = "Enterprise Edition"

            async def get_server_version(self):
                return self._probe_version

            async def get_edition(self):
                return self._probe_edition

        backend = _Backend()
        asyncio.run(backend.introspect_and_adapt())

        assert backend.dialect.edition == "Enterprise Edition"
        assert backend.dialect.supports_table_partitioning() is True
        assert backend.dialect.supports_concurrent_index() is True
