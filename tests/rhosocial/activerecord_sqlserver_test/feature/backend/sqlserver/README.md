# sqlserver tests

Vendor-specific subtree for SQL Server implementation details: offline adapter round trips (datetime, datetimeoffset, XML, hierarchyid, spatial, ...), adapter suggestions, SET type approximation via comma-separated VARCHAR values, spatial types, partition functions/schemes, SQL/XML support boundaries, dialect security (bracket escaping), function factory instantiation and P1/P2 coverage-gap features (OPTION hints, PIVOT/UNPIVOT, TABLESAMPLE, columnstore, memory-optimized tables, indexed views, full-text catalogs, procedures/functions/triggers DDL).

## Key files

- `test_adapter_suggestions.py` — default adapter suggestions
- `test_adapters_offline.py` — offline adapter round trips
- `test_p1_coverage_features.py` — P1 coverage-gap features
- `test_p2_coverage_features.py` — P2 coverage-gap features
- `test_protocol_support.py` — SQL Server protocol contracts
- `test_set_type.py` — SET type approximation protocol
- `test_set_type_backend.py` — comma-separated SET storage integration
- `test_spatial_types.py` — spatial type protocol/formatting
- `test_spatial_types_backend.py` — spatial types integration
- `test_sqlserver_dialect_security.py` — bracket-quoting security
- `test_sqlserver_functions.py` — function factory imports/instantiation
- `test_sqlserver_partition.py` — partition protocol/clauses/functions/schemes
- `test_sqlxml_support.py` — SQL/XML support boundaries

## Vendor-specific tests

Vendor-specific tests: everything under this directory exercises SQL Server-only implementation behavior that has no cross-backend equivalent.
