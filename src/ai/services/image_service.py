from __future__ import annotations

import base64
import binascii
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.domain.visual import IMAGE_FORMATS


OPENAI_BASE_URL = "https://api.openai.com/v1"
IMAGE_MODEL = "gpt-image-2"

# Product-supported presets. The API can evolve independently, but keeping a
# small validated matrix makes framing, visual review and per-article budgets
# predictable across the application.
SUPPORTED_SIZES = {
    size: (spec["width"], spec["height"])
    for size, spec in IMAGE_FORMATS.items()
}
SUPPORTED_QUALITIES = {"low", "medium", "high", "auto"}
DEFAULT_SIZE = "1536x1024"
DEFAULT_QUALITY = "medium"
MAX_PROMPT_CHARS = 4_800
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MIN_IMAGE_BYTES = 4 * 1024
MAX_ATTEMPTS = 2

# Internal planning estimates for one image, in cents. They are guardrails,
# not invoice values: the live provider calculator and image-token usage are
# the source of truth. "auto" is budgeted at the high tier so a project does
# not silently exceed the selected article ceiling.
GPT_IMAGE_2_ESTIMATED_COST_CENTS = {
    "low": {
        "1536x1024": 0.5,
        "1024x1024": 0.6,
        "1024x1536": 0.5,
    },
    "medium": {
        "1536x1024": 4.1,
        "1024x1024": 5.3,
        "1024x1536": 4.1,
    },
    "high": {
        "1536x1024": 16.5,
        "1024x1024": 21.1,
        "1024x1536": 16.5,
    },
}


def _reference_cost(size: str, quality: str) -> tuple[float, int]:
    """Pick a conservative documented-format baseline for a custom size."""
    width, height = SUPPORTED_SIZES[size]
    if width == height:
        reference = "1024x1024"
    elif height > width:
        reference = "1024x1536"
    else:
        reference = "1536x1024"
    base_cost = GPT_IMAGE_2_ESTIMATED_COST_CENTS[quality][reference]
    base_width, base_height = SUPPORTED_SIZES[reference]
    return base_cost, base_width * base_height

_ROOT = Path(__file__).resolve().parents[3]


def image_work_dir() -> Path:
    """Return the writable staging directory for generated image bytes.

    Vercel functions mount the deployment bundle as read-only.  The image is
    therefore staged under the system temporary directory there and immediately
    persisted by the caller in Supabase Storage.  Local development keeps the
    existing ``data/images`` behaviour, including the local ``/images`` route.
    """
    if os.getenv("VERCEL") == "1":
        return Path(tempfile.gettempdir()) / "nexiagp-images"
    return _ROOT / "data" / "images"


def uses_ephemeral_image_work_dir() -> bool:
    """Whether generated-image files must not be retained as durable state."""
    return os.getenv("VERCEL") == "1"


IMAGES_DIR = image_work_dir()


class ImageGenerationError(RuntimeError):
    """A message safe to show to the editor without leaking request details."""


@dataclass(frozen=True)
class ImageResult:
    filename: str
    size_bytes: int
    width: int
    height: int
    image_format: str
    attempts: int

    def validation(self) -> dict[str, object]:
        return {
            "valid": True,
            "format": self.image_format,
            "width": self.width,
            "height": self.height,
            "attempts": self.attempts,
        }


def normalize_image_request(size: str | None, quality: str | None) -> tuple[str, str]:
    """Accept only API-supported image settings, with safe defaults."""
    normalized_size = (size or DEFAULT_SIZE).strip()
    normalized_quality = (quality or DEFAULT_QUALITY).strip().lower()
    if normalized_size not in SUPPORTED_SIZES:
        allowed = ", ".join(SUPPORTED_SIZES)
        raise ImageGenerationError(f"Formato de imagen no admitido. Usa uno de: {allowed}.")
    if normalized_quality not in SUPPORTED_QUALITIES:
        raise ImageGenerationError("Calidad de imagen no admitida.")
    return normalized_size, normalized_quality


def estimate_gpt_image_cost_cents(size: str | None, quality: str | None) -> float:
    """Return a conservative pre-generation cost estimate for one image.

    This covers the documented image-output charge only. Text/image input
    tokens used by an edit or a separate prompt-generation call are variable,
    so callers must present this as an estimate rather than an invoice.
    """
    normalized_size, normalized_quality = normalize_image_request(size, quality)
    billable_quality = "high" if normalized_quality == "auto" else normalized_quality
    known_cost = GPT_IMAGE_2_ESTIMATED_COST_CENTS[billable_quality].get(normalized_size)
    if known_cost is not None:
        return known_cost
    # GPT Image 2 supports flexible resolutions. For product-only formats that
    # are not shown in the provider's comparison table, budget from the closest
    # documented orientation and scale by canvas area. This remains an internal
    # guardrail, not a billing assertion.
    base_cost, base_pixels = _reference_cost(normalized_size, billable_quality)
    width, height = SUPPORTED_SIZES[normalized_size]
    # Do not present a custom format as cheaper than the closest documented
    # orientation: provider billing can be bucketed rather than pixel-linear.
    return round(max(base_cost, base_cost * ((width * height) / base_pixels)), 1)


