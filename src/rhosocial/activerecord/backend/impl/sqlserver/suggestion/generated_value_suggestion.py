# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/generated_value_suggestion.py
"""SQLServerGeneratedValueSuggestionMixin -- sqlserver's generated-value column suggestion.

The answer is the backend's own spelling, assembled from its capability
probes where it has one. It is placed first in the dialect bases so no core
mixin can shadow it, and it renders nothing itself -- the returned clause's
formatter owns the SQL spelling.
"""

from typing import TYPE_CHECKING

from ....expression.statements import IdentityClause
from ....suggestion import GeneratedValueSuggestion

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.types._base import DataType


class SQLServerGeneratedValueSuggestionMixin:
    """Suggest sqlserver's declaration for a generated integer key."""

    def suggest_generated_value(
        self, default_type: "DataType"
    ) -> GeneratedValueSuggestion:
        return GeneratedValueSuggestion(
            state="generate",
            storage_type=default_type,
            clause=IdentityClause(self, start=1, increment=1),
        )
