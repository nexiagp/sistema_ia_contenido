from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BRAND_LOGO_PUBLIC_ID = "nexiagp/brand/logo-ngp"

# Cloudinary only handles the logo overlay (the chocolate frame and
# blurred outer strip are composed in Pillow before upload).
# Logo size as fraction of the FINAL (already framed) image, positioned
# inside the chocolate line so it does not overlap the blurred strip.
DEFAULT_OVERLAY = (
    "l_nexiagp:brand:logo-ngp,w_0.16,fl_relative,g_south_east,x_70,y_70,o_88"
)


class CloudinaryService:
    def __init__(self) -> None:
        self.cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
        self.api_key = os.environ.get("CLOUDINARY_API_KEY", "")
        self.api_secret = os.environ.get("CLOUDINARY_API_SECRET", "")

    @property
    def enabled(self) -> bool:
        return bool(self.cloud_name and self.api_key and self.api_secret)

    def upload_image(self, local_path: Path, public_id: str | None = None) -> dict:
        if not self.enabled:
            raise RuntimeError("Credenciales de Cloudinary no configuradas")

        public_id = public_id or f"nexiagp/posts/img_{uuid.uuid4().hex[:14]}"
        ts = int(time.time())
        params_to_sign = f"public_id={public_id}&timestamp={ts}"
        signature = hashlib.sha1((params_to_sign + self.api_secret).encode()).hexdigest()

        boundary = f"----Nexia{uuid.uuid4().hex}"
        image_bytes = local_path.read_bytes()

        def part(name: str, value: str) -> bytes:
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{local_path.name}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode()
        body += image_bytes
        body += b"\r\n"
        body += part("public_id", public_id)
        body += part("timestamp", str(ts))
        body += part("api_key", self.api_key)
        body += part("signature", signature)
        body += f"--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            f"https://api.cloudinary.com/v1_1/{self.cloud_name}/image/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(raw).get("error", {}).get("message") or raw
            except Exception:
                msg = raw
            raise RuntimeError(f"Cloudinary upload error {exc.code}: {msg}") from exc

    def build_branded_url(self, public_id: str, version: int | None = None, transformation: str | None = None) -> str:
        base = f"https://res.cloudinary.com/{self.cloud_name}/image/upload"
        overlay = transformation or DEFAULT_OVERLAY
        version_seg = f"/v{version}" if version else ""
        return f"{base}/{overlay}{version_seg}/{public_id}.png"

    def build_raw_url(self, public_id: str, version: int | None = None) -> str:
        base = f"https://res.cloudinary.com/{self.cloud_name}/image/upload"
        version_seg = f"/v{version}" if version else ""
        return f"{base}{version_seg}/{public_id}.png"
