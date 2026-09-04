# cli tests

SQL Server CLI coverage: argument parsing, help, provider factory, display functions, offline black-box tests for the info / query / introspect / status subcommands and __main__.parse_args with custom argv.

## Key files

- `test_cli.py` — CLI surface tests
- `test_cli_blackbox.py` — black-box CLI against live or skipped scenarios
- `test_cli_info_query.py` — offline info/query subcommand branches
- `test_cli_introspect.py` — offline introspect subcommand branches
- `test_cli_status.py` — offline status subcommand branches
- `test_main_parse_args.py` — __main__.parse_args
