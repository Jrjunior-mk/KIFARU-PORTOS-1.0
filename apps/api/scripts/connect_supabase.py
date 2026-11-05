"""Connect KIFARU PORTOS to a Supabase PostgreSQL project (or any hosted PostgreSQL).

    python scripts/connect_supabase.py --url "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres"
    python scripts/connect_supabase.py --url "..." --no-seed          # migrations only
    python scripts/connect_supabase.py --url "..." --env-file .env    # default: apps/api/.env (git-ignored)

What it does, in order:
  1. normalises the URI to the SQLAlchemy driver form (postgresql+psycopg://) and masks the password in all output;
  2. opens a connection and prints the server version;
  3. creates the core / pii / ts schemas and runs `alembic upgrade head`;
  4. seeds roles, stations, lanes, vehicles and the demo accounts unless users already exist (or --no-seed);
  5. writes KIFARU_DATABASE_URL into the env file so `uvicorn kifaru.main:app` uses the hosted database.

Nothing here prints the password. Run it from apps/api with the project virtualenv.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent


def normalise(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    if not url.startswith("postgresql+psycopg://"):
        raise SystemExit("expected a postgresql:// URI (copy it from Supabase Dashboard > Connect)")
    return url


def masked(url: str) -> str:
    return re.sub(r"://([^:/@]+):([^@]+)@", lambda m: f"://{m.group(1)}:****@", url)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=False, help="PostgreSQL URI; defaults to $SUPABASE_DB_URL or $KIFARU_DATABASE_URL")
    ap.add_argument("--env-file", default=str(API_DIR / ".env"))
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--no-env", action="store_true", help="do not write the env file")
    a = ap.parse_args(argv)

    raw = a.url or os.environ.get("SUPABASE_DB_URL") or os.environ.get("KIFARU_DATABASE_URL")
    if not raw or raw.startswith("sqlite"):
        raise SystemExit("no PostgreSQL URI given (--url)")
    url = normalise(raw)
    print(f"database: {masked(url)}")
    os.environ["KIFARU_DATABASE_URL"] = url
    os.chdir(API_DIR)
    sys.path.insert(0, str(API_DIR))

    from sqlalchemy import select, text

    from kifaru.config import get_settings

    get_settings.cache_clear()
    from kifaru.db import ensure_schemas, get_engine, get_sessionmaker, reset_engine

    reset_engine()
    engine = get_engine()
    with engine.connect() as c:
        print("connected:", c.execute(text("select version()")).scalar().split(",")[0])
    ensure_schemas(engine)
    print("schemas core/pii/ts ensured")

    env = dict(os.environ, KIFARU_DATABASE_URL=url)
    rc = subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, cwd=API_DIR)
    if rc != 0:
        raise SystemExit("alembic upgrade failed")
    print("migrations: head")

    if not a.no_seed:
        from kifaru.models import User

        with get_sessionmaker()() as db:
            has_users = db.execute(select(User).limit(1)).scalar_one_or_none() is not None
        if has_users:
            print("seed: skipped (users already exist)")
        else:
            from kifaru.seed import seed

            seed(verbose=True)

    if not a.no_env:
        path = Path(a.env_file)
        lines = path.read_text(encoding="utf8").splitlines() if path.exists() else []
        lines = [ln for ln in lines if not ln.startswith("KIFARU_DATABASE_URL=")]
        lines.append(f"KIFARU_DATABASE_URL={url}")
        path.write_text("\n".join(lines) + "\n", encoding="utf8")
        print(f"env file: {path} (KIFARU_DATABASE_URL set; file is git-ignored)")
    print("done. Start the API with: python -m uvicorn kifaru.main:app --port 8000")
    print("For Vercel: set the same value as KIFARU_DATABASE_URL (use the transaction pooler, port 6543) in the project environment variables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
