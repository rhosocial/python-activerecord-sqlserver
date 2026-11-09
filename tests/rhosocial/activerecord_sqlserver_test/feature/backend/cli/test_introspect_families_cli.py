# tests/rhosocial/activerecord_sqlserver_test/feature/backend/cli/test_introspect_families_cli.py
"""The shared families the MySQL and PostgreSQL CLIs ask, as this one asks them.

No server is needed here. What is checked is the wiring the CLI owns: that
each type reaches its introspector method, that NAME and the type-specific
flags arrive as arguments rather than being parsed and dropped, and that a
family the connected server refuses is refused. Whether the answer is right
is the introspector's question, and the live tests carry it.

Four of the eight are gated on the server's version because the SQL they
render needs an object a release can lack -- the dynamic management views
and the pagination clause -- so the floors are asserted on both sides: a
server at the floor is not refused, and a server below it is refused before
a statement is rendered rather than failing at execution. One of the nine
this engine does not answer at all, and that is asserted as the dialect's
``False`` as well. The ninth, ``ddl``, is not offered by the CLI: the
capability is permanently false, so the parser refuses it as an invalid
choice.
"""

import argparse
import json
from typing import Optional

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.cli import introspect as introspect_cli
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.backend import async_backend as async_backend_mod
from rhosocial.activerecord.backend.introspection.types import (
    ColumnDataProfile,
    ColumnValueFrequency,
    JoinCoverage,
)

#: The eight families this change wires, and the switch that gates each. The
#: dialect declares them, so a run against a real server passes the gate; the
#: refusal tests below turn the switch off to prove the gate is still read.
#: ``ddl`` is not among them: its capability is permanently false, so the CLI
#: does not advertise the type.
NEW_FAMILIES = {
    "unused-indexes": "supports_unused_indexes_detection",
    "table-stats": "supports_table_stats",
    "runtime": "supports_runtime_stats",
    "index-stats": "supports_index_stats",
    "dependencies": "supports_object_dependencies",
    "column-profiles": "supports_column_data_profile",
    "value-samples": "supports_column_value_sample",
    "join-coverage": "supports_join_coverage",
}

#: The four families that answer for the whole database and take no NAME.
WHOLE_DATABASE_FAMILIES = (
    "unused-indexes",
    "table-stats",
    "runtime",
    "index-stats",
)

#: The releases the CI matrix runs, and the product version each reports.
SQL_2017 = (14, 0, 1000)
SQL_2019 = (15, 0, 2000)
SQL_2022 = (16, 0, 1000)

#: The floor each gated family carries, and the reason for it.
VERSION_FLOORS = {
    "unused-indexes": ((9, 0, 0), "sys.dm_db_index_usage_stats arrived with 2005"),
    "index-stats": ((9, 0, 0), "sys.dm_db_index_usage_stats arrived with 2005"),
    "runtime": ((9, 0, 0), "sys.dm_os_performance_counters arrived with 2005"),
    "dependencies": ((10, 0, 0), "sys.sql_expression_dependencies arrived with 2008"),
    "value-samples": ((11, 0, 0), "OFFSET ... FETCH is 2012 syntax"),
}

#: A version below every floor: SQL Server 2000, which none of this is.
PRE_FLOOR = (8, 0, 0)


class _RecordingIntrospector:
    """Records each introspection call, and returns what the test declared.

    ``__getattr__`` is the whole implementation: a test names the method once,
    in the assertion, and a branch that reaches a different one fails on the
    recorded name rather than on an attribute error that would hide the typo.
    """

    def __init__(self, results: Optional[dict] = None) -> None:
        self.results = results or {}
        self.calls = []

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AsyncRecordingIntrospector(_RecordingIntrospector):
    """The async shape of the same recorder: methods are awaited, calls are not."""

    def __getattr__(self, name: str):
        async def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


