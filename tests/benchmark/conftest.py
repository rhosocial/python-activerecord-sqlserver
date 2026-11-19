# tests/benchmark/conftest.py
"""Register SQL Server implementations for the shared benchmark contracts.

Importing ``providers`` populates the testsuite's global ``benchmarks``
registry before pytest collects the shared ``benchmark/*`` contract files.
Without this import those contracts skip with "no implementation registered".
"""
from tests.benchmark import providers  # noqa: F401
