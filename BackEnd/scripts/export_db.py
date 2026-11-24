"""Export database deliverables into ../DataBase and ../docs.

    python scripts/export_db.py

* DataBase/schema.sql      MySQL DDL generated from the Alembic migrations (tables, indexes, FKs, triggers)
* DataBase/hrms_dump.sql   schema + data. Uses `mysqldump` when DATABASE_URL points at MySQL and the
                           tool is available; otherwise renders MySQL-compatible INSERTs from the current
                           database (e.g. the SQLite dev DB) so it can be imported into MySQL directly.
* docs/er_diagram.md       Mermaid ER diagram generated from the SQLAlchemy models
"""

import io
import json
import os
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from pymysql.converters import escape_string  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402

DB_DIR = ROOT.parent / "DataBase"
DOCS_DIR = ROOT.parent / "docs"
HEADER = f"-- HRMS database - generated {datetime.now():%Y-%m-%d %H:%M}\n-- Target: MySQL 8+/9 (utf8mb4)\n"


def mysql_schema_sql() -> str:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    old = settings.DATABASE_URL
    settings.DATABASE_URL = "mysql+pymysql://user:pass@localhost/hrms_db"  # offline: dialect only
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            command.upgrade(cfg, "head", sql=True)
    finally:
        settings.DATABASE_URL = old
    return buf.getvalue()


def literal(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, Enum):
        v = v.value
    if isinstance(v, datetime):
        return f"'{v:%Y-%m-%d %H:%M:%S}'"
    if isinstance(v, date):
        return f"'{v:%Y-%m-%d}'"
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    return "'" + escape_string(str(v)) + "'"


def rendered_inserts() -> str:
    out = ["SET FOREIGN_KEY_CHECKS = 0;", "SET NAMES utf8mb4;", ""]
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            rows = conn.execute(select(table)).mappings().all()
            if not rows:
                continue
            cols = ", ".join(f"`{c.name}`" for c in table.columns)
            out.append(f"-- {table.name}: {len(rows)} row(s)")
            for i in range(0, len(rows), 200):
                values = ",\n".join("(" + ", ".join(literal(r[c.name]) for c in table.columns) + ")" for r in rows[i:i + 200])
                out.append(f"INSERT INTO `{table.name}` ({cols}) VALUES\n{values};")
            out.append("")
    out.append("SET FOREIGN_KEY_CHECKS = 1;")
    return "\n".join(out)


def find_mysqldump() -> str | None:
    found = shutil.which("mysqldump")
    if found:
        return found
    for base in Path("C:/Program Files/MySQL").glob("MySQL Server */bin/mysqldump.exe"):
        return str(base)
    return None


def try_mysqldump(target: Path) -> bool:
    if not settings.DATABASE_URL.startswith("mysql"):
        return False
    tool = find_mysqldump()
    if not tool:
        print("mysqldump not found - falling back to rendered INSERTs")
        return False
    url = make_url(settings.DATABASE_URL)
    env = {**os.environ, "MYSQL_PWD": url.password or ""}  # keeps the password off the command line
    args = [tool, "-h", url.host or "localhost", "-P", str(url.port or 3306), "-u", url.username,
            "--routines", "--triggers", "--single-transaction", "--set-gtid-purged=OFF",
            "--default-character-set=utf8mb4", "--databases", url.database]
    with target.open("w", encoding="utf-8") as fh:
        fh.write(HEADER)
        res = subprocess.run(args, stdout=fh, stderr=subprocess.PIPE, env=env, text=True)
    if res.returncode != 0:
        print("mysqldump failed:", res.stderr.strip()[:300])
        return False
    return True


def er_diagram() -> str:
    lines = ["# HRMS - Entity Relationship Diagram", "", "Generated from the SQLAlchemy models (`BackEnd/app/models`).", "", "```mermaid", "erDiagram"]
    for t in Base.metadata.sorted_tables:
        lines.append(f"    {t.name} {{")
        for c in t.columns:
            typ = c.type.__class__.__name__.lower().replace("enum", "enum")
            keys = []
            if c.primary_key:
                keys.append("PK")
            if c.foreign_keys:
                keys.append("FK")
            if c.unique:
                keys.append("UK")
            lines.append(f"        {typ} {c.name}{' ' + ','.join(keys) if keys else ''}")
        lines.append("    }")
    rels = set()
    for t in Base.metadata.sorted_tables:
        for fk in t.foreign_keys:
            parent = fk.column.table.name
            one_to_one = any(c.unique for c in fk.parent.table.columns if c is fk.parent)
            card = "||--o|" if one_to_one else "||--o{"
            rels.add(f"    {parent} {card} {t.name} : \"{fk.parent.name}\"")
    lines += sorted(rels)
    lines += ["```", ""]
    return "\n".join(lines)


def main() -> None:
    DB_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    schema = HEADER + "-- Apply with:  mysql -u root -p hrms_db < schema.sql   (or run `alembic upgrade head`)\n\n" + mysql_schema_sql()
    (DB_DIR / "schema.sql").write_text(schema, encoding="utf-8")
    print("wrote", DB_DIR / "schema.sql")

    dump = DB_DIR / "hrms_dump.sql"
    if try_mysqldump(dump):
        print("wrote", dump, "(mysqldump)")
    else:
        body = (
            HEADER
            + f"-- Source database: {engine.dialect.name}. Import into an EMPTY MySQL database:\n"
            + "--   CREATE DATABASE hrms_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
            + "--   mysql -u root -p hrms_db < hrms_dump.sql\n\n"
            + mysql_schema_sql() + "\n\n" + rendered_inserts() + "\n"
        )
        dump.write_text(body, encoding="utf-8")
        print("wrote", dump, "(rendered INSERTs)")

    (DOCS_DIR / "er_diagram.md").write_text(er_diagram(), encoding="utf-8")
    print("wrote", DOCS_DIR / "er_diagram.md")


if __name__ == "__main__":
    main()
