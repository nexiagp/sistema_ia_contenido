"""Prueba manual de imagen que reutiliza el flujo seguro de producción.

Genera una imagen solo cuando se ejecuta explícitamente y la copia a
``data/test_images/``. Uso: ``python test_image.py``.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

from src.ai.services.image_service import DEFAULT_SIZE, ImageService

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "test_images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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


def generate_image(prompt: str, size: str = DEFAULT_SIZE, quality: str = "medium") -> Path:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("Falta OPENAI_API_KEY en .env")
    result = ImageService().generate(prompt, size=size, quality=quality)
    return ROOT / "data" / "images" / result.filename


def main() -> None:
    load_env()

    # Seleccionar prompt por argumento o usar el primero
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if idx >= len(PROMPTS):
        print(f"Índice fuera de rango. Disponibles: 0-{len(PROMPTS)-1}")
        sys.exit(1)

    entry = PROMPTS[idx]
    print(f"\n[gpt-image-2] Generando con el flujo validado: {entry['label']}")
    print(f"Prompt: {entry['prompt'][:100]}...")

    image_path = generate_image(entry["prompt"])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"{entry['id']}_{ts}.png"
    shutil.copy2(image_path, out_path)

    print(f"\nOK Imagen guardada en: {out_path}")
    print(f"  Tamaño: {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