def _args(type_: str, name: Optional[str] = None, **overrides) -> argparse.Namespace:
    """The attributes a parsed invocation carries, with sane defaults."""
    values = dict(
        output="json",
        rich_ascii=False,
        type=type_,
        name=name,
        database="mydb",
        is_async=False,
        named_connection=None,
        include_system=False,
        column=None,
        limit=None,
        left_table=None,
        left_column=None,
        right_table=None,
        right_column=None,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


class _AnsweringDialect(SQLServerDialect):
    """SQL Server's dialect with the one still-offered unanswered probe on.

    The branch tests drive the dispatch, not the engine's answer, so the
    switch the real dialect refuses is answered here. That this is a
    *different* dialect from the one a run meets is the point:
    :class:`TestTheUnansweredFamilies` below asserts what the real one says.
    """

    def supports_table_stats(self) -> bool:
        return True


#: The version the stub's ``introspect_and_adapt()`` claims. 2022, the newest
#: release the matrix runs and the one every answered family must answer on.
STUB_SERVER_VERSION = SQL_2022


def _run_sync(monkeypatch, introspector, args) -> None:
    """Drive the sync chain against a stub whose dialect answers yes.

    The stub installs its dialect in ``introspect_and_adapt`` the way the real
    backend does, so the capability question is answered from an adapted
    dialect rather than from a bare one.
    """
    class _Backend:
        _connection = None

        def __init__(self, **_kwargs) -> None:
            self.introspector = introspector

        def connect(self) -> None:
            pass

        def introspect_and_adapt(self) -> None:
            self.dialect = _AnsweringDialect(version=STUB_SERVER_VERSION)

        def disconnect(self) -> None:
            pass

    monkeypatch.setattr(introspect_cli, "SQLServerBackend", _Backend)
    monkeypatch.setattr(
        introspect_cli, "resolve_connection_config_from_args", lambda _args: None
    )
    introspect_cli.handle(args)


def _run_async(monkeypatch, introspector, args) -> None:
    class _Backend:
        _connection = None

        def __init__(self, **_kwargs) -> None:
            self.introspector = introspector

        async def connect(self) -> None:
            pass

        async def introspect_and_adapt(self) -> None:
            self.dialect = _AnsweringDialect(version=STUB_SERVER_VERSION)

        async def disconnect(self) -> None:
            pass

    # The command builds the async backend inside ``handle()``, so the name
    # it resolves there is the one patched -- not a module attribute of this
    # module.
    monkeypatch.setattr(async_backend_mod, "AsyncSQLServerBackend", _Backend)
    monkeypatch.setattr(
        introspect_cli, "resolve_connection_config_from_args", lambda _args: None
    )
    args.is_async = True
    introspect_cli.handle(args)


class TestTheSchemaWideFamilies:
    """The counters and listings describe the database, so NAME is refused."""

    @pytest.mark.parametrize(
        "type_, method",
        [
            ("unused-indexes", "list_unused_indexes"),
            ("table-stats", "list_table_usage_stats"),
            ("runtime", "list_runtime_metrics"),
            ("index-stats", "list_index_usage_stats"),
        ],
    )
    def test_the_family_asks_its_method_for_the_whole_schema(
        self, type_, method, monkeypatch
    ):
        introspector = _RecordingIntrospector({method: []})

        _run_sync(monkeypatch, introspector, _args(type_))

        assert introspector.calls == [(method, (), {"schema": None})]

    @pytest.mark.parametrize("type_", WHOLE_DATABASE_FAMILIES)
    def test_a_name_is_refused(self, type_, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_name(_args(type_, "orders"))

        assert excinfo.value.code == 2
        assert "takes no name" in capsys.readouterr().err


class TestTheDependenciesBranch:
    """One optional NAME narrows the graph; omitting it asks for all of it."""

    def test_a_named_object_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector({"list_object_dependencies": []})

        _run_sync(monkeypatch, introspector, _args("dependencies", "posts"))

        assert introspector.calls == [
            ("list_object_dependencies", (), {"object_name": "posts", "schema": None})
        ]

    def test_an_unnamed_run_asks_for_the_whole_graph(self, monkeypatch):
        introspector = _RecordingIntrospector({"list_object_dependencies": []})

        _run_sync(monkeypatch, introspector, _args("dependencies"))

        assert introspector.calls == [
            ("list_object_dependencies", (), {"object_name": None, "schema": None})
        ]


class TestTheColumnProfilesBranch:
    """The aggregate label must reach the reader; the numbers are not a catalogue."""

    def _profile(self) -> ColumnDataProfile:
        return ColumnDataProfile(
            schema="dbo",
            table_name="orders",
            column_name="status",
            null_fraction=0.0,
            distinct_count=3,
            row_count=120,
            source="aggregate",
        )

    def test_the_table_is_asked_for_by_name(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "orders"))

        assert introspector.calls == [
            ("list_column_data_profiles", (), {"table_name": "orders", "schema": None})
        ]

    def test_the_run_says_the_numbers_are_aggregated(self, monkeypatch, capsys):
        """Exact and expensive, on stderr so the JSON on stdout stays parseable."""
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "orders"))

        captured = capsys.readouterr()
        assert "aggregate" in captured.err
        assert "full scan" in captured.err
        payload = json.loads(captured.out)
        assert payload[0]["source"] == "aggregate"

    def test_the_note_is_not_mistaken_for_a_result_row(self, monkeypatch, capsys):
        """The note belongs on stderr; a line on stdout would break every parser."""
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "orders"))

        out = capsys.readouterr().out
        assert out.lstrip().startswith("[")


