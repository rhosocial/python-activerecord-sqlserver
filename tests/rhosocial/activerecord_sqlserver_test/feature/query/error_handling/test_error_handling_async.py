# tests/rhosocial/activerecord_sqlserver_test/feature/query/error_handling/test_error_handling_async.py
"""Bridge file for async feature.query.error_handling.test_error_handling_async tests.

SQL Server trims trailing spaces from VARCHAR/NVARCHAR columns on retrieval
(fundamental server behavior), so the two tests that assert exact round-trip
preservation of trailing spaces cannot pass and are skipped here.
"""
import pytest

import rhosocial.activerecord.testsuite.feature.query.error_handling.test_error_handling_async as _src

_TRAILING_SPACE_REASON = (
    "SQL Server trims trailing spaces from VARCHAR/NVARCHAR on retrieval "
    "(fundamental server behavior); these tests assert MySQL-style "
    "trailing-space preservation."
)
_TRAILING_SPACE_TESTS = [
    "test_special_character_full_matrix",
    "test_comment_style_variation_immunity",
]

for _name in _TRAILING_SPACE_TESTS:
    setattr(_src, _name, pytest.mark.skip(reason=_TRAILING_SPACE_REASON)(getattr(_src, _name)))

from rhosocial.activerecord.testsuite.feature.query.error_handling.test_error_handling_async import *  # noqa: F401, F403, E402
