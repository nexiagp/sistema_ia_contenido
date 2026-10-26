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
        self.assertNotIn("wp-image-77", captured["content"])
        self.assertIn("<p>Cuerpo.</p>", captured["content"])
        self.assertEqual(result["post"]["postId"], 123)

    def test_export_keeps_inline_images_and_only_available_resources(self) -> None:
        source = """
        <article class="blog-post"><h1>Artículo</h1>
          <figure data-figure-id="hero"></figure>
          <p>Introducción.</p>
          <figure data-figure-id="detail"></figure>
          <aside class="lead-magnet"><h3>Guía futura</h3><span class="lm-pending">descargar</span></aside>
          <aside class="lead-magnet"><h3>Guía real</h3><a href="https://nexiagp.com/guia/">Descargar</a></aside>
        </article>
        """
        media = {
            "hero": {"mediaId": 1, "sourceUrl": "https://nexiagp.com/hero.jpg"},
            "detail": {"mediaId": 2, "sourceUrl": "https://nexiagp.com/detail.jpg"},
        }

        result = clean_wordpress_article(source, media, featured_figure_id="hero")

        self.assertNotIn("wp-image-1", result)
        self.assertIn("wp-image-2", result)
        self.assertNotIn("Guía futura", result)
        self.assertIn("Guía real", result)

    def test_sync_applies_rank_math_fields_only_when_wordpress_registers_them(self) -> None:
        service = WordPressService(base_url="https://example.com", username="editor", application_password="test")
        captured: dict = {}

        def request(path: str, **kwargs):
            self.assertEqual(path, "posts?context=edit")
            self.assertEqual(kwargs["method"], "OPTIONS")
            return {
                "endpoints": [{
                    "args": {
                        "meta": {
                            "properties": {
                                "rank_math_title": {"type": "string"},
                                "rank_math_description": {"type": "string"},
                                "rank_math_focus_keyword": {"type": "string"},
                            }
                        }
                    }
                }]
            }

        def upsert(**kwargs):
            captured.update(kwargs)
            return {"postId": 456, "postUrl": "https://example.com/rank-math/", "editUrl": "https://example.com/edit", "status": "draft"}

        service._request = request  # type: ignore[method-assign]
        service.upsert_draft = upsert  # type: ignore[method-assign]
        blog = {
            "id": "blog_rank_math",
            "title": "Título visible",
            "slug": "titulo-visible",
            "metaTitle": "Título SEO | Nexia GP",
            "metaDescription": "Descripción SEO para Rank Math.",
            "brief": {"primary_keyword": "automatización de contenidos B2B"},
            "article": {"article_html": "<article><h1>Título visible</h1><p>Cuerpo.</p></article>"},
            "figures": [],
        }

        result = service.sync_blog_draft(blog, image_loader=lambda _image: (_ for _ in ()).throw(AssertionError("No hay imágenes")))

        self.assertEqual(captured["rank_math_meta"], {
            "rank_math_title": "Título SEO | Nexia GP",
            "rank_math_description": "Descripción SEO para Rank Math.",
            "rank_math_focus_keyword": "automatización de contenidos B2B",
        })
        self.assertTrue(result["post"]["rankMath"]["detected"])
        self.assertFalse(result["post"]["rankMath"]["manualReview"])

    def test_rank_math_falls_back_to_manual_review_when_meta_is_not_exposed(self) -> None:
        service = WordPressService(base_url="https://example.com", username="editor", application_password="test")
        service._request = lambda *_args, **_kwargs: {"endpoints": []}  # type: ignore[method-assign]

        self.assertEqual(service.rank_math_meta_fields(), set())
        self.assertEqual(
            service.rank_math_meta_values(set(), meta_title="Título", meta_description="Descripción", focus_keyword="keyword"),
            {},
        )


if __name__ == "__main__":
    unittest.main()
