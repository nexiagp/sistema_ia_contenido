#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sube la KB externa (data/uploads/kb-externa) a OpenAI Files + Vector Store.

- Reutiliza las funciones ya probadas de server.py (no arranca el servidor).
- Sube al Vector Store configurado en settings (ensure_vector_store).
- Es RESUMIBLE: guarda db.json tras cada archivo y salta los ya subidos
  (los que ya tienen openaiFileId). Si se corta, se relanza sin re-subir.
- Solo toca archivos de categoria "kb-*" (la KB sectorial), nunca los 12
  archivos web/copywriting ya existentes.

Uso:
    python scripts/upload_kb.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # carga .env al importar (load_env() en el modulo)


def register_kb_files(db: dict) -> int:
    """Registra en db['files'] los PDFs de kb-externa que aun no esten. Sin copiar a disco."""
    existing_paths = {f.get("localSourcePath") for f in db["files"]}
    existing_names = {f.get("name") for f in db["files"]}
    added = 0
    for doc in server.list_local_documents():
        if not str(doc["category"]).startswith("kb-"):
            continue
        path = Path(doc["path"])
        safe_name = server.sanitize_filename(doc["name"])
        if str(path) in existing_paths or safe_name in existing_names:
            continue
        now = server.now_iso()
        db["files"].append({
            "id": server.uid("file"),
            "name": safe_name,
            "category": doc["category"],
            "source": "kb_externa_import",
            "localPath": str(path),          # apunta al PDF existente (sin duplicar)
            "localSourcePath": str(path),
            "mimeType": server.mime_from_filename(doc["name"]) or "application/pdf",
            "size": path.stat().st_size,
            "status": "local_only",
            "openaiFileId": None,
            "vectorStoreId": db["settings"].get("vectorStoreId", ""),
            "vectorStoreFileId": None,
            "error": None,
            "createdAt": now,
            "updatedAt": now,
        })
        added += 1
    return added


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: falta OPENAI_API_KEY (.env).")
        return 1

    db = server.read_db()
    added = register_kb_files(db)
    server.write_db(db)
    print(f"Registrados {added} PDFs de KB nuevos (los ya presentes se saltan).")

    vsid = server.ensure_vector_store(db)
    server.write_db(db)
    pending = [f for f in db["files"]
               if str(f.get("category", "")).startswith("kb-") and not f.get("openaiFileId")]
    total = len(pending)
    print(f"Vector Store destino: {vsid}")
    print(f"Pendientes de subir: {total}\n")

    ok = fail = 0
    for i, item in enumerate(pending, 1):
        name = item.get("name", "?")
        local_path = item.get("localPath")
        try:
            buffer = Path(local_path).read_bytes()
            upload = server.upload_openai_file(buffer, name, item.get("mimeType") or "application/pdf")
            vfile = server.attach_file_to_vector_store(vsid, upload["id"], item.get("category") or "general", name)
            completed = server.poll_vector_store_file(vsid, vfile.get("id") or upload["id"])
            item["status"] = completed.get("status") or "in_progress"
            item["openaiFileId"] = upload["id"]
            item["vectorStoreId"] = vsid
            item["vectorStoreFileId"] = vfile.get("id") or upload["id"]
            item["error"] = (completed.get("last_error") or {}).get("message") if completed.get("last_error") else None
            item["updatedAt"] = server.now_iso()
            server.write_db(db)  # guardar tras cada archivo => resumible
            ok += 1
            print(f"[{i}/{total}] OK   {name[:58]:58} -> {item['status']}")
        except Exception as exc:  # noqa: BLE001
            item["status"] = "failed"
            item["error"] = str(exc)
            item["updatedAt"] = server.now_iso()
            server.write_db(db)
            fail += 1
            print(f"[{i}/{total}] FAIL {name[:58]:58} -> {exc}")

    print(f"\nResultado: {ok} subidos correctamente, {fail} con error.")
    if fail:
        print("Relanza el script para reintentar solo los fallidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
