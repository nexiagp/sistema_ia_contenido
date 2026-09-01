"""Offline persistence checks for the server-side WordPress handoff."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class _FakeWordPressService:
    enabled = True

    def public_config(self) -> dict:
        return {"configured": True, "baseUrl": "https://nexiagp.com"}

    def sync_blog_draft(self, blog: dict, **_kwargs) -> dict:
        return {
            "post": {
                "postId": 701,
                "postUrl": "https://nexiagp.com/piloto-wordpress/",
                "editUrl": "https://nexiagp.com/wp-admin/post.php?post=701&action=edit",
                "status": "draft",
            },
            "figures": {"hero": {"mediaId": 811, "sourceUrl": "https://nexiagp.com/uploads/hero.jpg", "sourceImageUrl": "/images/hero.png", "bytes": 120000}},
            "uploadedImages": 1,
            "optimizedBytes": 120000,
            "contentHash": "a" * 64,
        }


class WordPressServerSyncTests(unittest.TestCase):
    def test_refresh_keeps_the_recorded_editorial_acknowledgement(self) -> None:
        review_time = "2026-09-01T10:00:00Z"
        blog = {
            "article": {"article_html": "<article><h1>Piloto</h1><p>Cuerpo.</p></article>"},
            "qualityGate": {"blockers": ["Revisar la fuente"], "reviewAcknowledgedAt": review_time},
        }
        refreshed_gate = {"blockers": ["Revisar la fuente"], "can_mark_ready": False}

        with patch.object(server, "blog_quality_gate", return_value=({}, {}, refreshed_gate)):
            result = server.refresh_blog_quality_gate(blog)

        self.assertEqual(result["reviewAcknowledgedAt"], review_time)
        self.assertTrue(result["reviewAcknowledged"])
        self.assertTrue(result["can_mark_ready"])

    def test_public_vercel_deployment_cannot_trigger_wordpress_writes(self) -> None:
        with patch.dict(os.environ, {"VERCEL": "1", "NEXIAGP_AUTH_REQUIRED": "0"}, clear=False):
            with self.assertRaises(server.ApiError) as blocked:
                server.AppHandler.require_wordpress_sync_access(None)

        self.assertEqual(blocked.exception.status, 503)
        self.assertEqual(blocked.exception.code, "wordpress_auth_required")

    def test_successful_draft_sync_persists_public_traceability_and_never_marks_published(self) -> None:
        blog = {
            "id": "blog_wordpress_pilot",
            "status": "ready",
            "request": {"length": "medio", "images_per_article": 1},
            "article": {"article_html": "<article><h1>Piloto</h1><figure data-figure-id=\"hero\"></figure><p>Cuerpo.</p></article>"},
            "seo": {},
            "figures": [{"figure_id": "hero", "image": {"url": "/images/hero.png"}}],
            "qualityGate": {"blockers": [], "reviewAcknowledged": False},
        }
        db = {
            "settings": {}, "themes": [], "postTypes": [], "files": [], "posts": [],
            "blogs": [blog], "schedulerLog": [], "prompt_overrides": {}, "prompt_versions": {},
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "db.json"
            db_path.write_text(json.dumps(db), encoding="utf-8")
            with (
                patch.object(server, "DB_PATH", db_path),
                patch.object(server, "WordPressService", _FakeWordPressService),
                patch.object(server, "refresh_blog_quality_gate", return_value={"blockers": []}),
            ):
                result = server.sync_blog_to_wordpress_draft("blog_wordpress_pilot")
            persisted = json.loads(db_path.read_text(encoding="utf-8"))["blogs"][0]

        self.assertTrue(result["ok"])
        self.assertEqual(persisted["status"], "ready")
        self.assertNotEqual(persisted["status"], "published")
        self.assertEqual(persisted["wordpress"]["postId"], 701)
        self.assertEqual(persisted["figures"][0]["wordpress"]["mediaId"], 811)
        self.assertIsNone(persisted["wordpress"]["lastError"])

    def test_reviewed_blog_can_sync_when_the_gate_is_refreshed(self) -> None:
        blog = {
            "id": "blog_reviewed_wordpress_pilot",
            "status": "ready",
            "request": {"length": "medio", "images_per_article": 0},
            "article": {"article_html": "<article><h1>Piloto</h1><p>Cuerpo.</p></article>", "word_count": 2},
            "seo": {},
            "figures": [],
            "qualityGate": {"blockers": ["Revisar la fuente"], "reviewAcknowledgedAt": "2026-09-01T10:00:00Z"},
        }
        db = {
            "settings": {}, "themes": [], "postTypes": [], "files": [], "posts": [],
            "blogs": [blog], "schedulerLog": [], "prompt_overrides": {}, "prompt_versions": {},
        }
        refreshed_article = dict(blog["article"])

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "db.json"
            db_path.write_text(json.dumps(db), encoding="utf-8")
            with (
                patch.object(server, "DB_PATH", db_path),
                patch.object(server, "WordPressService", _FakeWordPressService),
                patch.object(server, "blog_quality_gate", return_value=(refreshed_article, {}, {"blockers": ["Revisar la fuente"]})),
            ):
                result = server.sync_blog_to_wordpress_draft("blog_reviewed_wordpress_pilot")

        self.assertTrue(result["ok"])

    def test_draft_cannot_sync_to_wordpress_before_editorial_approval(self) -> None:
        blog = {
            "id": "blog_waiting_approval",
            "status": "draft",
            "request": {"length": "medio", "images_per_article": 0},
            "article": {"article_html": "<article><h1>Piloto</h1><p>Cuerpo.</p></article>"},
            "seo": {},
            "figures": [],
            "qualityGate": {"blockers": [], "reviewAcknowledged": False},
        }
        db = {
            "settings": {}, "themes": [], "postTypes": [], "files": [], "posts": [],
            "blogs": [blog], "schedulerLog": [], "prompt_overrides": {}, "prompt_versions": {},
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "db.json"
            db_path.write_text(json.dumps(db), encoding="utf-8")
            with (
                patch.object(server, "DB_PATH", db_path),
                patch.object(server, "WordPressService", _FakeWordPressService),
                patch.object(server, "refresh_blog_quality_gate", return_value={"blockers": []}),
            ):
                with self.assertRaises(server.ApiError) as blocked:
                    server.sync_blog_to_wordpress_draft("blog_waiting_approval")

        self.assertEqual(blocked.exception.status, 409)
        self.assertEqual(blocked.exception.code, "blog_not_ready_for_wordpress")


if __name__ == "__main__":
    unittest.main()
