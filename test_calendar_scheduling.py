"""Offline checks for calendar scheduling of long-form editorial pieces."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class CalendarSchedulingTests(unittest.TestCase):
    def test_blog_requires_review_then_persists_utc_schedule(self) -> None:
        blog = {
            "id": "blog_calendar",
            "status": "draft",
            "request": {"length": "corto", "images_per_article": 0},
            "brief": {},
            "retrieval": {"sources": [], "warnings": []},
            "article": {"article_html": "<article><h1>Plan editorial</h1><p>Contenido pendiente.</p></article>"},
            "seo": {},
        }
        db = {
            "settings": {},
            "themes": [],
            "postTypes": [],
            "files": [],
            "posts": [],
            "blogs": [blog],
            "schedulerLog": [],
            "prompt_overrides": {},
            "prompt_versions": {},
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "db.json"
            db_path.write_text(json.dumps(db), encoding="utf-8")
            with patch.object(server, "DB_PATH", db_path):
                with self.assertRaises(server.ApiError) as blocked:
                    server.patch_blog("blog_calendar", {"scheduledFor": "2026-09-10T09:30:00Z"})
                self.assertEqual(blocked.exception.status, 409)

                result = server.patch_blog(
                    "blog_calendar",
                    {"scheduledFor": "2026-09-10T09:30:00+02:00", "reviewAcknowledged": True},
                )
                persisted = json.loads(db_path.read_text(encoding="utf-8"))["blogs"][0]

        self.assertEqual(result["blog"]["status"], "scheduled")
        self.assertEqual(persisted["status"], "scheduled")
        self.assertEqual(persisted["scheduledFor"], "2026-09-10T07:30:00Z")
        self.assertTrue(persisted["qualityGate"]["reviewAcknowledgedAt"])


if __name__ == "__main__":
    unittest.main()
