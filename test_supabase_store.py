"""Offline contracts for the Supabase storage adapter."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.platform.supabase_store import SupabaseStore


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class SupabaseStoreTests(unittest.TestCase):
    def test_upload_strips_content_type_parameters_for_bucket_allow_lists(self) -> None:
        environment = {
            "SUPABASE_URL": "https://project.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
            "SUPABASE_STATE_BACKEND": "1",
        }
        with patch.dict(os.environ, environment, clear=False), patch(
            "src.platform.supabase_store.urllib.request.urlopen", return_value=_Response()
        ) as urlopen:
            SupabaseStore().upload_object(
                "source-library",
                "sources/fabricante-airum-web.md",
                b"# Airum",
                "text/markdown; charset=utf-8",
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Content-type"), "text/markdown")


if __name__ == "__main__":
    unittest.main()
