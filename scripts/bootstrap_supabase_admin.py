"""Create and authorize the first NexiaGP Content administrator.

Run with server-only Supabase credentials supplied through the environment. This
script does not send an email; the authorised user later requests their own
passwordless link from the deployed sign-in screen.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.platform.supabase_store import SupabaseStore, SupabaseStoreError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    store = SupabaseStore()
    if not store.enabled:
        raise SystemExit("SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY y SUPABASE_STATE_BACKEND=1 son obligatorios.")
    try:
        result = store.ensure_admin(args.email)
    except SupabaseStoreError as exc:
        raise SystemExit(f"No se pudo preparar el administrador: {exc}") from exc
    print(json.dumps({"ok": True, "email": result["email"], "role": result["role"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
