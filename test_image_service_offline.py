"""Pruebas sin red para el contrato de imagen y composición de marca."""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
import unittest
from unittest.mock import patch

from PIL import Image

from src.ai.services import image_service
from src.ai.services.frame_composer import compose_branded_frame
from src.ai.services.image_service import (
    ImageGenerationError,
    ImageService,
    estimate_gpt_image_cost_cents,
    normalize_image_request,
    prepare_image_prompt,
)
from server import ApiError, publish_post


def png_bytes(size: tuple[int, int]) -> bytes:
    image = Image.effect_noise(size, 96).convert("RGB")
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class ImageServiceOfflineTests(unittest.TestCase):
    def test_vercel_stages_images_under_the_system_temp_directory(self) -> None:
        with patch.dict(os.environ, {"VERCEL": "1"}, clear=False):
            self.assertEqual(image_service.image_work_dir(), Path(gettempdir()) / "nexiagp-images")
            self.assertTrue(image_service.uses_ephemeral_image_work_dir())

    def test_only_documented_sizes_and_qualities_are_accepted(self) -> None:
        self.assertEqual(normalize_image_request(None, None), ("1536x1024", "medium"))
        self.assertEqual(normalize_image_request("1024x1536", "HIGH"), ("1024x1536", "high"))
        self.assertEqual(normalize_image_request("1088x1360", "medium"), ("1088x1360", "medium"))
        self.assertEqual(normalize_image_request("2048x1152", "low"), ("2048x1152", "low"))
        with self.assertRaises(ImageGenerationError):
            normalize_image_request("1344x768", "medium")
        with self.assertRaises(ImageGenerationError):
            normalize_image_request("1024x1024", "ultra")

    def test_prompt_has_hard_branding_exclusions(self) -> None:
        prompt = prepare_image_prompt("A real distribution team coordinating an inbound shipment at a Canary Islands dock.")
        self.assertIn("No text, lettering, captions, logos", prompt)
        self.assertIn("No maps, charts, diagrams, plans", prompt)
        self.assertIn("Avoid stock-photo posing", prompt)

    def test_flexible_product_formats_have_a_conservative_cost_estimate(self) -> None:
        portrait_cost = estimate_gpt_image_cost_cents("1088x1360", "medium")
        blog_cost = estimate_gpt_image_cost_cents("2048x1152", "medium")
        self.assertGreater(portrait_cost, 0)
        self.assertGreater(blog_cost, portrait_cost)

    def test_valid_png_is_persisted_atomically(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            original_directory = image_service.IMAGES_DIR
            image_service.IMAGES_DIR = Path(temporary_dir)
            try:
                result = ImageService()._persist_validated_png(
                    png_bytes((1536, 1024)), size="1536x1024", attempts=1
                )
            finally:
                image_service.IMAGES_DIR = original_directory

            output = Path(temporary_dir) / result.filename
            self.assertTrue(output.is_file())
            self.assertEqual((result.width, result.height, result.image_format), (1536, 1024, "PNG"))
            self.assertEqual(result.validation()["valid"], True)

    def test_wrong_dimensions_leave_no_file_behind(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            original_directory = image_service.IMAGES_DIR
            image_service.IMAGES_DIR = Path(temporary_dir)
            try:
                with self.assertRaises(ImageGenerationError):
                    ImageService()._persist_validated_png(
                        png_bytes((1024, 1024)), size="1536x1024", attempts=1
                    )
            finally:
                image_service.IMAGES_DIR = original_directory

            self.assertEqual(list(Path(temporary_dir).iterdir()), [])

    def test_brand_frame_is_written_as_a_valid_png(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "source.png"
            destination = root / "branded.png"
            Image.new("RGB", (400, 300), (44, 91, 104)).save(source, format="PNG")

            compose_branded_frame(source, destination)

            with Image.open(destination) as result:
                result.verify()
            with Image.open(destination) as result:
                self.assertEqual(result.format, "PNG")
                self.assertEqual(result.size, (432, 332))

    def test_manual_publish_is_rejected_without_a_connected_webhook(self) -> None:
        post = {"status": "ready"}
        with patch.dict("os.environ", {"SOCIAL_WEBHOOK_URL": ""}):
            with self.assertRaises(ApiError) as captured:
                publish_post({}, post, require_webhook=True)
        self.assertEqual(captured.exception.status, 409)
        self.assertEqual(post["status"], "ready")


if __name__ == "__main__":
    unittest.main()
