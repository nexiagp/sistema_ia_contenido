"""Offline contracts for manufacturer research sources and scheduler rotation."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import server
from src.domain.manufacturer_sources import default_manufacturer_sources, ensure_manufacturer_sources


class ManufacturerSourceTests(unittest.TestCase):
    def test_catalogue_has_verified_https_sites_and_x_is_opt_in(self) -> None:
        sources = default_manufacturer_sources()
        self.assertGreaterEqual(len(sources), 20)
        self.assertEqual(len({source["id"] for source in sources}), len(sources))
        for source in sources:
            self.assertTrue(source["website"]["url"].startswith("https://"))
            self.assertTrue(source["website"]["enabled"])
            self.assertFalse(source["social"]["x"]["enabled"])

    def test_soft_migration_preserves_operator_settings(self) -> None:
        db = {
            "manufacturerSources": [{
                "id": "altuna",
                "name": "Altuna Group",
                "website": {"enabled": False, "lastStatus": "updated"},
                "social": {"x": {"enabled": True, "handle": "altuna"}},
            }]
        }
        sources = ensure_manufacturer_sources(db)
        altuna = next(source for source in sources if source["id"] == "altuna")
        self.assertFalse(altuna["website"]["enabled"])
        self.assertEqual(altuna["website"]["lastStatus"], "updated")
        self.assertTrue(altuna["social"]["x"]["enabled"])
        self.assertEqual(altuna["social"]["x"]["handle"], "altuna")

    def test_parser_discovers_public_x_link_without_enabling_it(self) -> None:
        parser = server.ManufacturerPageParser()
        parser.feed('<html><title>Marca</title><body><p>Soluciones profesionales</p><a href="https://x.com/marca_oficial">X</a></body></html>')
        social = server._manufacturer_social_link("https://x.com/marca_oficial")
        self.assertEqual("Marca", " ".join(parser.title_parts))
        self.assertIn("Soluciones profesionales", parser.text_parts)
        self.assertEqual(social, {"network": "x", "url": "https://x.com/marca_oficial", "candidateHandle": "marca_oficial"})

    def test_scheduler_rotates_every_active_theme(self) -> None:
        db = {
            "settings": {"schedulerThemeCursor": 0},
            "themes": [
                {"id": "a", "active": True},
                {"id": "paused", "active": False},
                {"id": "b", "active": True},
                {"id": "c", "active": True},
            ],
        }
        first, cursor = server.next_scheduled_theme(db)
        self.assertEqual((first["id"], cursor), ("a", 1))
        db["settings"]["schedulerThemeCursor"] = cursor
        second, cursor = server.next_scheduled_theme(db)
        self.assertEqual((second["id"], cursor), ("b", 2))
        db["settings"]["schedulerThemeCursor"] = cursor
        third, cursor = server.next_scheduled_theme(db)
        self.assertEqual((third["id"], cursor), ("c", 0))

    def test_daily_x_monitor_does_not_call_network_without_private_token(self) -> None:
        with patch.dict("os.environ", {"X_API_BEARER_TOKEN": ""}, clear=False):
            result = server.sync_enabled_manufacturer_x_sources()
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["updated"], 0)
        self.assertIn("no configurado", result["skipped"])

    def test_openai_sync_can_be_bounded_to_requested_files(self) -> None:
        target = {
            "id": "target", "name": "target.md", "mimeType": "text/markdown",
            "category": "fabricante", "status": "local_only",
        }
        skipped = {
            "id": "skipped", "name": "skipped.md", "mimeType": "text/markdown",
            "category": "fabricante", "status": "local_only",
        }
        db = {"settings": {"vectorStoreId": "vs_test"}, "files": [target, skipped]}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}, clear=False), \
             patch.object(server, "read_db", return_value=db), \
             patch.object(server, "write_db") as write_db, \
             patch.object(server, "read_source_file_bytes", return_value=b"# source"), \
             patch.object(server, "upload_openai_file", return_value={"id": "file_openai"}) as upload, \
             patch.object(server, "attach_file_to_vector_store", return_value={"id": "vector_file"}), \
             patch.object(server, "poll_vector_store_file", return_value={"status": "completed"}):
            result = server.sync_files_to_openai({"target"})

        self.assertEqual(len(result["synced"]), 1)
        self.assertEqual(result["synced"][0]["id"], "target")
        self.assertEqual(target["status"], "completed")
        self.assertEqual(skipped["status"], "local_only")
        self.assertEqual(upload.call_count, 1)
        write_db.assert_called_once_with(db)


if __name__ == "__main__":
    unittest.main()
