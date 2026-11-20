# query/relation tests (SQL Server bridge)

SQL Server bridge for the shared `feature/query/relation` testsuite topic. This
directory mirrors the testsuite source tree after its feature restructure: the
old `feature/relation/` bridge group and the old `feature/query/relations/`
bridge group were merged here.

- `conftest.py` — star-imports `testsuite.feature.query.relation.conftest`.
- `ordering/conftest.py` — star-imports `testsuite.feature.query.relation.ordering.conftest`.

See [feature tests](../README.md) and [tests/README.md](../../../../README.md).
