"""Pre-enable READ_COMMITTED_SNAPSHOT before pytest-xdist workers start."""
import yaml, os, pyodbc, sys
cfg_path = os.environ.get("SQLSERVER_SCENARIOS_CONFIG_PATH", "")
if not cfg_path or not os.path.exists(cfg_path):
    sys.exit(0)
with open(cfg_path) as f:
    scenarios = yaml.safe_load(f).get("scenarios", {})
for name, cfg in scenarios.items():
    port = cfg.get("port", 1433)
    db = cfg.get("database", "test_db")
    pwd = cfg.get("password", "Password123!")
    driver = cfg.get("driver", "ODBC Driver 18 for SQL Server")
    conn_str = (
        f"DRIVER={{{driver}}};SERVER=localhost,{port};DATABASE=master;"
        f"UID=sa;PWD={pwd};TrustServerCertificate=yes;Encrypt=no;"
    )
    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
        cur = conn.cursor()
        cur.execute("SET LOCK_TIMEOUT 10000")
        cur.execute(f"ALTER DATABASE [{db}] SET READ_COMMITTED_SNAPSHOT ON")
        cur.close()
        conn.close()
        print(f"READ_COMMITTED_SNAPSHOT enabled for {db} on port {port}")
    except Exception as e:
        print(f"Note: {db} on port {port}: {e}")