def prepare_image_prompt(prompt: str) -> str:
    """Produce a bounded, production-safe prompt shared by posts and blogs."""
    cleaned = " ".join((prompt or "").split())
    if len(cleaned) < 24:
        raise ImageGenerationError("La dirección visual no tiene suficiente detalle para generar una imagen fiable.")
    cleaned = cleaned[:MAX_PROMPT_CHARS].rstrip()
    return (
        f"{cleaned}\n\n"
        "Production requirements: one coherent photorealistic editorial scene, "
        "professionally composed. No text, lettering, captions, logos, watermarks, "
        "brand marks, signage, interface elements, collage, split screen, or infographic. "
        "No maps, charts, diagrams, plans, readable documents or technical drawings. "
        "Avoid stock-photo posing, duplicated subjects, distorted anatomy and invented product labels."
    )


class ImageService:
    def generate(
        self,
        prompt: str,
        size: str = DEFAULT_SIZE,
        quality: str = DEFAULT_QUALITY,
    ) -> ImageResult:
        """Generate, validate and atomically persist one production-ready PNG.

        A failed, corrupt or wrongly sized response is never written to the image
        library and therefore can never replace the editor's previous image.
        """
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ImageGenerationError("Falta la configuración de OpenAI para generar imágenes.")

        size, quality = normalize_image_request(size, quality)
        safe_prompt = prepare_image_prompt(prompt)
        image_bytes, attempts = self._request_image(key, safe_prompt, size, quality)
        return self._persist_validated_png(image_bytes, size=size, attempts=attempts)

    @staticmethod
    def _payload(prompt: str, size: str, quality: str) -> bytes:
        return json.dumps(
            {
                "model": IMAGE_MODEL,
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": quality,
                "output_format": "png",
                "moderation": "auto",
            },
            ensure_ascii=False,
        ).encode("utf-8")

    def _request_image(self, key: str, prompt: str, size: str, quality: str) -> tuple[bytes, int]:
        payload = self._payload(prompt, size, quality)
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            req = urllib.request.Request(
                f"{OPENAI_BASE_URL}/images/generations",
                data=payload,
                headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
                method="POST",
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with opener.open(req, timeout=180) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                data = json.loads(raw) if raw else {}
                return self._extract_image_bytes(data), attempt
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 409, 429, 500, 502, 503, 504} or attempt == MAX_ATTEMPTS:
                    raise self._friendly_http_error(exc) from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ImageGenerationError) as exc:
                last_error = exc
                if attempt == MAX_ATTEMPTS:
                    raise ImageGenerationError(
                        "No se pudo obtener una imagen válida tras dos intentos. Conservamos la imagen anterior."
                    ) from exc
            time.sleep(1.2 * attempt)

        raise ImageGenerationError("No se pudo iniciar la generación de imagen.") from last_error

    @staticmethod
    def _extract_image_bytes(data: dict) -> bytes:
        items = data.get("data")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise ImageGenerationError("La API no devolvió una imagen utilizable.")
        encoded = items[0].get("b64_json")
        if not isinstance(encoded, str) or not encoded:
            # GPT Image with output_format=png should return base64 data. We do
            # not follow arbitrary response URLs, keeping the pipeline deterministic.
            raise ImageGenerationError("La API no devolvió el archivo de imagen esperado.")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ImageGenerationError("La imagen recibida está dañada.") from exc
        if not MIN_IMAGE_BYTES <= len(image_bytes) <= MAX_IMAGE_BYTES:
            raise ImageGenerationError("La imagen recibida no tiene un tamaño válido.")
        return image_bytes

    @staticmethod
    def _friendly_http_error(exc: urllib.error.HTTPError) -> ImageGenerationError:
        if exc.code == 400:
            return ImageGenerationError("La dirección visual o el formato no son compatibles con la generación de imagen.")
        if exc.code in {401, 403}:
            return ImageGenerationError("OpenAI no autorizó la generación de imagen. Revisa la configuración del proyecto.")
        if exc.code == 429:
            return ImageGenerationError("El servicio de imagen está temporalmente saturado. Espera un momento e inténtalo de nuevo.")
        return ImageGenerationError("El servicio de imagen no pudo completar la solicitud. La imagen anterior se mantiene intacta.")

    @staticmethod
    def _inspect_png(path: Path, expected_size: tuple[int, int]) -> tuple[int, int, str]:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                width, height = image.size
                image_format = image.format or ""
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageGenerationError("El archivo generado no es una imagen PNG válida.") from exc
        if image_format.upper() != "PNG":
            raise ImageGenerationError("El archivo generado no usa el formato PNG requerido.")
        if (width, height) != expected_size:
            raise ImageGenerationError(
                f"La imagen generada no respeta las dimensiones solicitadas ({expected_size[0]}x{expected_size[1]})."
            )
        return width, height, image_format.upper()

    def _persist_validated_png(self, image_bytes: bytes, *, size: str, attempts: int) -> ImageResult:
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"img_{uuid.uuid4().hex[:14]}.png"
        target = IMAGES_DIR / filename
        temporary = target.with_suffix(".tmp")
        try:
            temporary.write_bytes(image_bytes)
            width, height, image_format = self._inspect_png(temporary, SUPPORTED_SIZES[size])
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return ImageResult(
            filename=filename,
            size_bytes=len(image_bytes),
            width=width,
            height=height,
            image_format=image_format,
            attempts=attempts,
        )