class TestTheValueSamplesBranch:
    """A table and a column, and a limit that the introspector receives."""

    def test_the_table_column_and_limit_reach_the_introspector(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"sample_column_values": [ColumnValueFrequency(value="paid", count=7)]}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _args("value-samples", "orders", column="status", limit=20),
        )

        assert introspector.calls == [
            (
                "sample_column_values",
                (),
                {
                    "table_name": "orders",
                    "column_name": "status",
                    "limit": 20,
                    "schema": None,
                },
            )
        ]

    def test_no_limit_is_sent_when_the_flag_is_omitted(self, monkeypatch):
        introspector = _RecordingIntrospector({"sample_column_values": []})

        _run_sync(
            monkeypatch, introspector, _args("value-samples", "orders", column="status")
        )

        # Absent ``--limit`` means absent from the call: the introspector's own
        # signature answers with its own default, and the CLI does not restate
        # it. A number here would fail the day the signature's default moved.
        assert "limit" not in introspector.calls[0][2]

    def test_a_missing_column_is_an_incomplete_invocation(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_options(_args("value-samples", "orders"))

        assert excinfo.value.code == 1
        assert "--column" in capsys.readouterr().err


class TestTheJoinCoverageBranch:
    """Four names, both sides of the measurement, in the order they are asked."""

    def _coverage(self) -> JoinCoverage:
        return JoinCoverage(
            left_schema="dbo",
            left_table="orders",
            left_column="customer_id",
            right_schema="dbo",
            right_table="customers",
            right_column="id",
            left_coverage=1.0,
            right_coverage=0.75,
        )

    def test_the_four_names_reach_the_introspector(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"estimate_join_coverage": self._coverage()}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _args(
                "join-coverage",
                left_table="orders",
                left_column="customer_id",
                right_table="customers",
                right_column="id",
            ),
        )

        assert introspector.calls == [
            (
                "estimate_join_coverage",
                (),
                {
                    "left_table": "orders",
                    "left_column": "customer_id",
                    "right_table": "customers",
                    "right_column": "id",
                    "schema": None,
                },
            )
        ]

    def test_both_fractions_are_reported(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"estimate_join_coverage": self._coverage()}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _args(
                "join-coverage",
                left_table="orders",
                left_column="customer_id",
                right_table="customers",
                right_column="id",
            ),
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["left_coverage"] == 1.0
        assert payload[0]["right_coverage"] == 0.75

    def test_missing_names_are_listed_together(self, capsys):
        """One run should name every absent flag, not the first one it met."""
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_options(
                _args(
                    "join-coverage",
                    left_table="orders",
                    right_table="customers",
                )
            )

        assert excinfo.value.code == 1
        err = capsys.readouterr().err
        assert "--left-column" in err
        assert "--right-column" in err

    def test_an_unmeasurable_pair_is_an_error(self, monkeypatch, capsys):
        """``None`` is "not measured", which is not a zero-overlap answer."""
        introspector = _RecordingIntrospector({"estimate_join_coverage": None})

        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                introspector,
                _args(
                    "join-coverage",
                    left_table="orders",
                    left_column="customer_id",
                    right_table="customers",
                    right_column="id",
                ),
            )

        assert excinfo.value.code == 1
        assert "could not measure" in capsys.readouterr().err


