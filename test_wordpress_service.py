"""Offline contract checks for the WordPress blog handoff."""
from __future__ import annotations

from io import BytesIO
import unittest

from PIL import Image

from src.ai.services.wordpress_service import (
    MAX_WORDPRESS_IMAGE_BYTES,
    PREFERRED_IMAGE_BYTES,
    WordPressService,
    clean_wordpress_article,
    prepare_wordpress_image,
)


def noisy_png() -> bytes:
    image = Image.effect_noise((1600, 1000), 90).convert("RGB")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class WordPressImageTests(unittest.TestCase):
    def test_image_is_a_web_safe_jpeg_under_the_hard_limit(self) -> None:
        prepared = prepare_wordpress_image(noisy_png(), "Cabecera Nexia.png")

        self.assertEqual(prepared.content_type, "image/jpeg")
        self.assertTrue(prepared.filename.endswith(".jpg"))
        self.assertLessEqual(len(prepared.content), MAX_WORDPRESS_IMAGE_BYTES)
        self.assertLessEqual(prepared.width, 1600)
        self.assertLessEqual(prepared.height, 1000)

    def test_small_image_stays_within_the_preferred_size_target(self) -> None:
        image = Image.new("RGB", (1200, 675), (25, 117, 119))
        output = BytesIO()
        image.save(output, format="PNG")

        prepared = prepare_wordpress_image(output.getvalue(), "portada.png")

        self.assertLessEqual(len(prepared.content), PREFERRED_IMAGE_BYTES)


class WordPressArticleTests(unittest.TestCase):
    def test_wordpress_content_removes_duplicate_header_and_injects_media(self) -> None:
        source = """
        <article class="blog-post">
          <header class="blog-header"><h1>Un título duplicado</h1><p>Por Nexia GP</p></header>
          <figure data-figure-id="hero"><figcaption>Equipo de distribución</figcaption></figure>
          <p>Contenido que debe permanecer.</p>
        </article>
        """
        result = clean_wordpress_article(
            source,
            {
                "hero": {
                    "mediaId": 88,
                    "sourceUrl": "https://nexiagp.com/wp-content/uploads/portada.jpg",
                    "alt": "Equipo de distribución",
                    "caption": "Equipo de distribución",
                }
            },
        )

        self.assertNotIn("blog-header", result)
        self.assertNotIn("<h1", result)
        self.assertIn('class="wp-image-88"', result)
        self.assertIn("Contenido que debe permanecer.", result)
        self.assertIn("wp-element-caption", result)

    def test_sync_reuses_existing_media_and_marks_the_hero_as_featured(self) -> None:
        service = WordPressService(base_url="https://example.com", username="editor", application_password="test")
        captured: dict = {}

        def fail_if_loaded(_image: dict):
            raise AssertionError("No se debe descargar una imagen ya sincronizada")

        def upsert(**kwargs):
            captured.update(kwargs)
            return {"postId": 123, "postUrl": "https://example.com/demo/", "editUrl": "https://example.com/edit", "status": "draft"}

        service.upsert_draft = upsert  # type: ignore[method-assign]
        blog = {
            "id": "blog_demo",
            "title": "Demo de automatización",
            "slug": "demo-automatizacion",
            "metaDescription": "Extracto del piloto.",
            "article": {"article_html": '<article class="blog-post"><h1>Demo</h1><figure data-figure-id="hero"></figure><p>Cuerpo.</p></article>'},
            "figures": [{
                "figure_id": "hero",
                "caption": "Imagen de portada",
                "image": {"url": "/images/demo.png"},
                "wordpress": {"mediaId": 77, "sourceUrl": "https://example.com/uploads/demo.jpg", "sourceImageUrl": "/images/demo.png", "bytes": 110000},
            }],
        }

        result = service.sync_blog_draft(blog, image_loader=fail_if_loaded)

        self.assertEqual(result["uploadedImages"], 0)
        self.assertEqual(captured["featured_media_id"], 77)
        self.assertIn("wp-image-77", captured["content"])
        self.assertEqual(result["post"]["postId"], 123)


if __name__ == "__main__":
    unittest.main()
