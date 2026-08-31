"""Minimal Supabase REST adapter used by the Python application.

Keeping this adapter dependency-free lets the local single-file mode continue to
work while Vercel uses Supabase as the durable state and object store.
"""
from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class SupabaseStoreError(RuntimeError):
    """A non-secret, actionable error returned by Supabase."""


@dataclass(frozen=True)
class StoredState:
    state: dict[str, Any]
    version: int


class SupabaseStore:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.service_key and os.getenv("SUPABASE_STATE_BACKEND") == "1")

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Any | None = None,
        headers: dict[str, str] | None = None,
        raw: bool = False,
    ) -> Any:
        if not self.enabled:
            raise SupabaseStoreError("Supabase no está configurado para este entorno.")
        body = None
        request_headers = {
            "apikey": self.service_key,
            "authorization": f"Bearer {self.service_key}",
        }
        if headers:
            request_headers.update(headers)
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            request_headers.setdefault("content-type", "application/json")
        request = urllib.request.Request(f"{self.url}{path}", data=body, method=method, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
                if raw:
                    return data, dict(response.headers.items())
                if not data:
                    return None
                return json.loads(data.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:1200]
            raise SupabaseStoreError(f"Supabase devolvió HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise SupabaseStoreError(f"No se pudo conectar con Supabase: {exc.reason}") from exc

    def read_state(self) -> StoredState:
        rows = self._request("/rest/v1/app_state?id=eq.1&select=version,state") or []
        if not rows:
            raise SupabaseStoreError("El estado de NexiaGP todavía no ha sido migrado a Supabase.")
        row = rows[0]
        state = row.get("state")
        if not isinstance(state, dict):
            raise SupabaseStoreError("El estado remoto de NexiaGP no tiene un formato válido.")
        return StoredState(state=state, version=int(row.get("version") or 0))

    def seed_state(self, state: dict[str, Any]) -> None:
        self._request(
            "/rest/v1/app_state",
            method="POST",
            payload={"id": 1, "state": state},
            headers={"prefer": "resolution=ignore-duplicates,return=minimal"},
        )

    def replace_state(self, state: dict[str, Any], expected_version: int) -> int:
        response = self._request(
            "/rest/v1/rpc/replace_app_state",
            method="POST",
            payload={"p_state": state, "p_expected_version": expected_version, "p_updated_by": None},
        )
        if not isinstance(response, list) or not response:
            raise SupabaseStoreError("Supabase no confirmó la actualización atómica del estado.")
        return int(response[0].get("version") or 0)

    def upload_object(self, bucket: str, object_path: str, content: bytes, mime_type: str | None = None) -> None:
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in object_path.split("/"))
        # Storage bucket allow-lists compare the media type itself, not HTTP
        # parameters.  Keep a caller's useful type while stripping values such
        # as ``; charset=utf-8`` that Supabase correctly rejects as a distinct
        # MIME type.
        content_type = (mime_type or mimetypes.guess_type(object_path)[0] or "application/octet-stream").split(";", 1)[0].strip()
        if not content_type:
            content_type = "application/octet-stream"
        request = urllib.request.Request(
            f"{self.url}/storage/v1/object/{urllib.parse.quote(bucket, safe='')}/{encoded_path}",
            data=content,
            method="POST",
            headers={
                "apikey": self.service_key,
                "authorization": f"Bearer {self.service_key}",
                "content-type": content_type,
                "x-upsert": "true",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90):
                return
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:1200]
            raise SupabaseStoreError(f"No se pudo guardar el archivo en Supabase (HTTP {exc.code}): {details}") from exc

    def download_object(self, bucket: str, object_path: str) -> tuple[bytes, dict[str, str]]:
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in object_path.split("/"))
        return self._request(f"/storage/v1/object/{urllib.parse.quote(bucket, safe='')}/{encoded_path}", raw=True)

    def object_size(self, bucket: str, object_path: str) -> int:
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in object_path.split("/"))
        request = urllib.request.Request(
            f"{self.url}/storage/v1/object/{urllib.parse.quote(bucket, safe='')}/{encoded_path}",
            method="HEAD",
            headers={"apikey": self.service_key, "authorization": f"Bearer {self.service_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return int(response.headers.get("content-length") or -1)
        except urllib.error.HTTPError as exc:
            raise SupabaseStoreError(f"No se pudo verificar el objeto remoto (HTTP {exc.code}).") from exc

    def delete_object(self, bucket: str, object_path: str) -> None:
        self._request(
            f"/storage/v1/object/{urllib.parse.quote(bucket, safe='')}",
            method="DELETE",
            payload={"prefixes": [object_path]},
        )

    def authenticated_user(self, access_token: str) -> dict[str, Any]:
        """Return the Supabase user represented by a browser-issued JWT.

        The service key is only used as the API key. The bearer token remains the
        user's token, so Supabase performs the authoritative session validation.
        """
        token = str(access_token or "").strip()
        if not token:
            raise SupabaseStoreError("Falta la sesión de acceso.")
        request = urllib.request.Request(
            f"{self.url}/auth/v1/user",
            method="GET",
            headers={
                "apikey": self.service_key,
                "authorization": f"Bearer {token}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:500]
            raise SupabaseStoreError(f"La sesión de Supabase no es válida (HTTP {exc.code}): {details}") from exc
        except urllib.error.URLError as exc:
            raise SupabaseStoreError(f"No se pudo validar la sesión con Supabase: {exc.reason}") from exc
        if not isinstance(payload, dict) or not payload.get("id"):
            raise SupabaseStoreError("Supabase no devolvió una identidad de usuario válida.")
        return payload

    def active_member(self, user_id: str) -> dict[str, Any] | None:
        encoded_id = urllib.parse.quote(str(user_id), safe="")
        rows = self._request(
            f"/rest/v1/app_members?user_id=eq.{encoded_id}&active=is.true&select=user_id,role,active"
        ) or []
        return rows[0] if rows else None

    def ensure_admin(self, email: str) -> dict[str, Any]:
        """Create (without email delivery) and authorize the initial admin.

        This trusted, server-only operation intentionally does not use
        user_metadata for authorization. The user id is persisted in
        ``app_members`` and checked on every API request.
        """
        normalized_email = str(email or "").strip().lower()
        if not normalized_email or "@" not in normalized_email:
            raise SupabaseStoreError("El correo del administrador no es válido.")

        users = self._request("/auth/v1/admin/users?page=1&per_page=1000") or {}
        candidates = users.get("users", []) if isinstance(users, dict) else []
        user = next(
            (item for item in candidates if str(item.get("email") or "").lower() == normalized_email),
            None,
        )
        if user is None:
            created = self._request(
                "/auth/v1/admin/users",
                method="POST",
                payload={"email": normalized_email, "email_confirm": True},
            ) or {}
            user = created.get("user", created) if isinstance(created, dict) else {}
        user_id = str(user.get("id") or "")
        if not user_id:
            raise SupabaseStoreError("No se pudo crear ni localizar el usuario administrador en Supabase Auth.")
        rows = self._request(
            "/rest/v1/app_members",
            method="POST",
            payload={"user_id": user_id, "role": "admin", "active": True},
            headers={"prefer": "resolution=merge-duplicates,return=representation"},
        ) or []
        member = rows[0] if rows else self.active_member(user_id)
        if not member or member.get("role") != "admin":
            raise SupabaseStoreError("Supabase no confirmó el permiso de administrador inicial.")
        return {"id": user_id, "email": normalized_email, "role": "admin"}

    def create_generation_job(self, job_id: str, kind: str, request: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "/rest/v1/generation_jobs",
            method="POST",
            payload={
                "id": job_id,
                "kind": kind,
                "status": "queued",
                "request": request,
                "progress": progress,
            },
            headers={"prefer": "return=representation"},
        ) or []
        if not rows:
            raise SupabaseStoreError("Supabase no confirmó la cola de generación.")
        return rows[0]

    def get_generation_job(self, job_id: str) -> dict[str, Any] | None:
        encoded_id = urllib.parse.quote(str(job_id), safe="")
        rows = self._request(
            f"/rest/v1/generation_jobs?id=eq.{encoded_id}&select=*"
        ) or []
        return rows[0] if rows else None

    def claim_generation_job(self, lease_seconds: int = 780) -> dict[str, Any] | None:
        rows = self._request(
            "/rest/v1/rpc/claim_generation_job",
            method="POST",
            payload={"p_lease_seconds": max(60, int(lease_seconds))},
        ) or []
        return rows[0] if rows else None

    def update_generation_job(self, job_id: str, values: dict[str, Any]) -> dict[str, Any]:
        encoded_id = urllib.parse.quote(str(job_id), safe="")
        rows = self._request(
            f"/rest/v1/generation_jobs?id=eq.{encoded_id}",
            method="PATCH",
            payload=values,
            headers={"prefer": "return=representation"},
        ) or []
        if not rows:
            raise SupabaseStoreError("El trabajo de generación ya no existe.")
        return rows[0]
