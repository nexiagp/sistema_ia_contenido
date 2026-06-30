"""
Prueba rápida de gpt-image-2.
Genera una imagen a partir de un prompt B2B y la guarda en data/test_images/.
Uso: python test_image.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "test_images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_BASE_URL = "https://api.openai.com/v1"
MODEL = "gpt-image-2"

PROMPTS = [
    {
        "id": "distribucion_b2b",
        "label": "Distribución B2B en Canarias",
        "prompt": (
            "Professional B2B commercial scene in the Canary Islands. "
            "Two business professionals shaking hands in a modern warehouse with product pallets and shelves in the background. "
            "Warm Mediterranean light, clean and corporate aesthetic. "
            "Style: editorial photography look, photorealistic, high detail. "
            "No text, no logos."
        ),
    },
    {
        "id": "fabricante_socio",
        "label": "Fabricante y socio comercial",
        "prompt": (
            "Aerial view of a modern industrial distribution hub with trucks and logistics infrastructure. "
            "Clean corporate photography style, blue and warm tones, professional B2B atmosphere. "
            "Canary Islands landscape in the background with ocean visible. "
            "Photorealistic, cinematic lighting. No text, no logos."
        ),
    },
    {
        "id": "reunion_estrategia",
        "label": "Reunión de estrategia comercial",
        "prompt": (
            "Corporate meeting room with three business professionals reviewing charts and strategy documents on a table. "
            "Modern office, clean minimal design, natural light from large windows. "
            "Professional editorial photography look. B2B context. No text, no logos."
        ),
    },
]


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def generate_image(prompt: str, size: str = "1344x768", quality: str = "medium") -> bytes:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("Falta OPENAI_API_KEY en .env")

    payload = json.dumps({
        "model": MODEL,
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
        with opener.open(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(raw).get("error", {}).get("message") or raw
        except Exception:
            msg = raw
        raise RuntimeError(f"OpenAI error {exc.code}: {msg}") from exc

    item = data["data"][0]
    if "b64_json" in item:
        return base64.b64decode(item["b64_json"])
    if "url" in item:
        print(f"  (descargando desde URL...)")
        with urllib.request.urlopen(item["url"], timeout=60) as r:
            return r.read()
    raise RuntimeError(f"Respuesta inesperada de la API: {list(item.keys())}")


def main() -> None:
    load_env()

    # Seleccionar prompt por argumento o usar el primero
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if idx >= len(PROMPTS):
        print(f"Índice fuera de rango. Disponibles: 0-{len(PROMPTS)-1}")
        sys.exit(1)

    entry = PROMPTS[idx]
    print(f"\n[gpt-image-2] Generando: {entry['label']}")
    print(f"Prompt: {entry['prompt'][:100]}...")

    image_bytes = generate_image(entry["prompt"])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"{entry['id']}_{ts}.png"
    out_path.write_bytes(image_bytes)

    print(f"\nOK Imagen guardada en: {out_path}")
    print(f"  Tamaño: {len(image_bytes) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
