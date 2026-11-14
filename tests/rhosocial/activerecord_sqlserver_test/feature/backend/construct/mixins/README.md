# construct/mixins

Mixin-level formatting tests for this backend.

Empty by design: the SQL Server backend's mixin-level formatting lives with the
feature it belongs to (`construct/dialect/` for capability probes and
`construct/statements/` for rendered SQL), and its one mixin-specific area —
T-SQL session settings (`SET DEADLOCK_PRIORITY`, `SET LANGUAGE`,
`SET DATEFORMAT`, `IDENTITY` queries) — is a backend-unique capability, so it
lives in `construct/sqlserver/session_settings/`.

The directory stays so the construct tree has the same eleven directories in
every backend.
