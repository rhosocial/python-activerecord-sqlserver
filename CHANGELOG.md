## [v1.0.0.dev2] - 2026-08-15

Introduced a relatively complete set of features for the SQL Server backend.

### Added

- SQL Server partition DDL support: `SQLServerPartitionMixin`, partition function/scheme expressions, `format_partition_clause` integration into `format_create_table_statement`, and protocol conformance gaited by server version.
- DataType #108 parsing support: register `parse_type` on dialect, populate `parsed_data_type` in introspector, and implement SQL Server-specific type string parser.
- `SQLServerSchemaDiffer` for schema snapshot diff/comparison, supporting column add/remove/modify, ordinal position detection, and table add/remove.
- `named-migration` CLI subcommand with sync and `--async` support, bridging to core `AsyncMigrationRunner` via `AsyncSQLServerBackend`.

### Changed

- Fix CLI import paths: rename `named_query` to `named_expression` in `named_procedure.py` import statements.
- Fix config `__repr__`: use `to_dict()` instead of `model_dump()` for compatibility with core `ConnectionConfig` protocol.
- Fix `parse_type` VARCHAR parsing: change `NCHAR` detection condition to `VARCHAR` so `VARCHAR` correctly returns `VarCharType` instead of `CharType`.

### Removed

- Remove outdated `TestCLINamedQueryArgs` test class and `named-query` assertion from CLI tests.

## [v1.0.0.dev1] - 2026-04-12

Initial commit of the SQL Server backend. Incomplete development placeholder.
