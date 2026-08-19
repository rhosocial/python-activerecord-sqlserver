# src/rhosocial/activerecord/backend/impl/sqlserver/examples/cli/named_connection_demo.py
"""
Named Connection CLI demo script.

Demonstrates how to invoke named connections (Named Connection) via SQL Server CLI.

Usage:
    cd src/rhosocial/activerecord/backend/impl/sqlserver/examples
    python3 cli/named_connection_demo.py

Or use CLI directly:
    python -m rhosocial.activerecord.backend.impl.sqlserver named-connection \
        --show rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.local_dev
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
import subprocess
import sys
from pathlib import Path

# Setup: ensure the package is importable from source (if not installed)
project_root = Path(__file__).resolve().parents[8]
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
"""
This section demonstrates typical Named Connection CLI usage.

### 1. List all named connections in a module

```bash
python -m rhosocial.activerecord.backend.impl.sqlserver named-connection \
    --list rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections
```

### 2. View single connection configuration details

```bash
python -m rhosocial.activerecord.backend.impl.sqlserver named-connection \
    --show rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.local_dev
```

### 3. Dry-run: resolve connection configuration

```bash
python -m rhosocial.activerecord.backend.impl.sqlserver named-connection \
    --describe rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.local_dev
```

### 4. Use named connection in query

```bash
python -m rhosocial.activerecord.backend.impl.sqlserver query \
    --named-connection rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.local_dev \
    "SELECT 1 AS test"
```
"""


def run_cli_command(args):
    """Execute CLI command and print output."""
    cmd = [sys.executable, "-m", "rhosocial.activerecord.backend.impl.sqlserver"] + args
    print(f"\n{'=' * 60}")
    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))
    print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    return result.returncode


def main():
    print("Named Connection CLI Demo")
    print("=" * 60)

    # 1. List all named connections in a module
    print("\n【1】List all named connections in module")
    run_cli_command(
        [
            "named-connection",
            "--list",
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections",
        ]
    )

    # 2. View single connection configuration details
    print("\n【2】View single connection configuration details")
    run_cli_command(
        [
            "named-connection",
            "--show",
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.local_dev",
        ]
    )

    # 3. Dry-run: resolve connection configuration
    print("\n【3】Dry-run: resolve connection configuration")
    run_cli_command(
        [
            "named-connection",
            "--describe",
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.local_dev",
        ]
    )

    # 4. Use named connection in query
    print("\n【4】Use named connection in query")
    run_cli_command(
        [
            "query",
            "--named-connection",
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.local_dev",
            "SELECT 1 AS test",
        ]
    )

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
# No cleanup needed - CLI commands are self-contained