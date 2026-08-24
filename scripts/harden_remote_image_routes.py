"""Replace legacy Cloudinary display URLs with authenticated Nexia image routes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.platform.supabase_store import SupabaseStore, SupabaseStoreError


def image_filename(url: object) -> str | None:
    value = str(url or "")
    if not value.startswith("/images/"):
        return None
    name = value.rsplit("/", 1)[-1]
    return name if name and "/" not in name and "\\" not in name else None


def routed_image(store: SupabaseStore, image: dict) -> bool:
    raw_name = image_filename(image.get("url"))
    if not raw_name:
        return False
    stem = Path(raw_name).stem
    suffix = Path(raw_name).suffix or ".png"
    wants_frame = bool((image.get("config") or {}).get("withFrame"))
    framed_name = f"{stem}_framed{suffix}"
    display_name = raw_name
    if wants_frame:
        try:
            store.object_size("editorial-images", framed_name)
            display_name = framed_name
        except SupabaseStoreError:
            # Preserve a usable image even for historic rows without the local
            # framed counterpart.
            display_name = raw_name
    display_url = f"/images/{display_name}"
    changed = False
    for key, value in (("displayUrl", display_url), ("brandedUrl", display_url if wants_frame else None)):
        if image.get(key) != value:
            image[key] = value
            changed = True
    cloudinary = image.get("cloudinary")
    if isinstance(cloudinary, dict):
        if cloudinary.get("rawUrl") != f"/images/{raw_name}":
            cloudinary["rawUrl"] = f"/images/{raw_name}"
            changed = True
        if cloudinary.get("brandedUrl") != (display_url if wants_frame else None):
            cloudinary["brandedUrl"] = display_url if wants_frame else None
            changed = True
    return changed


def main() -> int:
    store = SupabaseStore()
    if not store.enabled:
        raise SystemExit("SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY y SUPABASE_STATE_BACKEND=1 son obligatorios.")
    stored = store.read_state()
    state = json.loads(json.dumps(stored.state))
    changed = 0
    for post in state.get("posts", []):
        for image in [post.get("image"), *(post.get("imageVariants") or [])]:
            if isinstance(image, dict) and routed_image(store, image):
                changed += 1
    for blog in state.get("blogs", []):
        for figure in blog.get("figures", []):
            image = figure.get("image") if isinstance(figure, dict) else None
            if isinstance(image, dict) and routed_image(store, image):
                changed += 1
    if changed:
        version = store.replace_state(state, stored.version)
    else:
        version = stored.version
    print(json.dumps({"ok": True, "changed": changed, "version": version}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
