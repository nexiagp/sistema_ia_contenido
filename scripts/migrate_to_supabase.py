"""One-time, id-preserving migration of NexiaGP's local content assets.

Run with --dry-run first. Credentials are supplied as environment variables and
are intentionally never read from or written to this script.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import mimetypes
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.platform.supabase_store import SupabaseStore, SupabaseStoreError  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "".join(char if char.isalnum() or char in ".-_" else "-" for char in normalized)[:160] or "asset"


def all_files(path: Path) -> list[Path]:
    return sorted(file for file in path.rglob("*") if file.is_file()) if path.exists() else []


def map_registered_sources(state: dict, uploads: list[Path]) -> tuple[dict[str, Path], list[Path]]:
    by_name: dict[str, list[Path]] = {}
    for path in uploads:
        # Files imported by the app carry `file_<hex>-`; external KB files keep
        # their original hyphens and must not be truncated at the first one.
        names = [path.name]
        prefixed = re.match(r"^file_[a-z0-9]+-(.+)$", path.name, flags=re.I)
        if prefixed:
            names.append(prefixed.group(1))
        for name in names:
            by_name.setdefault(name.lower(), []).append(path)
    mapped: dict[str, Path] = {}
    used: set[Path] = set()
    for item in state.get("files", []):
        candidates = by_name.get(str(item.get("name") or "").lower(), [])
        candidate = next((path for path in candidates if path not in used), None)
        if candidate is not None:
            mapped[str(item.get("id"))] = candidate
            used.add(candidate)
    return mapped, [path for path in uploads if path not in used]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Upload objects and seed the remote state.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and write only the local manifest (default).")
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("Usa --apply o --dry-run, no ambos.")

    store = SupabaseStore()
    if not store.enabled:
        raise SystemExit("Configura SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY y SUPABASE_STATE_BACKEND=1.")

    state = json.loads((ROOT / "data" / "db.json").read_text(encoding="utf-8"))
    uploads = all_files(ROOT / "data" / "uploads")
    images = all_files(ROOT / "data" / "images")
    docs = all_files(ROOT / "Documentación Nexia")
    registered, orphan_uploads = map_registered_sources(state, uploads)
    manifest = {
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "apply" if args.apply else "dry-run",
        "state": {"posts": len(state.get("posts", [])), "blogs": len(state.get("blogs", [])), "files": len(state.get("files", []))},
        "assets": {"uploads": len(uploads), "images": len(images), "documentation": len(docs), "registeredSources": len(registered), "unmatchedUploads": len(orphan_uploads)},
        "missingRegisteredSources": [item.get("id") for item in state.get("files", []) if str(item.get("id")) not in registered],
        "objects": [],
    }

    upload_plan: list[tuple[str, str, Path]] = []

    def record(bucket: str, object_path: str, source: Path) -> None:
        manifest["objects"].append({"bucket": bucket, "path": object_path, "bytes": source.stat().st_size, "sha256": sha256(source)})
        upload_plan.append((bucket, object_path, source))

    for item in state.get("files", []):
        source = registered.get(str(item.get("id")))
        if source is None:
            continue
        object_path = f"sources/{item['id']}-{safe_name(item.get('name') or source.name)}"
        record("source-library", object_path, source)
        item["localPath"] = f"supabase://source-library/{object_path}"

    for source in orphan_uploads:
        record("source-library", f"unregistered/{sha256(source)[:16]}-{safe_name(source.name)}", source)
    for source in images:
        record("editorial-images", source.name, source)
    for source in docs:
        record("source-library", f"reference/{sha256(source)[:16]}-{safe_name(source.name)}", source)
    logo = ROOT / "Imágenes" / "Logo NGP.png"
    if logo.is_file():
        record("brand-assets", "logo-ngp.png", logo)

    manifest_path = ROOT / "data" / "migration-manifest-supabase.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.apply:
        # Object names are deterministic and storage upserts are idempotent. The
        # remote state is intentionally seeded only after every object succeeds.
        def upload(entry: tuple[str, str, Path]) -> None:
            bucket, object_path, source = entry
            store.upload_object(bucket, object_path, source.read_bytes(), mimetypes.guess_type(source.name)[0])

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(upload, entry) for entry in upload_plan]
            for future in as_completed(futures):
                future.result()
        store.seed_state(state)

    print(json.dumps({
        "mode": manifest["mode"],
        "state": manifest["state"],
        "assetCount": len(manifest["objects"]),
        "assetBytes": sum(item["bytes"] for item in manifest["objects"]),
        "missingRegisteredSources": len(manifest["missingRegisteredSources"]),
        "manifest": str(manifest_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SupabaseStoreError as exc:
        raise SystemExit(f"Migración Supabase fallida: {exc}") from exc
