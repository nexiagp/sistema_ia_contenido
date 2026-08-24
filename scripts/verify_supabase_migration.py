"""Verify remote state and every object declared by the migration manifest."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.platform.supabase_store import SupabaseStore  # noqa: E402


def main() -> int:
    store = SupabaseStore()
    state = store.read_state()
    manifest = json.loads((ROOT / "data" / "migration-manifest-supabase.json").read_text(encoding="utf-8"))
    mismatches = []
    for asset in manifest["objects"]:
        if store.object_size(asset["bucket"], asset["path"]) != asset["bytes"]:
            mismatches.append(asset["path"])
    print(json.dumps({
        "stateVersion": state.version,
        "posts": len(state.state.get("posts", [])),
        "blogs": len(state.state.get("blogs", [])),
        "files": len(state.state.get("files", [])),
        "objectsChecked": len(manifest["objects"]),
        "mismatches": len(mismatches),
    }, ensure_ascii=False))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
