"""Offline checks for source traceability, editorial gates and safe blog output."""
from __future__ import annotations

import json
import unittest

from server import ApiError, apply_post_edits
from src.ai.services.content_quality import (
    blog_quality_gate,
    canonicalize_retrieval,
    post_quality_gate,
    sanitize_article_html,
)


class ContentQualityTests(unittest.TestCase):
    def test_remote_sources_are_matched_to_the_catalog(self) -> None:
        retrieval = {
            "query_used": "canal B2B",
            "context_summary": "Resumen no verificado.",
            "sources": [
                {
                    "source_id": "0",
                    "title": "NEXIAGP_KB",
                    "entity": "nexia",
                    "source_group": "inventado",
                    "excerpt": "Soporte documental.",
                    "relevance": "high",
                },
                {
                    "source_id": "0",
                    "title": "NEXIAGP_KB",
                    "entity": "nexia",
                    "source_group": "inventado",
                    "excerpt": "Segundo fragmento del mismo archivo.",
                    "relevance": "medium",
                },
                {
                    "source_id": "7",
                    "title": "Fuente inexistente",
                    "entity": "nexia",
                    "source_group": "web",
                    "excerpt": "No debe pasar.",
                    "relevance": "medium",
                },
            ],
            "confidence": "high",
            "warnings": [],
        }
        files = [{"id": "file_catalogada", "name": "NEXIAGP_KB.txt", "category": "brand"}]

        normalized = canonicalize_retrieval(retrieval, files)

        self.assertEqual(len(normalized["sources"]), 1)
        self.assertEqual(normalized["sources"][0]["source_id"], "file_catalogada")
        self.assertEqual(normalized["sources"][0]["source_group"], "nexia_core")
        self.assertEqual(normalized["confidence"], "medium")
        self.assertTrue(any("excluyeron" in warning for warning in normalized["warnings"]))

    def test_validator_flag_is_a_real_ready_gate(self) -> None:
        validation = {
            "review_flags": ["too_generic_risk"],
            "human_review_required": False,
            "risk_level": "low",
            "validation_notes": [],
        }
        gate = post_quality_gate(
            {"tipo_post": "educativo_autoridad"},
            {"post_type": "educativo_autoridad", "factual_sensitivity": "medium"},
            {"sources": [{"source_id": "file_1"}], "confidence": "high", "warnings": []},
            validation,
        )

        self.assertFalse(gate["can_mark_ready"])
        self.assertTrue(validation["human_review_required"])
        self.assertEqual(validation["risk_level"], "medium")

    def test_vector_file_id_maps_back_to_local_catalog_id(self) -> None:
        normalized = canonicalize_retrieval(
            {
                "sources": [{
                    "source_id": "file_openai_123",
                    "title": "Nombre alternativo.pdf",
                    "entity": "canarias",
                    "source_group": "kb-logistica",
                    "excerpt": "Fragmento recuperado de la búsqueda vectorial.",
                    "relevance": "high",
                }],
                "warnings": [],
                "confidence": "high",
            },
            [{
                "id": "file_local_123",
                "openaiFileId": "file_openai_123",
                "name": "D01_AP-Tenerife-Memoria-Anual-2024.pdf",
                "category": "kb-logistica",
            }],
        )

        self.assertEqual(normalized["sources"][0]["source_id"], "file_local_123")
        self.assertEqual(normalized["sources"][0]["source_group"], "official_data")

    def test_ready_transition_requires_explicit_review_acknowledgement(self) -> None:
        post = {
            "status": "draft",
            "qualityGate": {"blockers": ["Flag editorial"], "can_mark_ready": False},
            "generation": {"copy": {}},
            "validation": {},
        }
        with self.assertRaises(ApiError) as captured:
            apply_post_edits(post, {"status": "ready"})
        self.assertEqual(captured.exception.status, 409)

        apply_post_edits(post, {"status": "ready", "reviewAcknowledged": True})
        self.assertEqual(post["status"], "ready")
        self.assertTrue(post["qualityGate"]["reviewAcknowledgedAt"])

    def test_blog_html_removes_active_content_and_fake_downloads(self) -> None:
        raw_html = (
            '<article><h1>Guía</h1><p onclick="alert(1)">Contenido</p>'
            '<script>alert("x")</script><a class="lm-download" href="javascript:alert(2)">Descargar</a>'
            '<a href="https://nexiagp.com/contacto/">Contactar</a></article>'
        )
        cleaned = sanitize_article_html(raw_html)

        self.assertNotIn("script", cleaned.lower())
        self.assertNotIn("onclick", cleaned.lower())
        self.assertNotIn("javascript:", cleaned.lower())
        self.assertIn("lm-pending", cleaned)
        self.assertIn('href="https://nexiagp.com/contacto/"', cleaned)

    def test_blog_gate_uses_actual_word_count_and_valid_schema(self) -> None:
        article = {
            "article_html": "<article><h1>Guía B2B</h1><figure data-figure-id=\"hero\"><figcaption>Imagen</figcaption></figure><p>"
            + "criterio " * 820
            + "</p></article>",
            "word_count": 1,
            "figure_slots": [],
            "internal_links_used": [{"anchor": "Contacto", "url_path": "/contacto/"}],
        }
        seo = {
            "slug": "guia-b2b",
            "canonical_path": "/guia-b2b/",
            "schema_jsonld": json.dumps({"@context": "https://schema.org", "@type": "Article"}),
            "seo_review_flags": [],
        }
        clean_article, clean_seo, gate = blog_quality_gate(
            {"length": "corto", "images_per_article": 1},
            {},
            {"sources": [{"source_id": "file_1"}], "warnings": []},
            article,
            seo,
        )

        self.assertGreaterEqual(clean_article["word_count"], 800)
        self.assertEqual(clean_seo["canonical_path"], "/guia-b2b/")
        self.assertTrue(gate["can_mark_ready"])


if __name__ == "__main__":
    unittest.main()
