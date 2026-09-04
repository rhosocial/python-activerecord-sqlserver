import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

SQL_SERVER_2012 = (11, 0, 0)
SQL_SERVER_2014 = (12, 0, 0)
SQL_SERVER_2016 = (13, 0, 0)
SQL_SERVER_2017 = (14, 0, 0)
SQL_SERVER_2019 = (15, 0, 0)
SQL_SERVER_2022 = (16, 0, 0)


class TestSQLServerFunctionSupportBasic:
    def test_supports_functions_returns_dict(self):
        dialect = SQLServerDialect(SQL_SERVER_2022)
        result = dialect.supports_functions()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_supports_functions_all_values_are_bool(self):
        dialect = SQLServerDialect(SQL_SERVER_2022)
        result = dialect.supports_functions()
        for func_name, supported in result.items():
            assert isinstance(supported, bool), f"Value for {func_name} is not bool"

    def test_core_functions_always_supported(self):
        dialect = SQLServerDialect(SQL_SERVER_2022)
        result = dialect.supports_functions()
        core_functions = ["count", "sum_", "avg", "min_", "max_", "coalesce", "nullif"]
        for func in core_functions:
            assert func in result, f"Core function {func} not in result"
            assert result[func] is True, f"Core function {func} should be supported"


class TestSQLServerFunctionSupportVersionDependent:
    def test_json_functions_require_sqlserver_2016(self):
        json_functions = ["json_value", "json_query", "json_modify", "isjson", "openjson"]

        dialect_old = SQLServerDialect(SQL_SERVER_2014)
        result_old = dialect_old.supports_functions()
        for func in json_functions:
            assert result_old.get(func) is False, f"{func} should not be supported pre-2016"

        dialect_new = SQLServerDialect(SQL_SERVER_2016)
        result_new = dialect_new.supports_functions()
        for func in json_functions:
            assert result_new.get(func) is True, f"{func} should be supported on 2016+"

    def test_string_agg_requires_sqlserver_2017(self):
        dialect_old = SQLServerDialect(SQL_SERVER_2016)
        result_old = dialect_old.supports_functions()
        assert result_old.get("string_agg") is False

        dialect_new = SQLServerDialect(SQL_SERVER_2017)
        result_new = dialect_new.supports_functions()
        assert result_new.get("string_agg") is True

    def test_concat_ws_and_trim_require_sqlserver_2017(self):
        functions = ["concat_ws", "trim"]

        dialect_old = SQLServerDialect(SQL_SERVER_2016)
        result_old = dialect_old.supports_functions()
        for func in functions:
            assert result_old.get(func) is False

        dialect_new = SQLServerDialect(SQL_SERVER_2017)
        result_new = dialect_new.supports_functions()
        for func in functions:
            assert result_new.get(func) is True

    def test_approx_count_distinct_requires_sqlserver_2019(self):
        dialect_old = SQLServerDialect(SQL_SERVER_2017)
        result_old = dialect_old.supports_functions()
        assert result_old.get("approx_count_distinct") is False

        dialect_new = SQLServerDialect(SQL_SERVER_2019)
        result_new = dialect_new.supports_functions()
        assert result_new.get("approx_count_distinct") is True

    def test_latest_json_functions_require_sqlserver_2022(self):
        json_functions_2022 = ["json_path_exists", "json_object", "json_array"]

        dialect_old = SQLServerDialect(SQL_SERVER_2019)
        result_old = dialect_old.supports_functions()
        for func in json_functions_2022:
            assert result_old.get(func) is False, f"{func} should not be supported pre-2022"

        dialect_new = SQLServerDialect(SQL_SERVER_2022)
        result_new = dialect_new.supports_functions()
        for func in json_functions_2022:
            assert result_new.get(func) is True, f"{func} should be supported on 2022+"

    def test_always_available_functions(self):
        dialect = SQLServerDialect(SQL_SERVER_2022)
        result = dialect.supports_functions()
        always_available = [
            "iif", "choose", "try_cast", "try_convert", "try_parse",
            "eomonth", "datefromparts", "datetime2fromparts",
            "datetimeoffsetfromparts", "timefromparts",
        ]
        for func in always_available:
            assert result.get(func) is True, f"{func} should be always available"

    def test_datediff_big_requires_sqlserver_2016(self):
        dialect_old = SQLServerDialect(SQL_SERVER_2014)
        result_old = dialect_old.supports_functions()
        assert result_old.get("datediff_big") is False

        dialect_new = SQLServerDialect(SQL_SERVER_2016)
        result_new = dialect_new.supports_functions()
        assert result_new.get("datediff_big") is True


class TestSQLServerFunctionSupportPrivateMethod:
    def test_unknown_function_returns_true(self):
        dialect = SQLServerDialect(SQL_SERVER_2022)
        result = dialect._is_sqlserver_function_supported("unknown_function_xyz")
        assert result is True

    def test_version_restricted_function_below_minimum(self):
        dialect = SQLServerDialect(SQL_SERVER_2014)
        result = dialect._is_sqlserver_function_supported("json_value")
        assert result is False

    def test_version_restricted_function_at_minimum(self):
        dialect = SQLServerDialect(SQL_SERVER_2016)
        result = dialect._is_sqlserver_function_supported("json_value")
        assert result is True

    def test_version_restricted_function_above_minimum(self):
        dialect = SQLServerDialect(SQL_SERVER_2022)
        result = dialect._is_sqlserver_function_supported("json_value")
        assert result is True


class TestSQLServerFunctionSupportIntegration:
    def test_function_dict_contains_both_core_and_backend_functions(self):
        dialect = SQLServerDialect(SQL_SERVER_2022)
        result = dialect.supports_functions()
        assert any(func in result for func in ["count", "sum_", "avg"])
        assert any(func in result for func in ["json_value", "string_agg", "iif"])

    def test_function_support_changes_with_version(self):
        old_dialect = SQLServerDialect(SQL_SERVER_2014)
        new_dialect = SQLServerDialect(SQL_SERVER_2022)
        old_result = old_dialect.supports_functions()
        new_result = new_dialect.supports_functions()
        assert old_result.get("openjson") is False
        assert new_result.get("openjson") is True
        assert old_result.get("string_agg") is False
        assert new_result.get("string_agg") is True
