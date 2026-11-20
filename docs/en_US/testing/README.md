# Testing

Test commands and provider registration for the family of projects are defined
centrally in the core repository's `testing.md`. This page records only the SQL
Server-specific facts: the driver, the local server image and the scope of
tests you are expected to run locally.

## Environment

| Item | Value |
|------|-------|
| Python | 3.14 (default for the local venv) |
| Driver | `pyodbc` (+ ODBC Driver 17/18) |
| Local server | SQL Server 2022 image in `docker-compose.yml` |
| Async | `aioodbc`; the suite runs isolation/transaction tests through both paths |

Bring up a local server with the repository's Compose file, then let the
fixtures point at it. Connection parameters for tests come from environment
variables such as `SQLSERVER_HOST`, `SQLSERVER_PORT`, `SQLSERVER_DATABASE`,
`SQLSERVER_USERNAME`, `SQLSERVER_PASSWORD` and `SQLSERVER_DRIVER`.

## Running tests

The suite needs the `tests/` directory on `PYTHONPATH` so that the provider
registry is importable:

```bash
$env:PYTHONPATH = 'src;tests'
pytest tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct -q
```

Use the repository's `/test`, `/test-feature <category>` and `/lint` shortcuts
where available. Tests are organised by feature (`backend/construct`,
`backend/execute`, `connection`, `logging`, `adapters`, and so on); the
`providers/` registration supplies the backend to the shared testsuite.

## Live vs offline tests

- **Offline** suites replace catalogue reads with canned rows and assert every
  rendered statement. They need no database and are the default local check.
- **Live** tests (for example the catalogue coverage under
  `feature/backend/execute/introspection/`) exercise the backend against the
  SQL Server 2022 image. Partition behaviour is covered offline by the
  expression, syntax-matrix and suggestion suites. A live test **skips —
  rather than passes —** when no scenario is configured or the server cannot be
  reached, so a skipped live test is not evidence that the feature works.

## Local test scope

> ⚠️ **Never run the full suite locally.** A single `pytest tests/` collection
> takes minutes and conflicts with the task time budget. Full-matrix testing
> belongs to remote CI.

Local runs are limited to targeted checks within the task at hand:

- importing a single module;
- asserting a signature or a single behaviour;
- a single test file or a single test case;
- `python -m py_compile` on changed example scripts.

The `docs/examples/` scripts are syntax-checked this way. They are not executed
locally because no SQL Server is available to the documentation build; their
import paths and model declarations are nevertheless written against this
backend's real classes.

## Sibling testsuite installation

When wiring the shared testsuite for local cross-repo integration, install it by explicit local
path rather than relying on a published version from an index — a published
version may be older and lack modules the current backend expects. Install
sibling packages the same way so the editable source tree, not a stale
published wheel, is what gets imported.
