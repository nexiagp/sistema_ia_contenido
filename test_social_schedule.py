"""The social handoff must keep human approval and the scheduled time separate."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from server import ApiError, apply_post_edits, publish_post


class SocialScheduleTests(unittest.TestCase):
    def test_approval_is_required_before_scheduling_and_publication_waits_for_date(self) -> None:
        post = {"status": "draft", "generation": {"copy": {}}, "validation": {}}
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        with self.assertRaises(ApiError) as blocked:
            apply_post_edits(post, {"scheduledFor": future, "reviewAcknowledged": True})
        self.assertEqual(blocked.exception.code, "editorial_approval_required")

        apply_post_edits(post, {"status": "ready", "reviewAcknowledged": True})
        self.assertTrue(post["editorialApprovedAt"])
        apply_post_edits(post, {"scheduledFor": future})
        self.assertEqual(post["status"], "scheduled")

        with patch.dict("os.environ", {"SOCIAL_WEBHOOK_URL": "https://example.com/social"}):
            with self.assertRaises(ApiError) as early:
                publish_post({}, post, require_webhook=True)
        self.assertEqual(early.exception.code, "scheduled_time_pending")
        self.assertEqual(post["status"], "scheduled")

    def test_editing_a_scheduled_post_requires_fresh_approval(self) -> None:
        post = {
            "status": "scheduled",
            "scheduledFor": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "editorialApprovedAt": datetime.now(timezone.utc).isoformat(),
            "generation": {"copy": {}},
            "validation": {},
        }

        apply_post_edits(post, {"copy": "Texto actualizado"})

        self.assertEqual(post["status"], "review")
        self.assertNotIn("scheduledFor", post)
        self.assertNotIn("editorialApprovedAt", post)


if __name__ == "__main__":
    unittest.main()