class TestTheArgumentRules:
    def test_a_flag_the_type_does_not_read_is_refused(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_options(_args("tables", column="status"))

        assert excinfo.value.code == 2
        assert "takes no --column" in capsys.readouterr().err

    def test_a_required_name_is_required_for_the_new_families(self, capsys):
        for type_ in ("column-profiles", "value-samples"):
            with pytest.raises(SystemExit) as excinfo:
                introspect_cli._validate_name(_args(type_))
            assert excinfo.value.code == 1
        assert "required" in capsys.readouterr().err


class TestTheCapabilityGate:
    @pytest.mark.parametrize("type_, switch", list(NEW_FAMILIES.items()))
    def test_a_family_the_server_refuses_exits_two(self, type_, switch, capsys):
        class _Dialect:
            pass

        setattr(_Dialect, switch, staticmethod(lambda: False))

        class _Backend:
            dialect = _Dialect()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(_Backend(), type_)

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err


class TestTheAsyncPath:
    """The second dispatch chain must ask the same question the first one does."""

    @pytest.mark.parametrize(
        "type_, method, args_kwargs, expected",
        [
            ("unused-indexes", "list_unused_indexes", {}, ((), {"schema": None})),
            (
                "dependencies",
                "list_object_dependencies",
                {"name": "orders"},
                ((), {"object_name": "orders", "schema": None}),
            ),
            (
                "column-profiles",
                "list_column_data_profiles",
                {"name": "orders"},
                ((), {"table_name": "orders", "schema": None}),
            ),
            (
                "value-samples",
                "sample_column_values",
                {"name": "orders", "column": "status", "limit": 5},
                (
                    (),
                    {
                        "table_name": "orders",
                        "column_name": "status",
                        "limit": 5,
                        "schema": None,
                    },
                ),
            ),
            (
                "join-coverage",
                "estimate_join_coverage",
                {
                    "left_table": "orders",
                    "left_column": "customer_id",
                    "right_table": "customers",
                    "right_column": "id",
                },
                (
                    (),
                    {
                        "left_table": "orders",
                        "left_column": "customer_id",
                        "right_table": "customers",
                        "right_column": "id",
                        "schema": None,
                    },
                ),
            ),
        ],
    )
    def test_the_async_branch_calls_the_same_method_with_the_same_arguments(
        self, type_, method, args_kwargs, expected, monkeypatch
    ):
        introspector = _AsyncRecordingIntrospector({method: []})

        _run_async(monkeypatch, introspector, _args(type_, **args_kwargs))

        assert introspector.calls == [(method, expected[0], expected[1])]


class TestTheTypeSurfaceExtension:
    def test_each_new_family_has_a_switch_the_dialect_declares(self):
        for type_, switch in NEW_FAMILIES.items():
            assert introspect_cli._TYPE_CAPABILITIES[type_] == switch
            assert hasattr(SQLServerDialect, switch)


class TestTheVersionFloors:
    """The families whose SQL needs an object a release can lack.

    The dynamic management views arrived across three releases and the
    pagination clause ``value-samples`` renders is 2012 syntax, so each probe
    asks the version accessor rather than answering a bare ``True``. That is
    what keeps the CLI from turning a definition-time question into a runtime
    syntax error: a server below the floor is refused at the capability
    question, and the introspector is never reached.

    Asserted on both sides of each floor, and on every release the matrix
    runs -- 2017, 2019 and 2022 -- which are the versions this repository
    actually tests against.
    """

    @pytest.mark.parametrize("type_, switch", list(NEW_FAMILIES.items()))
    def test_a_gated_family_answers_at_every_matrix_release(self, type_, switch):
        if type_ not in VERSION_FLOORS:
            pytest.skip(f"{type_} is not gated on a version")
        for version in (SQL_2017, SQL_2019, SQL_2022):
            dialect = SQLServerDialect(version=version)
            assert getattr(dialect, switch)() is True, (type_, version)

    @pytest.mark.parametrize("type_, switch", list(NEW_FAMILIES.items()))
    def test_a_gated_family_refuses_below_its_floor(self, type_, switch):
        if type_ not in VERSION_FLOORS:
            pytest.skip(f"{type_} is not gated on a version")
        floor, reason = VERSION_FLOORS[type_]
        below = (floor[0] - 1, 0, 0)
        dialect = SQLServerDialect(version=below)
        assert getattr(dialect, switch)() is False, f"{type_}: {reason}"

    @pytest.mark.parametrize("type_", list(VERSION_FLOORS))
    def test_the_refusal_comes_before_the_statement_is_rendered(self, type_, capsys):
        """The regression itself: the statement is never handed to the engine.

        A probe that answered ``True`` below the floor rendered its SQL and
        reported the resulting ``ProgrammingError`` as a generic "Error during
        introspection". Below the floor the introspector is not reached at all.
        """
        floor = VERSION_FLOORS[type_][0]
        below = (floor[0] - 1, 0, 0)

        class _Backend:
            dialect = SQLServerDialect(version=below)

            def __init__(self):
                self.introspector = _RecordingIntrospector()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(_Backend(), type_)

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err

    def test_an_unadapted_dialect_refuses_a_gated_family(self):
        """An unconfirmed version must not read as a capability the server has.

        ``version_at_least`` answers without raising, so a probe guarded on it
        can be called before the handshake -- and a dialect nobody has adapted
        is one whose version nobody has confirmed.
        """
        dialect = SQLServerDialect()
        assert dialect.version_or_none is None
        for type_, switch in NEW_FAMILIES.items():
            if type_ in VERSION_FLOORS:
                assert getattr(dialect, switch)() is False, type_


class TestTheUnansweredFamilies:
    """What this engine does not answer, on any version.

    Per-table usage counters: SQL Server's counters are per *index*, and
    summing them per table would be a derived figure wearing the shape of a
    measured one; inserts and deletes are not tracked at all. The probe answers
    ``False``, the CLI offers the type and refuses it at the capability
    question, and the roundtrip matrix keeps its pin for the statement class
    with this reason.

    DDL retrieval is equally unanswered -- the engine has no per-object call
    of the kind MySQL's ``SHOW CREATE TABLE`` is -- but it is not offered by
    the CLI at all. A type whose capability can never be true would promise
    only a refusal, so ``ddl`` is an invalid argparse choice instead. The
    backend capability and expression stay, ready for a real implementation.
    """

    UNANSWERED = {
        "table-stats": "supports_table_stats",
    }

    @pytest.mark.parametrize("type_, switch", list(UNANSWERED.items()))
    def test_the_dialect_refuses_them(self, type_, switch):
        for version in (SQL_2017, SQL_2019, SQL_2022):
            dialect = SQLServerDialect(version=version)
            assert getattr(dialect, switch)() is False, type_

    @pytest.mark.parametrize("type_", list(UNANSWERED))
    def test_the_cli_offers_them_and_refuses_them(self, type_, capsys):
        """Offered, not hidden: the parser accepts the type and the gate
        refuses it, which is a different answer from an invalid choice."""
        from rhosocial.activerecord.backend.impl.sqlserver.__main__ import parse_args

        args = parse_args(["introspect", type_, "--database", "db"])
        assert args.type == type_

        class _Backend:
            dialect = SQLServerDialect(version=SQL_2022)

            def __init__(self):
                self.introspector = _RecordingIntrospector()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(_Backend(), type_)

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err

    def test_an_empty_per_table_counter_list_would_not_be_an_answer(self):
        """The refusal is the capability answer, not "this database has none".

        A probe that answered ``True`` and a backend that returned an empty
        list would read as a measured zero, which is the wrong answer twice
        over: the engine never measured, and the reader cannot tell.
        """
        dialect = SQLServerDialect(version=SQL_2022)
        assert dialect.supports_table_stats() is False

    def test_ddl_is_not_advertised_by_the_parser(self):
        """The backend's ``False`` is unchanged; the CLI no longer offers it."""
        from rhosocial.activerecord.backend.impl.sqlserver.__main__ import parse_args

        assert "ddl" not in introspect_cli._TYPE_CAPABILITIES
        assert "ddl" not in introspect_cli._NAME_RULE
        assert SQLServerDialect(version=SQL_2022).supports_ddl_extraction() is False
        with pytest.raises(SystemExit) as excinfo:
            parse_args(["introspect", "ddl", "orders", "--database", "db"])
        assert excinfo.value.code == 2
