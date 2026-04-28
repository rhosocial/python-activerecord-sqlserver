# src/rhosocial/activerecord/backend/impl/sqlserver/cli/output.py
"""Output provider factory and display helpers."""

from rhosocial.activerecord.backend.output import (
    JsonOutputProvider,
    CsvOutputProvider,
    TsvOutputProvider,
)

try:
    from rhosocial.activerecord.backend.output_rich import RichOutputProvider
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    RichOutputProvider = None  # type: ignore[misc,assignment]


def create_provider(output_format: str, ascii_borders: bool = False):
    """Factory function to get the correct output provider.

    Args:
        output_format: One of 'table', 'json', 'csv', 'tsv'.
        ascii_borders: Use ASCII characters for rich table borders.

    Returns:
        An output provider instance.
    """
    if output_format == "table" and not RICH_AVAILABLE:
        output_format = "json"

    if output_format == "table" and RICH_AVAILABLE:
        from rich.console import Console
        return RichOutputProvider(console=Console(), ascii_borders=ascii_borders)

    if output_format == "json":
        return JsonOutputProvider()

    if output_format == "csv":
        return CsvOutputProvider()

    if output_format == "tsv":
        return TsvOutputProvider()

    return JsonOutputProvider()


def display_nested_json(data):
    """Display nested data as JSON to stdout.

    Used when the output structure is too complex for csv/tsv
    (e.g., info overview, status 'all').
    """
    import json
    print(json.dumps(data, indent=2))
