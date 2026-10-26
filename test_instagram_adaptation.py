"""Instagram copy must be available for review without implying account access."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.ai.services.adaptation_service import AdaptationService
from src.ai.services.pipeline_service import _adaptations_complete


class OfflineClient:
    enabled = False


class InstagramAdaptationTests(unittest.TestCase):
    def test_offline_adaptation_has_instagram_caption_and_limited_hashtags(self) -> None:
        service = AdaptationService(OfflineClient())
        validation = {
            "final_post": "El canal B2B necesita criterio.\n\nLa distribución local aporta continuidad.",
            "cta": "Hablemos de Canarias.",
            "hashtags": ["#Canarias", "#Industria", "#B2B", "#Distribucion", "#NexiaGP", "#Extra"],
        }

        adaptations, response_id = service.adapt({}, validation, {})

        self.assertIsNone(response_id)
        self.assertTrue(_adaptations_complete(adaptations))
        self.assertIn("canal B2B", adaptations["instagram"]["caption"])
        self.assertEqual(len(adaptations["instagram"]["hashtags"]), 5)

    def test_schema_requires_instagram_and_strips_unusable_web_links(self) -> None:
        schema_path = Path(__file__).parent / "src" / "ai" / "schemas" / "adaptation.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertIn("instagram", schema["required"])

        result = AdaptationService._enforce_instagram_caption({
            "instagram": {"caption": "Visita https://example.com/info para saber más", "cta": "Comenta", "hashtags": ["#B2B"] * 7}
        })
        self.assertNotIn("https://", result["instagram"]["caption"])
        self.assertEqual(len(result["instagram"]["hashtags"]), 5)


if __name__ == "__main__":
    unittest.main()
