"""Read-only: report which tables, columns and indexes from database/migrations a database is missing.

    python scripts/check_migrations.py                    # DATABASE_URL from backend/.env
    python scripts/check_migrations.py --url postgresql://...

There is no migrations ledger, so this inspects the catalog for what each file creates. Run it
against every database (development, staging, production) before relying on a new feature.
Exit code 1 when anything is missing.
"""

import argparse
import re
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
TABLE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?(\w+)", re.I)
COLUMN = re.compile(
    r"alter\s+table\s+(?:only\s+)?(?:public\.)?(\w+)\s+add\s+column\s+(?:if\s+not\s+exists\s+)?(\w+)", re.I
)
INDEX = re.compile(r"create\s+(?:unique\s+)?index\s+(?:if\s+not\s+exists\s+)?(\w+)", re.I)
RLS = re.compile(r"alter\s+table\s+(?:public\.)?(\w+)\s+enable\s+row\s+level\s+security", re.I)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="database URL (default: DATABASE_URL in backend/.env)")
    args = parser.parse_args()
    url = args.url or (dotenv_values(ROOT / "backend/.env").get("DATABASE_URL") or "").strip("'\"")
    if not url:
        print("No database URL: pass --url or set DATABASE_URL in backend/.env", file=sys.stderr)
        return 2
    with psycopg.connect(url) as conn:
        tables = {r[0] for r in conn.execute("select table_name from information_schema.tables where table_schema='public'")}
        columns = {
            (r[0], r[1])
            for r in conn.execute("select table_name,column_name from information_schema.columns where table_schema='public'")
        }
        indexes = {r[0] for r in conn.execute("select indexname from pg_indexes where schemaname='public'")}
        secured = {r[0] for r in conn.execute("select relname from pg_class where relrowsecurity and relnamespace='public'::regnamespace")}
    incomplete = 0
    for path in sorted((ROOT / "database/migrations").glob("*.sql")):
        sql = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
        missing = [f"table {t}" for t in TABLE.findall(sql) if t not in tables]
        missing += [f"column {t}.{c}" for t, c in COLUMN.findall(sql) if (t, c) not in columns]
        missing += [f"index {i}" for i in INDEX.findall(sql) if i not in indexes]
        missing += [f"RLS on {t}" for t in RLS.findall(sql) if t in tables and t not in secured]
        incomplete += bool(missing)
        print(f"{path.name:45} {'OK' if not missing else 'MISSING: ' + ', '.join(missing)}")
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
