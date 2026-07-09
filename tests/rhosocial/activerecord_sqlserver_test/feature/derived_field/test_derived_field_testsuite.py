# tests/rhosocial/activerecord_sqlserver_test/feature/derived_field/test_derived_field_testsuite.py
"""
Bridge file for derived field feature tests from the testsuite.
"""

from rhosocial.activerecord.testsuite.feature.derived_field.conftest import (  # noqa: F401
    product_class,
    product_form_a_class,
    product_with_proxy_class,
    product_with_column_and_adapter_class,
    async_product_class,
    async_product_with_proxy_class,
    async_product_with_column_and_adapter_class,
)
from rhosocial.activerecord.testsuite.feature.derived_field.test_derived_field import *  # noqa: F401,F403
from rhosocial.activerecord.testsuite.feature.derived_field.test_derived_field_async import *  # noqa: F401,F403
