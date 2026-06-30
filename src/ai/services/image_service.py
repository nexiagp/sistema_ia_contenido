from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path


OPENAI_BASE_URL = "https://api.openai.com/v1"
IMAGE_MODEL = "gpt-image-2"

_ROOT = Path(__file__).resolve().parents[3]
IMAGES_DIR = _ROOT / "data" / "images"


class ImageService:
    def generate(
        self,
        prompt: str,
        size: str = "1344x768",
        quality: str = "medium",
    ) -> tuple[str, int]:
        """Generate an image, save to disk, return (filename, size_bytes)."""
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("Falta OPENAI_API_KEY")

        payload = json.dumps({
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
            "output_format": "png",
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            f"{OPENAI_BASE_URL}/images/generations",
            data=payload,
            headers={
                "authorization": f"Bearer {key}",
                "content-type": "application/json",
            },
            method="POST",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(raw).get("error", {}).get("message") or raw
            except Exception:
                msg = raw
            raise RuntimeError(f"OpenAI image error {exc.code}: {msg}") from exc

        item = data["data"][0]
        if "b64_json" in item:
            image_bytes = base64.b64decode(item["b64_json"])
        elif "url" in item:
            with urllib.request.urlopen(item["url"], timeout=60) as r:
                image_bytes = r.read()
        else:
            raise RuntimeError(f"Formato de respuesta inesperado: {list(item.keys())}")

        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"img_{uuid.uuid4().hex[:14]}.png"
        (IMAGES_DIR / filename).write_bytes(image_bytes)
        return filename, len(image_bytes)
