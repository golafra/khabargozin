"""Create khabargozin_test DB and run migrations."""

import subprocess
import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from scripts._util import configure_stdout

MAIN_DB = "khabargozin"
TEST_DB = "khabargozin_test"
USER = "khabargozin"
PASSWORD = "khabargozin"
HOST = "localhost"
PORT = 5432


def main() -> int:
    configure_stdout()
    try:
        conn = psycopg2.connect(
            dbname=MAIN_DB, user=USER, password=PASSWORD, host=HOST, port=PORT
        )
    except Exception as exc:
        print(f"Cannot connect to Postgres: {exc}")
        return 1

    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{TEST_DB}"')
        print(f"Created database {TEST_DB}")
    else:
        print(f"Database {TEST_DB} already exists")
    cur.close()
    conn.close()

    test_url = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{TEST_DB}"
    env = {**__import__("os").environ, "DATABASE_URL": test_url}
    print("Running alembic upgrade head...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        cwd=__import__("os").path.dirname(__import__("os").path.dirname(__file__)),
    )
    if result.returncode != 0:
        return result.returncode
    print("Test DB ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
