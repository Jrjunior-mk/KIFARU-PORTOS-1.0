"""Prepare the environment variables for a Vercel deployment and keep apps/api/.env consistent with them.

    python scripts/vercel_env_setup.py --project-url https://kifaru-portos-1-0.vercel.app            # print the commands
    python scripts/vercel_env_setup.py --project-url https://kifaru-portos-1-0.vercel.app --apply    # run `vercel env add` yourself

Values prepared (none are printed unless you pass --show):
  KIFARU_DATABASE_URL      the Supabase URL from apps/api/.env, switched to the transaction pooler port 6543 (serverless)
  KIFARU_JWT_SECRET        a new strong random secret (also written to apps/api/.env so local and Vercel match)
  KIFARU_PII_KEY_B64       pinned to the key the dev configuration has derived so far, so PII already in the database stays readable
  KIFARU_SIGNING_SEED_B64  pinned likewise, so tickets and tokens already signed keep verifying
  KIFARU_PUBLIC_BASE_URL   the deployment URL (used in QR codes)
  KIFARU_ENV=dev, KIFARU_LOCAL_OBJECT_DIR=/tmp/kifaru-objects

Rotating the PII key and signing seed to fresh values is a separate, deliberate step (re-encrypt and re-sign), see
docs/06-operations/supabase-postgres.md. Run this script from apps/api with the project virtualenv.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import subprocess
import sys
from pathlib import Path

API = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project-url", required=True)
    ap.add_argument("--scope", default=None, help="Vercel team slug, e.g. jrsnr")
    ap.add_argument("--apply", action="store_true", help="run `vercel env add` for production and preview")
    ap.add_argument("--show", action="store_true", help="print the values (secrets) instead of masking them")
    a = ap.parse_args()

    from kifaru.config import Settings

    env_path = API / ".env"
    lines = env_path.read_text(encoding="utf8").splitlines() if env_path.exists() else []
    env = dict(ln.split("=", 1) for ln in lines if "=" in ln and not ln.startswith("#"))
    db = env.get("KIFARU_DATABASE_URL", "")
    if not db.startswith("postgresql"):
        raise SystemExit("apps/api/.env has no PostgreSQL KIFARU_DATABASE_URL; run scripts/connect_supabase.py first")
    dev_default = Settings.model_fields["jwt_secret"].default
    derived_pii = base64.b64encode(hashlib.sha256(("kifaru-dev-pii:" + dev_default).encode()).digest()).decode()
    derived_seed = base64.b64encode(hashlib.sha256(("kifaru-dev-signing:" + dev_default).encode()).digest()).decode()
    values = {
        "KIFARU_DATABASE_URL": db.replace(":5432/", ":6543/"),
        "KIFARU_JWT_SECRET": env.get("KIFARU_JWT_SECRET") or secrets.token_urlsafe(48),
        "KIFARU_PII_KEY_B64": env.get("KIFARU_PII_KEY_B64") or derived_pii,
        "KIFARU_SIGNING_SEED_B64": env.get("KIFARU_SIGNING_SEED_B64") or derived_seed,
        "KIFARU_PUBLIC_BASE_URL": a.project_url.rstrip("/"),
        "KIFARU_ENV": "dev",
        "KIFARU_LOCAL_OBJECT_DIR": "/tmp/kifaru-objects",
    }
    # keep local in step (same JWT secret, same pinned keys) so both environments read the same database correctly
    local = {**env, "KIFARU_JWT_SECRET": values["KIFARU_JWT_SECRET"], "KIFARU_PII_KEY_B64": values["KIFARU_PII_KEY_B64"], "KIFARU_SIGNING_SEED_B64": values["KIFARU_SIGNING_SEED_B64"]}
    env_path.write_text("\n".join(f"{k}={v}" for k, v in local.items()) + "\n", encoding="utf8")
    print(f"local {env_path} updated (git-ignored)")

    scope = f" --scope {a.scope}" if a.scope else ""
    for k, v in values.items():
        shown = v if (a.show or k in ("KIFARU_PUBLIC_BASE_URL", "KIFARU_ENV", "KIFARU_LOCAL_OBJECT_DIR")) else "****"
        print(f"{k} = {shown}")
    if not a.apply:
        print("\nTo add them to Vercel yourself, rerun with --apply (uses your `vercel` login), or paste the values in the dashboard")
        print("(Project > Settings > Environment Variables, environments Production and Preview). Use --show to display them.")
        return 0
    for k, v in values.items():
        for target in ("production", "preview"):
            cmd = f'npx --yes vercel@latest env add {k} {target}{scope} --yes'
            r = subprocess.run(cmd, input=v, text=True, shell=True, capture_output=True, cwd=API.parent.parent)
            tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
            print(f"{k} [{target}]: {'ok' if r.returncode == 0 else 'FAILED'} {tail[0][:120]}")
    print("\nDone. Trigger a new deployment so the variables take effect: npx vercel@latest deploy --prod" + scope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
