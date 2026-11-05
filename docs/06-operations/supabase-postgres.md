# Supabase PostgreSQL for KIFARU PORTOS

Project: **KIFARU-PORTOS**, reference `myftjzmpshjoopgfibzp`
(https://supabase.com/dashboard/project/myftjzmpshjoopgfibzp). The platform uses Supabase only as a hosted
PostgreSQL: the API connects with the database password over TLS and owns its own schemas (`core`, `pii`, `ts`).
Supabase's REST/GraphQL API, anon key and service-role key are **not** used, and the schemas are not added to the
API-exposed list, so nothing is reachable through Supabase's public endpoints. Access is only through the KIFARU API
(JWT + RBAC + MFA) or by someone who holds the database password.

## 1. Get the connection string

Dashboard → project → **Connect** (top bar) → **Session pooler** tab (IPv4, works from any network) → copy the URI.
It looks like

```
postgresql://postgres.myftjzmpshjoopgfibzp:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Replace `[YOUR-PASSWORD]` with the database password (Project Settings → Database → *Reset database password* if you
no longer have it). The **Transaction pooler** URI (port 6543) is the one to use for Vercel serverless functions.
The **Direct** URI (`db.<ref>.supabase.co:5432`) is IPv6-only on the free plan and often fails from home networks.

## 2. Connect the local API (one command)

```bash
cd apps/api
../../.venv/Scripts/python scripts/connect_supabase.py --url "postgresql://postgres.myftjzmpshjoopgfibzp:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres"
```

The script tests the connection, creates the schemas, runs `alembic upgrade head` (0001 initial, 0002 RCS v2),
seeds the demo data once (skipped if users already exist) and writes `KIFARU_DATABASE_URL` into `apps/api/.env`
(git-ignored). The password never appears in its output. Then start the API as usual; the web app does not change.

The driver (`kifaru/db.py`) recognises `*.supabase.com` and sets `sslmode=require` and `prepare_threshold=None`
(transaction-mode poolers cannot track server-side prepared statements). Flags `KIFARU_DB_REQUIRE_SSL` and
`KIFARU_DB_POOLER_TRANSACTION_MODE` force the same behaviour for other hosts.

## 3. Point the Vercel demo at it

Vercel → project `kifaru-portos` → Settings → Environment Variables → add for Production (and Preview):

| Variable | Value |
|---|---|
| `KIFARU_DATABASE_URL` | the **transaction pooler** URI with `postgresql+psycopg://` prefix, port 6543 |
| `KIFARU_JWT_SECRET`, `KIFARU_SIGNING_SEED_B64`, `KIFARU_PII_KEY_B64` | long random secrets (see `.env.example`); keep the existing ones if already set |
| `KIFARU_ACCESS_TOKEN_MINUTES` | can go back to `15` now that refresh sessions are durable |

`api/index.py` also accepts `SUPABASE_DB_URL`, `POSTGRES_URL` or `DATABASE_URL` (the names the Supabase ↔ Vercel
Marketplace integration injects). Redeploy once; the first cold start runs the seed because the database is empty,
after that every instance shares the same data and simulated passes, tokens and release orders persist.

## 4. Keeping it private

- The database password is the only credential; store it in Vercel env vars and the local `.env`, never in git
  (`.env*` is ignored; `.vercelignore` excludes it from uploads).
- Rotate it from Project Settings → Database if it is ever exposed, then rerun the connect script and update Vercel.
- Keep the Supabase project on its own organisation (as it is) and do not invite collaborators who do not need it.
- Network restrictions (allow-listing Vercel's egress ranges) and SSL enforcement toggles are in Project Settings →
  Database; network restrictions need a paid plan.
- Row-level security is irrelevant here because the Supabase API is not used; the KIFARU API enforces tenancy
  (`org_scope`) and roles itself.
- Backups: free plan has no point-in-time recovery; `docs/06-operations/backup-and-retention.md` applies
  (`pg_dump` on a schedule from a machine that holds the password).

## 5. Checks

```bash
cd apps/api && ../../.venv/Scripts/python -m pytest -q          # KIFARU_TEST_DATABASE_URL=<uri> runs the suite on Postgres
curl https://kifaru-portos.vercel.app/ready                     # {"status":"ready"} once the env var is live
```
