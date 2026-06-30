from __future__ import annotations

import cgi
import json
import mimetypes
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import unicodedata
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.ai.services.pipeline_service import EditorialPipeline
from src.ai.services.blog_pipeline import BlogPipeline
from src.ai.services.image_prompt_service import ImagePromptService
from src.ai.services.image_service import ImageService
from src.ai.services.cloudinary_service import CloudinaryService
from src.ai.services.frame_composer import compose_branded_frame
from src.ai.services.openai_client import OpenAIClient
from src.ai.services import prompt_service
from src.domain.editorial import AUDIENCES, CHANNELS, CTA_TYPES, OBJECTIVES, POST_TYPES, RISK_FLAGS
from src.domain.blog import (
    BLOG_AUDIENCES,
    BLOG_CTA_TYPES,
    BLOG_LENGTH_TARGETS,
    BLOG_REVIEW_FLAGS,
    BLOG_STATUSES,
    FRAMEWORKS as BLOG_FRAMEWORKS,
    FUNNEL_STAGES,
    LEAD_MAGNET_TYPES,
    SEARCH_INTENTS,
)


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "db.json"
UPLOAD_DIR = DATA_DIR / "uploads"
IMAGES_DIR = DATA_DIR / "images"
OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.4-mini"
PORT = 8787
DB_LOCK = threading.Lock()


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


load_env()
PORT = int(os.getenv("PORT", str(PORT)))


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "NexiaGPSocialAI/0.1"

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api()
            return
        if self.path.startswith("/images/"):
            self.serve_image_file()
            return
        self.serve_public_file()

    def do_POST(self) -> None:
        self.handle_api()

    def do_PATCH(self) -> None:
        self.handle_api()

    def do_PUT(self) -> None:
        self.handle_api()

    def do_DELETE(self) -> None:
        self.handle_api()

    def log_message(self, fmt: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def serve_public_file(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        rel = urllib.parse.unquote(parsed.path).lstrip("/") or "index.html"
        target = (PUBLIC_DIR / rel).resolve()
        if not str(target).startswith(str(PUBLIC_DIR.resolve())) or not target.is_file():
            self.send_json({"ok": False, "error": "Archivo no encontrado"}, status=404)
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix in {".html", ".css", ".js", ".json"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(target.stat().st_size))
        self.end_headers()
        with target.open("rb") as fh:
            shutil.copyfileobj(fh, self.wfile)

    def handle_api(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if self.command == "GET" and path == "/api/health":
                db = read_db()
                self.send_json(
                    {
                        "ok": True,
                        "hasOpenAIKey": bool(os.getenv("OPENAI_API_KEY")),
                        "hasSocialWebhook": bool(os.getenv("SOCIAL_WEBHOOK_URL")),
                        "model": db["settings"].get("model") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL,
                        "vectorStoreId": db["settings"].get("vectorStoreId", ""),
                    }
                )
                return

            if self.command == "GET" and path == "/api/state":
                self.send_json(decorate_state(read_db()))
                return

            if self.command == "GET" and path == "/api/editorial/options":
                self.send_json(editorial_options())
                return

            if self.command == "PATCH" and path == "/api/settings":
                body = self.read_json()
                db = read_db()
                allowed = {
                    "model",
                    "vectorStoreId",
                    "vectorStoreName",
                    "cadenceDays",
                    "defaultPostTypeId",
                    "publishMode",
                    "schedulerEnabled",
                }
                for key in allowed:
                    if key in body:
                        db["settings"][key] = body[key]
                if isinstance(body.get("blog"), dict):
                    blog_settings = db["settings"].setdefault("blog", {})
                    for k, v in body["blog"].items():
                        if k in BLOG_SETTINGS_KEYS:
                            blog_settings[k] = v
                    normalize_blog_settings(blog_settings)
                db["settings"]["cadenceDays"] = clamp(int(db["settings"].get("cadenceDays") or 3), 1, 30)
                if db["settings"].get("publishMode") not in {"draft", "ready", "auto"}:
                    db["settings"]["publishMode"] = "draft"
                write_db(db)
                self.send_json(decorate_state(db))
                return

            if self.command == "GET" and path == "/api/prompts":
                self.send_json({"ok": True, "prompts": prompt_service.list_prompts_meta()})
                return

            # /revert must be checked BEFORE the generic prompt match because the
            # generic regex (.+) is greedy and would otherwise swallow "/revert".
            revert_match = re.match(r"^/api/prompts/(.+)/revert$", path)
            if revert_match and self.command == "POST":
                prompt_id = urllib.parse.unquote(revert_match.group(1))
                if not prompt_service.is_registered(prompt_id):
                    raise ApiError("Prompt no encontrado", 404)
                body = self.read_json()
                detail = revert_prompt_to_version(prompt_id, int(body.get("version") or 0))
                self.send_json({"ok": True, "prompt": detail, "state": decorate_state(read_db())})
                return

            prompt_match = re.match(r"^/api/prompts/(.+)$", path)
            if prompt_match:
                prompt_id = urllib.parse.unquote(prompt_match.group(1))
                if not prompt_service.is_registered(prompt_id):
                    raise ApiError("Prompt no encontrado", 404)
                if self.command == "GET":
                    self.send_json({"ok": True, "prompt": prompt_service.get_prompt_detail(prompt_id)})
                    return
                if self.command == "PUT":
                    body = self.read_json()
                    detail = save_prompt_override(prompt_id, body.get("text", ""), body.get("note", ""))
                    self.send_json({"ok": True, "prompt": detail, "state": decorate_state(read_db())})
                    return

            if self.command == "POST" and path == "/api/themes":
                body = self.read_json()
                db = read_db()
                db["themes"].insert(0, normalize_theme(body))
                write_db(db)
                self.send_json(decorate_state(db), status=201)
                return

            theme_match = re.match(r"^/api/themes/([^/]+)$", path)
            if theme_match and self.command == "PUT":
                body = self.read_json()
                db = read_db()
                idx = find_index(db["themes"], theme_match.group(1))
                if idx < 0:
                    raise ApiError("Tematica no encontrada", 404)
                db["themes"][idx] = normalize_theme(body, db["themes"][idx])
                write_db(db)
                self.send_json(decorate_state(db))
                return

            if theme_match and self.command == "DELETE":
                db = read_db()
                db["themes"] = [theme for theme in db["themes"] if theme["id"] != theme_match.group(1)]
                write_db(db)
                self.send_json(decorate_state(db))
                return

            if self.command == "POST" and path == "/api/post-types":
                body = self.read_json()
                db = read_db()
                db["postTypes"].insert(0, normalize_post_type(body))
                write_db(db)
                self.send_json(decorate_state(db), status=201)
                return

            type_match = re.match(r"^/api/post-types/([^/]+)$", path)
            if type_match and self.command == "PUT":
                body = self.read_json()
                db = read_db()
                idx = find_index(db["postTypes"], type_match.group(1))
                if idx < 0:
                    raise ApiError("Tipo de post no encontrado", 404)
                db["postTypes"][idx] = normalize_post_type(body, db["postTypes"][idx])
                write_db(db)
                self.send_json(decorate_state(db))
                return

            if type_match and self.command == "DELETE":
                db = read_db()
                db["postTypes"] = [item for item in db["postTypes"] if item["id"] != type_match.group(1)]
                write_db(db)
                self.send_json(decorate_state(db))
                return

            if self.command == "POST" and path == "/api/generate":
                body = self.read_json()
                result = generate_posts(
                    theme_id=body.get("themeId"),
                    post_type_id=body.get("postTypeId"),
                    count=clamp(int(body.get("count") or 1), 1, 5),
                    desired_status=body.get("status"),
                    source="manual",
                )
                self.send_json(result, status=201)
                return

            if self.command == "POST" and path == "/api/editorial/generate":
                body = self.read_json()
                result = run_editorial_pipeline(body)
                self.send_json(result, status=201)
                return

            regen_match = re.match(r"^/api/editorial/posts/([^/]+)/regenerate$", path)
            if regen_match and self.command == "POST":
                body = self.read_json()
                result = regenerate_editorial_post(regen_match.group(1), body)
                self.send_json(result, status=201)
                return

            adapt_match = re.match(r"^/api/editorial/posts/([^/]+)/adapt$", path)
            if adapt_match and self.command == "POST":
                result = adapt_editorial_post(adapt_match.group(1))
                self.send_json(result, status=200)
                return

            img_gen_match = re.match(r"^/api/posts/([^/]+)/generate-image$", path)
            if img_gen_match and self.command == "POST":
                body = self.read_json()
                result = generate_post_image(img_gen_match.group(1), body)
                self.send_json(result, status=200)
                return

            if self.command == "GET" and path == "/api/blogs/options":
                self.send_json(blog_options())
                return

            if self.command == "POST" and path == "/api/blogs/generate":
                body = self.read_json()
                result = run_blog_pipeline(body)
                self.send_json(result, status=201)
                return

            blog_match = re.match(r"^/api/blogs/([^/]+)$", path)
            if blog_match and self.command == "PATCH":
                body = self.read_json()
                result = patch_blog(blog_match.group(1), body)
                self.send_json(result)
                return

            if blog_match and self.command == "DELETE":
                result = delete_blog(blog_match.group(1))
                self.send_json(result)
                return

            figure_img_match = re.match(r"^/api/blogs/([^/]+)/figures/([^/]+)/generate-image$", path)
            if figure_img_match and self.command == "POST":
                body = self.read_json()
                result = generate_blog_figure_image(figure_img_match.group(1), figure_img_match.group(2), body)
                self.send_json(result, status=200)
                return

            if self.command == "POST" and path == "/api/scheduler/run":
                self.send_json(run_scheduler(force=True, source="manual"))
                return

            if self.command == "POST" and path == "/api/files/upload":
                self.send_json(self.handle_upload(), status=201)
                return

            if self.command == "POST" and path == "/api/files/import-local":
                self.send_json(import_local_documents(), status=201)
                return

            if self.command == "POST" and path == "/api/files/sync-openai":
                self.send_json(sync_files_to_openai(), status=200)
                return

            file_match = re.match(r"^/api/files/([^/]+)$", path)
            if file_match and self.command == "DELETE":
                db = read_db()
                file_item = next((item for item in db["files"] if item["id"] == file_match.group(1)), None)
                if not file_item:
                    raise ApiError("Archivo no encontrado", 404)
                delete_remote_file_if_possible(file_item)
                db["files"] = [item for item in db["files"] if item["id"] != file_item["id"]]
                write_db(db)
                self.send_json(decorate_state(db))
                return

            post_match = re.match(r"^/api/posts/([^/]+)$", path)
            if post_match and self.command == "PATCH":
                body = self.read_json()
                db = read_db()
                post = next((item for item in db["posts"] if item["id"] == post_match.group(1)), None)
                if not post:
                    raise ApiError("Post no encontrado", 404)
                post["status"] = normalize_status(body.get("status") or post.get("status"))
                post["updatedAt"] = now_iso()
                write_db(db)
                self.send_json(decorate_state(db))
                return

            if post_match and self.command == "DELETE":
                db = read_db()
                db["posts"] = [item for item in db["posts"] if item["id"] != post_match.group(1)]
                write_db(db)
                self.send_json(decorate_state(db))
                return

            publish_match = re.match(r"^/api/posts/([^/]+)/publish$", path)
            if publish_match and self.command == "POST":
                db = read_db()
                post = next((item for item in db["posts"] if item["id"] == publish_match.group(1)), None)
                if not post:
                    raise ApiError("Post no encontrado", 404)
                publish_post(db, post)
                write_db(db)
                self.send_json(decorate_state(db))
                return

            raise ApiError("Ruta no encontrada", 404)
        except ApiError as exc:
            self.send_json({"ok": False, "error": exc.message, "code": exc.code}, status=exc.status)
        except Exception as exc:
            print("API error:", exc)
            self.send_json({"ok": False, "error": str(exc), "code": "server_error"}, status=500)

    def handle_upload(self) -> dict:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("content-type", ""),
                "CONTENT_LENGTH": self.headers.get("content-length", "0"),
            },
        )
        file_item = form["file"] if "file" in form else None
        if file_item is None or not getattr(file_item, "filename", ""):
            raise ApiError("No se recibio ningun archivo", 400)
        category = form.getfirst("category", "general")
        buffer = file_item.file.read()
        db = read_db()
        registered = register_file(
            db,
            file_name=sanitize_filename(file_item.filename),
            mime_type=file_item.type or "application/octet-stream",
            buffer=buffer,
            category=category,
            source="upload",
        )
        write_db(db)
        return {"ok": True, "file": registered, "state": decorate_state(db)}

    def serve_image_file(self) -> None:
        filename = urllib.parse.unquote(self.path[len("/images/"):].split("?")[0])
        target = (IMAGES_DIR / filename).resolve()
        if not str(target).startswith(str(IMAGES_DIR.resolve())) or not target.is_file():
            self.send_json({"ok": False, "error": "Imagen no encontrada"}, status=404)
            return
        ext = target.suffix.lower()
        content_type = {"jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(target.stat().st_size))
        self.send_header("cache-control", "public, max-age=31536000, immutable")
        self.end_headers()
        with target.open("rb") as fh:
            shutil.copyfileobj(fh, self.wfile)

    def read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "http_error") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def generate_posts(theme_id: str, post_type_id: str, count: int, desired_status: str | None, source: str) -> dict:
    db = read_db()
    theme = next((item for item in db["themes"] if item["id"] == theme_id), None)
    post_type = next((item for item in db["postTypes"] if item["id"] == post_type_id), None)
    if not theme:
        raise ApiError("Tematica no encontrada", 404)
    if not post_type:
        raise ApiError("Tipo de post no encontrado", 404)

    status = normalize_status(desired_status) if desired_status else status_from_mode(
        db["settings"].get("publishMode"), post_type.get("defaultStatus", "draft")
    )
    model = db["settings"].get("model") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    used_ideas = collect_used_ideas(db, theme["id"])

    if os.getenv("OPENAI_API_KEY"):
        generated = generate_with_openai(db, theme, post_type, count, used_ideas, model)
        provider = "openai"
    else:
        generated = {"posts": create_demo_posts(theme, post_type, count, used_ideas), "responseId": None}
        provider = "demo"

    created_at = now_iso()
    new_posts = []
    for item in generated["posts"]:
        post_status = "ready" if item.get("statusRecommendation") == "ready" else status
        post = {
            "id": uid("post"),
            "themeId": theme["id"],
            "themeTitle": theme["title"],
            "postTypeId": post_type["id"],
            "postTypeLabel": post_type["label"],
            "platform": item.get("platform") or post_type.get("platform"),
            "title": item.get("title") or item.get("idea"),
            "idea": item.get("idea", ""),
            "angle": item.get("angle", ""),
            "copy": item.get("copy", ""),
            "hashtags": item.get("hashtags") if isinstance(item.get("hashtags"), list) else [],
            "cta": item.get("cta", ""),
            "rationale": item.get("rationale", ""),
            "sourceNotes": item.get("sourceNotes", ""),
            "status": normalize_status(post_status),
            "provider": provider,
            "responseId": generated.get("responseId"),
            "createdAt": created_at,
            "updatedAt": created_at,
            "publishedAt": None,
            "publishResult": None,
            "source": source,
        }
        new_posts.append(post)

    db["posts"] = new_posts + db["posts"]
    theme_ref = next(item for item in db["themes"] if item["id"] == theme["id"])
    theme_ref["usedIdeas"] = [
        {
            "id": uid("idea"),
            "postId": post["id"],
            "idea": post["idea"],
            "angle": post["angle"],
            "createdAt": created_at,
        }
        for post in new_posts
    ] + theme_ref.get("usedIdeas", [])
    theme_ref["usedIdeas"] = theme_ref["usedIdeas"][:200]

    if db["settings"].get("publishMode") == "auto" or desired_status == "auto":
        for post in new_posts:
            publish_post(db, post)

    write_db(db)
    return {"ok": True, "posts": new_posts, "provider": provider, "state": decorate_state(db)}


def run_editorial_pipeline(request: dict) -> dict:
    db = read_db()
    pipeline = EditorialPipeline(model=db.get("settings", {}).get("model"))
    result = pipeline.run(request, db)
    post = result["post"]
    db.setdefault("posts", []).insert(0, post)
    register_editorial_idea(db, post)
    write_db(db)
    result["state"] = decorate_state(db)
    return result


def regenerate_editorial_post(post_id: str, body: dict) -> dict:
    db = read_db()
    original = next((item for item in db.get("posts", []) if item.get("id") == post_id), None)
    if not original:
        raise ApiError("Post no encontrado", 404)
    request = dict(original.get("request") or {})
    instruction = body.get("instruction") or "Regenera la pieza completa manteniendo la estrategia y mejorando utilidad."
    request["regeneration_instruction"] = instruction
    if body.get("variant"):
        request["regeneration_instruction"] = f"{instruction}. Variante solicitada: {body['variant']}"
    pipeline = EditorialPipeline(model=db.get("settings", {}).get("model"))
    result = pipeline.run(request, db)
    result["post"]["parentPostId"] = post_id
    db.setdefault("posts", []).insert(0, result["post"])
    register_editorial_idea(db, result["post"])
    write_db(db)
    result["state"] = decorate_state(db)
    return result


def adapt_editorial_post(post_id: str) -> dict:
    db = read_db()
    post = next((item for item in db.get("posts", []) if item.get("id") == post_id), None)
    if not post:
        raise ApiError("Post no encontrado", 404)
    pipeline = EditorialPipeline(model=db.get("settings", {}).get("model"))
    adaptations = pipeline.adapt_existing(post, db)
    write_db(db)
    return {"ok": True, "adaptations": adaptations, "state": decorate_state(db)}


def generate_post_image(post_id: str, config: dict) -> dict:
    db = read_db()
    post = next((item for item in db.get("posts", []) if item.get("id") == post_id), None)
    if not post:
        raise ApiError("Post no encontrado", 404)
    if not os.getenv("OPENAI_API_KEY"):
        raise ApiError("Falta OPENAI_API_KEY", 400)

    style = config.get("style") or "Fotografía documental editorial"
    user_notes = config.get("userNotes") or ""
    size = config.get("size") or "1344x768"
    quality = config.get("quality") or "medium"
    with_frame = bool(config.get("withFrame", True))

    client = OpenAIClient(model=db.get("settings", {}).get("model"))
    image_prompt, prompt_response_id = ImagePromptService(client).generate_prompt(post, style, user_notes)
    filename, size_bytes = ImageService().generate(image_prompt, size=size, quality=quality)
    local_path = IMAGES_DIR / filename

    # If with_frame: compose framed version (blurred strip + chocolate line)
    # Else: skip composition and upload the raw image
    if with_frame:
        upload_path = IMAGES_DIR / f"{Path(filename).stem}_framed.png"
        compose_branded_frame(local_path, upload_path)
        public_id_suffix = "_framed"
    else:
        upload_path = local_path
        public_id_suffix = ""

    cloudinary_data: dict | None = None
    cloudinary = CloudinaryService()
    if cloudinary.enabled:
        try:
            public_id = f"nexiagp/posts/{Path(filename).stem}{public_id_suffix}"
            upload_result = cloudinary.upload_image(upload_path, public_id=public_id)
            version = upload_result.get("version")
            cloudinary_data = {
                "publicId": upload_result.get("public_id"),
                "version": version,
                "rawUrl": upload_result.get("secure_url"),
                "brandedUrl": cloudinary.build_branded_url(upload_result["public_id"], version=version),
                "withFrame": with_frame,
            }
        except Exception as exc:
            print("Cloudinary upload error:", exc)

    now = now_iso()
    post["image"] = {
        "url": f"/images/{filename}",
        "brandedUrl": cloudinary_data["brandedUrl"] if cloudinary_data else None,
        "cloudinary": cloudinary_data,
        "prompt": image_prompt,
        "config": {"style": style, "size": size, "quality": quality, "userNotes": user_notes, "withFrame": with_frame},
        "generatedAt": now,
        "promptResponseId": prompt_response_id,
        "sizeBytes": size_bytes,
    }
    post["imageLocalPath"] = str(local_path)
    post["updatedAt"] = now
    write_db(db)
    return {"ok": True, "image": post["image"], "state": decorate_state(db)}


def run_blog_pipeline(request: dict) -> dict:
    db = read_db()
    blog_settings = normalize_blog_settings(dict(db.get("settings", {}).get("blog") or {}))
    # Merge configurable defaults from settings.blog if the request did not override them.
    enriched_request = dict(request or {})
    enriched_request.setdefault("length", blog_settings.get("defaultLength"))
    enriched_request.setdefault("framework_hint", blog_settings.get("defaultFramework"))
    enriched_request.setdefault("audience", blog_settings.get("defaultAudience"))
    enriched_request["images_per_article"] = int(
        enriched_request.get("images_per_article")
        if enriched_request.get("images_per_article") not in (None, "")
        else blog_settings.get("imagesPerArticle", 2)
    )
    pipeline = BlogPipeline(model=blog_settings.get("defaultModel") or db.get("settings", {}).get("model"))
    result = pipeline.run(enriched_request, db)
    blog = result["blog"]
    db.setdefault("blogs", []).insert(0, blog)
    write_db(db)
    result["state"] = decorate_state(db)
    return result


def patch_blog(blog_id: str, body: dict) -> dict:
    db = read_db()
    blog = next((item for item in db.get("blogs", []) if item.get("id") == blog_id), None)
    if not blog:
        raise ApiError("Blog no encontrado", 404)
    allowed_fields = {"status", "metaTitle", "metaDescription", "slug", "title", "articleHtmlOverride"}
    for key in allowed_fields:
        if key in body:
            if key == "status" and body[key] not in BLOG_STATUSES:
                continue
            if key == "articleHtmlOverride":
                blog.setdefault("article", {})["article_html_override"] = body[key]
            else:
                blog[key] = body[key]
    blog["updatedAt"] = now_iso()
    write_db(db)
    return {"ok": True, "blog": blog, "state": decorate_state(db)}


def delete_blog(blog_id: str) -> dict:
    db = read_db()
    before = len(db.get("blogs", []))
    db["blogs"] = [item for item in db.get("blogs", []) if item.get("id") != blog_id]
    if len(db["blogs"]) == before:
        raise ApiError("Blog no encontrado", 404)
    write_db(db)
    return {"ok": True, "state": decorate_state(db)}


def generate_blog_figure_image(blog_id: str, figure_id: str, config: dict) -> dict:
    db = read_db()
    blog = next((item for item in db.get("blogs", []) if item.get("id") == blog_id), None)
    if not blog:
        raise ApiError("Blog no encontrado", 404)
    figure = next((f for f in blog.get("figures", []) if f.get("figure_id") == figure_id), None)
    if not figure:
        raise ApiError("Figura no encontrada", 404)
    if not os.getenv("OPENAI_API_KEY"):
        raise ApiError("Falta OPENAI_API_KEY", 400)

    blog_settings = normalize_blog_settings(dict(db.get("settings", {}).get("blog") or {}))
    # Map settings.blog.imageQuality (low|standard|high) to the image-service quality values.
    quality_map = {"low": "low", "standard": "medium", "high": "high"}
    default_quality = quality_map.get(blog_settings.get("imageQuality", "standard"), "medium")

    style = config.get("style") or "Ilustracion editorial sobria, concorde al articulo"
    user_notes = config.get("userNotes") or ""
    size = config.get("size") or "1344x768"
    quality = config.get("quality") or default_quality
    # Blog images are "sin edicion": no branded frame unless the caller explicitly opts in.
    with_frame = bool(config.get("withFrame", False))

    # Combine the figure's image_prompt with any user notes; bypass the AI prompt
    # generator since the brief already has a precise image_brief.
    combined_prompt = figure.get("image_prompt", "")
    if user_notes:
        combined_prompt += f"\n\nUser notes: {user_notes}"

    filename, size_bytes = ImageService().generate(combined_prompt, size=size, quality=quality)
    local_path = IMAGES_DIR / filename

    if with_frame:
        upload_path = IMAGES_DIR / f"{Path(filename).stem}_framed.png"
        compose_branded_frame(local_path, upload_path)
        public_id_suffix = "_framed"
    else:
        upload_path = local_path
        public_id_suffix = ""

    cloudinary_data: dict | None = None
    cloudinary = CloudinaryService()
    if cloudinary.enabled:
        try:
            public_id = f"nexiagp/blogs/{Path(filename).stem}{public_id_suffix}"
            upload_result = cloudinary.upload_image(upload_path, public_id=public_id)
            version = upload_result.get("version")
            cloudinary_data = {
                "publicId": upload_result.get("public_id"),
                "version": version,
                "rawUrl": upload_result.get("secure_url"),
                "brandedUrl": cloudinary.build_branded_url(upload_result["public_id"], version=version),
                "withFrame": with_frame,
            }
        except Exception as exc:
            print("Cloudinary upload error (blog figure):", exc)

    now = now_iso()
    # Display URL respects withFrame: with marco -> brandedUrl (Cloudinary overlay), sin marco -> rawUrl.
    # Falls back to the local /images/<filename> path if Cloudinary is disabled.
    if cloudinary_data:
        display_url = (cloudinary_data.get("brandedUrl") if with_frame else cloudinary_data.get("rawUrl")) or f"/images/{filename}"
    else:
        display_url = f"/images/{filename}"
    figure["image"] = {
        "url": f"/images/{filename}",
        "displayUrl": display_url,
        "brandedUrl": (cloudinary_data or {}).get("brandedUrl"),
        "cloudinary": cloudinary_data,
        "prompt": combined_prompt,
        "config": {"style": style, "size": size, "quality": quality, "userNotes": user_notes, "withFrame": with_frame},
        "generatedAt": now,
        "sizeBytes": size_bytes,
    }
    blog["updatedAt"] = now
    write_db(db)
    return {"ok": True, "figure": figure, "blog": blog, "state": decorate_state(db)}


def blog_options() -> dict:
    return {
        "ok": True,
        "options": {
            "searchIntents": SEARCH_INTENTS,
            "frameworks": BLOG_FRAMEWORKS,
            "audiences": BLOG_AUDIENCES,
            "ctaTypes": BLOG_CTA_TYPES,
            "lengths": BLOG_LENGTH_TARGETS,
            "funnelStages": FUNNEL_STAGES,
            "leadMagnets": LEAD_MAGNET_TYPES,
            "statuses": BLOG_STATUSES,
            "reviewFlags": BLOG_REVIEW_FLAGS,
        },
    }


def register_editorial_idea(db: dict, post: dict) -> None:
    post_type = post.get("postTypeId") or post.get("themeId")
    theme = next((item for item in db.get("themes", []) if item.get("id") == post_type), None)
    if not theme:
        return
    theme.setdefault("usedIdeas", []).insert(
        0,
        {
            "id": uid("idea"),
            "postId": post.get("id"),
            "idea": post.get("idea") or post.get("title"),
            "angle": post.get("angle"),
            "createdAt": now_iso(),
        },
    )
    theme["usedIdeas"] = theme["usedIdeas"][:200]


def generate_with_openai(db: dict, theme: dict, post_type: dict, count: int, used_ideas: list[str], model: str) -> dict:
    vector_store_id = db["settings"].get("vectorStoreId", "")
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": build_system_prompt(post_type)},
            {
                "role": "user",
                "content": build_generation_prompt(db, theme, post_type, count, used_ideas, bool(vector_store_id)),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "nexiagp_social_posts",
                "strict": True,
                "schema": post_schema(),
            }
        },
    }
    if vector_store_id:
        payload["tools"] = [
            {"type": "file_search", "vector_store_ids": [vector_store_id], "max_num_results": 8}
        ]

    response = openai_request("/responses", method="POST", payload=payload)
    output_text = extract_output_text(response)
    parsed = json.loads(output_text)
    return {"posts": parsed.get("posts", []), "responseId": response.get("id")}


def build_system_prompt(post_type: dict) -> str:
    return "\n".join(
        [
            "Eres el estratega de contenidos B2B de Nexia Growth Partner.",
            "Trabajas exclusivamente con informacion disponible en los archivos recuperados y en las instrucciones de marca.",
            "No inventes datos, precios, clientes, plazos, marcas ni certificaciones.",
            "Nexia GP no atiende a particulares: todo el contenido debe quedar orientado a fabricantes, distribuidores y clientes empresariales.",
            "Escribe en espanol de Espana, con tono profesional, claro, cercano y comercialmente sobrio.",
            "Devuelve solo JSON valido segun el schema.",
            "",
            f"Instrucciones especificas del tipo de post: {post_type.get('instructions', '')}",
        ]
    )


def build_generation_prompt(db: dict, theme: dict, post_type: dict, count: int, used_ideas: list[str], has_vector: bool) -> str:
    recent_posts = [
        f"- {post.get('idea')} | {post.get('angle')}"
        for post in db["posts"]
        if post.get("themeId") == theme["id"]
    ][:12]
    return "\n".join(
        [
            f"Genera {count} post(s) para {post_type.get('platform')}.",
            "",
            "Cliente:",
            f"- Nombre: {db['client'].get('name')}",
            f"- Posicionamiento: {db['client'].get('positioning')}",
            f"- Mercados: {', '.join(db['client'].get('markets', []))}",
            f"- Valores: {', '.join(db['client'].get('values', []))}",
            "",
            "Tematica seleccionada:",
            f"- Titulo: {theme.get('title')}",
            f"- Audiencia: {theme.get('audience')}",
            f"- Descripcion: {theme.get('description')}",
            f"- Pilares: {', '.join(theme.get('pillars', []))}",
            "",
            "Ideas ya utilizadas que debes evitar:",
            "\n".join(f"- {idea}" for idea in used_ideas) if used_ideas else "- No hay ideas registradas aun.",
            "",
            "Posts recientes de esta tematica:",
            "\n".join(recent_posts) if recent_posts else "- Sin posts recientes.",
            "",
            "Consulta los archivos con file_search antes de proponer el contenido. Usa sourceNotes para resumir internamente el soporte documental usado."
            if has_vector
            else "No hay Vector Store configurada todavia; trabaja solo con las instrucciones y marca sourceNotes como pendiente de documentacion.",
            "",
            "Cada post debe tener una idea nueva, diferenciada y registrable.",
        ]
    )


def post_schema() -> dict:
    props = {
        "idea": {"type": "string"},
        "angle": {"type": "string"},
        "platform": {"type": "string"},
        "title": {"type": "string"},
        "copy": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "cta": {"type": "string"},
        "rationale": {"type": "string"},
        "statusRecommendation": {"type": "string", "enum": ["draft", "ready"]},
        "sourceNotes": {"type": "string"},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "posts": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": props,
                    "required": list(props.keys()),
                },
            }
        },
        "required": ["posts"],
    }


def create_demo_posts(theme: dict, post_type: dict, count: int, used_ideas: list[str]) -> list[dict]:
    concepts = [
        "adaptar la estrategia comercial a cada isla",
        "convertir la red local en una ventaja competitiva",
        "coordinar fabricantes y distribuidores con seguimiento real",
        "combinar soporte tecnico, formacion y cercania comercial",
        "mejorar la reposicion en un mercado insular",
    ]
    posts = []
    for index in range(count):
        concept = concepts[(len(used_ideas) + index) % len(concepts)]
        posts.append(
            {
                "idea": f"{theme.get('title')}: {concept}",
                "angle": f"Insight B2B sobre {concept}",
                "platform": post_type.get("platform", "LinkedIn"),
                "title": theme.get("title"),
                "copy": "\n".join(
                    [
                        "En Canarias, crecer no va solo de llegar: va de entender cada isla, cada canal y cada decision de compra profesional.",
                        "",
                        f"Para {theme.get('audience', 'la audiencia B2B').lower()}, {concept} puede marcar la diferencia entre una entrada puntual y una presencia comercial sostenible.",
                        "",
                        "En Nexia GP trabajamos como socio B2B: conectamos fabricantes, distribuidores y clientes empresariales con conocimiento local, seguimiento comercial y una red consolidada en el archipielago.",
                        "",
                        "La oportunidad esta en construir relaciones que duren, no en hacer ruido.",
                    ]
                ),
                "hashtags": ["#NexiaGP", "#Canarias", "#B2B", "#Distribucion", "#CrecimientoComercial"],
                "cta": "Hablemos de como posicionar tu marca en Canarias.",
                "rationale": "Borrador demo basado en los pilares de marca configurados localmente.",
                "statusRecommendation": "draft",
                "sourceNotes": "Modo demo: falta OPENAI_API_KEY o no se ha conectado la Vector Store.",
            }
        )
    return posts


def import_local_documents() -> dict:
    docs = list_local_documents()
    if not docs:
        raise ApiError("No se encontraron documentos locales para importar", 404)
    db = read_db()
    imported = []
    skipped = []
    for doc in docs:
        if any(item.get("localSourcePath") == str(doc["path"]) or item.get("name") == doc["name"] for item in db["files"]):
            skipped.append(doc["name"])
            continue
        imported.append(
            register_file(
                db,
                file_name=doc["name"],
                mime_type=mime_from_filename(doc["name"]),
                buffer=Path(doc["path"]).read_bytes(),
                category=doc["category"],
                source="local_import",
                local_source_path=str(doc["path"]),
            )
        )
    write_db(db)
    return {"ok": True, "imported": imported, "skipped": skipped, "state": decorate_state(db)}


def sync_files_to_openai() -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        raise ApiError("Falta OPENAI_API_KEY", 400)
    db = read_db()
    synced = []
    errors = []
    for item in db.get("files", []):
        if item.get("openaiFileId"):
            if item.get("vectorStoreId") and item.get("vectorStoreFileId") and item.get("status") not in {"completed", "failed", "cancelled"}:
                try:
                    completed = poll_vector_store_file(item["vectorStoreId"], item["vectorStoreFileId"])
                    item["status"] = completed.get("status") or item.get("status") or "in_progress"
                    item["error"] = completed.get("last_error", {}).get("message") if completed.get("last_error") else None
                    item["updatedAt"] = now_iso()
                    synced.append(item)
                except Exception as exc:
                    item["error"] = str(exc)
                    item["updatedAt"] = now_iso()
                    errors.append({"id": item.get("id"), "name": item.get("name"), "error": str(exc)})
            continue
        local_path = item.get("localPath")
        if not local_path or not Path(local_path).exists():
            errors.append({"id": item.get("id"), "name": item.get("name"), "error": "Archivo local no encontrado"})
            continue
        try:
            buffer = Path(local_path).read_bytes()
            vector_store_id = ensure_vector_store(db)
            upload = upload_openai_file(buffer, item["name"], item.get("mimeType") or "application/octet-stream")
            vector_file = attach_file_to_vector_store(
                vector_store_id,
                upload["id"],
                item.get("category") or "general",
                item["name"],
            )
            completed = poll_vector_store_file(vector_store_id, vector_file.get("id") or upload["id"])
            item["status"] = completed.get("status") or vector_file.get("status") or "in_progress"
            item["openaiFileId"] = upload["id"]
            item["vectorStoreId"] = vector_store_id
            item["vectorStoreFileId"] = vector_file.get("id") or upload["id"]
            item["error"] = completed.get("last_error", {}).get("message") if completed.get("last_error") else None
            item["updatedAt"] = now_iso()
            synced.append(item)
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            item["updatedAt"] = now_iso()
            errors.append({"id": item.get("id"), "name": item.get("name"), "error": str(exc)})
    write_db(db)
    return {"ok": True, "synced": synced, "errors": errors, "state": decorate_state(db)}


def register_file(
    db: dict,
    file_name: str,
    mime_type: str,
    buffer: bytes,
    category: str,
    source: str,
    local_source_path: str | None = None,
    sync_remote: bool = False,
) -> dict:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uid("file")
    safe_name = sanitize_filename(file_name)
    stored_path = UPLOAD_DIR / f"{file_id}-{safe_name}"
    stored_path.write_bytes(buffer)
    now = now_iso()
    item = {
        "id": file_id,
        "name": safe_name,
        "category": category,
        "source": source,
        "localPath": str(stored_path),
        "localSourcePath": local_source_path,
        "mimeType": mime_type,
        "size": len(buffer),
        "status": "local_only",
        "openaiFileId": None,
        "vectorStoreId": db["settings"].get("vectorStoreId", ""),
        "vectorStoreFileId": None,
        "error": None,
        "createdAt": now,
        "updatedAt": now,
    }

    if sync_remote and os.getenv("OPENAI_API_KEY"):
        try:
            vector_store_id = ensure_vector_store(db)
            upload = upload_openai_file(buffer, safe_name, mime_type)
            vector_file = attach_file_to_vector_store(vector_store_id, upload["id"], category, safe_name)
            completed = poll_vector_store_file(vector_store_id, vector_file.get("id") or upload["id"])
            item["status"] = completed.get("status") or vector_file.get("status") or "in_progress"
            item["openaiFileId"] = upload["id"]
            item["vectorStoreId"] = vector_store_id
            item["vectorStoreFileId"] = vector_file.get("id") or upload["id"]
            if completed.get("last_error"):
                item["error"] = completed["last_error"].get("message")
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)

    db["files"].insert(0, item)
    return item


def ensure_vector_store(db: dict) -> str:
    if db["settings"].get("vectorStoreId"):
        return db["settings"]["vectorStoreId"]
    store = openai_request(
        "/vector_stores",
        method="POST",
        payload={
            "name": db["settings"].get("vectorStoreName") or "Nexia GP Knowledge Base",
            "metadata": {"client": "nexiagp", "app": "social-ai"},
        },
    )
    db["settings"]["vectorStoreId"] = store["id"]
    return store["id"]


def upload_openai_file(buffer: bytes, filename: str, mime_type: str) -> dict:
    body, content_type = encode_multipart(
        fields={"purpose": "assistants"},
        files={"file": (filename, mime_type or "application/octet-stream", buffer)},
    )
    return openai_request("/files", method="POST", data=body, content_type=content_type)


def attach_file_to_vector_store(vector_store_id: str, file_id: str, category: str, filename: str) -> dict:
    return openai_request(
        f"/vector_stores/{urllib.parse.quote(vector_store_id)}/files",
        method="POST",
        payload={
            "file_id": file_id,
            "attributes": {"category": category, "source": "nexiagp-social-ai", "filename": filename},
        },
    )


def poll_vector_store_file(vector_store_id: str, vector_file_id: str) -> dict:
    for _ in range(20):
        item = openai_request(
            f"/vector_stores/{urllib.parse.quote(vector_store_id)}/files/{urllib.parse.quote(vector_file_id)}"
        )
        if item.get("status") in {"completed", "failed", "cancelled"}:
            return item
        time.sleep(1)
    return {"status": "in_progress", "last_error": None}


def delete_remote_file_if_possible(file_item: dict) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        return
    if file_item.get("vectorStoreId") and file_item.get("vectorStoreFileId"):
        try:
            openai_request(
                f"/vector_stores/{urllib.parse.quote(file_item['vectorStoreId'])}/files/{urllib.parse.quote(file_item['vectorStoreFileId'])}",
                method="DELETE",
            )
        except Exception:
            pass
    if file_item.get("openaiFileId"):
        try:
            openai_request(f"/files/{urllib.parse.quote(file_item['openaiFileId'])}", method="DELETE")
        except Exception:
            pass


def run_scheduler(force: bool, source: str) -> dict:
    db = read_db()
    cadence_days = clamp(int(db["settings"].get("cadenceDays") or 3), 1, 30)
    last = db["settings"].get("lastSchedulerRun")
    if last:
        last_ts = datetime.fromisoformat(last.replace("Z", "+00:00")).timestamp()
    else:
        last_ts = 0
    if not force and (not db["settings"].get("schedulerEnabled", True) or time.time() - last_ts < cadence_days * 86400):
        return {"ok": True, "skipped": True, "reason": "No toca generar todavia", "state": decorate_state(db)}

    active_themes = [theme for theme in db["themes"] if theme.get("active", True)][:3]
    post_type_id = db["settings"].get("defaultPostTypeId") or db["postTypes"][0]["id"]
    generated = []
    errors = []
    pipeline = EditorialPipeline(model=db.get("settings", {}).get("model"))
    for theme in active_themes:
        try:
            request = {
                "canal": "linkedin",
                "tipo_post": theme.get("id") if theme.get("id") in POST_TYPES and theme.get("id") != "auto" else post_type_id,
                "objetivo": "autoridad",
                "audiencia_principal": "mixta",
                "sector": ", ".join(theme.get("pillars", [])[:2]),
                "marca_o_entidad": "Nexia GP",
                "tema_libre": theme.get("description", ""),
                "cta_preferida": "comentario",
                "usar_enlace": False,
                "nivel_promocional": "bajo",
                "necesita_adaptacion_multicanal": True,
                "notas_humanas": "Generacion automatica por cadencia editorial. Evitar repetir ideas usadas.",
            }
            result = pipeline.run(request, db)
            post = result["post"]
            if db["settings"].get("publishMode") == "ready":
                post["status"] = "ready"
            elif db["settings"].get("publishMode") == "auto":
                publish_post(db, post)
            db.setdefault("posts", []).insert(0, post)
            register_editorial_idea(db, post)
            generated.append(post)
        except Exception as exc:
            errors.append({"themeId": theme["id"], "error": str(exc)})

    latest = db
    latest["settings"]["lastSchedulerRun"] = now_iso()
    latest["schedulerLog"] = [
        {
            "id": uid("run"),
            "createdAt": latest["settings"]["lastSchedulerRun"],
            "source": source,
            "generated": len(generated),
            "errors": errors,
        }
    ] + latest.get("schedulerLog", [])
    latest["schedulerLog"] = latest["schedulerLog"][:50]
    write_db(latest)
    return {"ok": True, "skipped": False, "generated": generated, "errors": errors, "state": decorate_state(latest)}


def scheduler_loop() -> None:
    while True:
        time.sleep(3600)
        try:
            run_scheduler(force=False, source="timer")
        except Exception as exc:
            print("Scheduler error:", exc)


def publish_post(db: dict, post: dict) -> None:
    webhook = os.getenv("SOCIAL_WEBHOOK_URL")
    if not webhook:
        post["status"] = "ready"
        post["publishResult"] = {"ok": False, "message": "SOCIAL_WEBHOOK_URL no configurado. Post listo para revision."}
        post["updatedAt"] = now_iso()
        return
    payload = json.dumps({"client": db["client"], "post": post}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"content-type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            text = response.read().decode("utf-8", errors="replace")
            post["status"] = "published"
            post["publishedAt"] = now_iso()
            post["publishResult"] = {"ok": True, "status": response.status, "message": text[:1000]}
    except urllib.error.HTTPError as exc:
        post["status"] = "ready"
        post["publishResult"] = {"ok": False, "status": exc.code, "message": exc.read().decode("utf-8", "replace")[:1000]}
    post["updatedAt"] = now_iso()


def openai_request(endpoint: str, method: str = "GET", payload: dict | None = None, data: bytes | None = None, content_type: str | None = None) -> dict:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ApiError("Falta OPENAI_API_KEY", 400)
    headers = {"authorization": f"Bearer {key}"}
    body = data
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["content-type"] = "application/json"
    elif content_type:
        headers["content-type"] = content_type

    req = urllib.request.Request(f"{OPENAI_BASE_URL}{endpoint}", data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=180) as response:
            text = response.read().decode("utf-8", errors="replace")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(text)
            message = payload.get("error", {}).get("message") or text
        except Exception:
            message = text
        raise ApiError(message, exc.code, "openai_error")


def encode_multipart(fields: dict[str, str], files: dict[str, tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = f"----NexiaGP{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode(),
                b"\r\n",
            ]
        )
    for name, (filename, content_type, content) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                content,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def extract_output_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks = []
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if isinstance(content.get("text"), str):
                    chunks.append(content["text"])
                if isinstance(content.get("output_text"), str):
                    chunks.append(content["output_text"])
    return "\n".join(chunks).strip()


def sanitize_post(post: dict) -> dict:
    safe = dict(post)
    safe.pop("imageLocalPath", None)
    return safe


# ----- Blog settings & prompt-override helpers -----

BLOG_SETTINGS_KEYS = {
    "defaultModel",
    "defaultLength",
    "defaultFramework",
    "defaultAudience",
    "imagesPerArticle",
    "imageQuality",
    "costTargetCents",
}

BLOG_SETTINGS_DEFAULTS = {
    "defaultModel": "gpt-5.4-mini",
    "defaultLength": "medio",
    "defaultFramework": "pas",
    "defaultAudience": "fabricantes",
    "imagesPerArticle": 2,
    "imageQuality": "standard",
    "costTargetCents": 30,
}


def normalize_blog_settings(blog: dict) -> dict:
    for key, default in BLOG_SETTINGS_DEFAULTS.items():
        if key not in blog or blog[key] in (None, ""):
            blog[key] = default
    try:
        blog["imagesPerArticle"] = clamp(int(blog.get("imagesPerArticle") or 2), 0, 6)
    except (TypeError, ValueError):
        blog["imagesPerArticle"] = 2
    try:
        blog["costTargetCents"] = clamp(int(blog.get("costTargetCents") or 30), 0, 1000)
    except (TypeError, ValueError):
        blog["costTargetCents"] = 30
    if blog.get("imageQuality") not in {"low", "standard", "high"}:
        blog["imageQuality"] = "standard"
    return blog


def _ensure_prompt_baseline(db: dict, prompt_id: str) -> list:
    """Make sure prompt_versions[prompt_id] has a v1 baseline read from the .txt file."""
    versions = db.setdefault("prompt_versions", {})
    history = versions.setdefault(prompt_id, [])
    if not history:
        try:
            file_text = prompt_service.read_file_prompt(prompt_id)
        except FileNotFoundError:
            file_text = ""
        history.append({
            "version": 1,
            "text": file_text,
            "source": "file",
            "note": "baseline desde archivo .txt",
            "createdAt": now_iso(),
        })
    return history


def save_prompt_override(prompt_id: str, text: str, note: str = "") -> dict:
    """Append a new version and set it as the active override. Returns updated detail."""
    text = (text or "").strip()
    if not text:
        raise ApiError("El texto del prompt no puede estar vacio", 400)
    db = read_db()
    db.setdefault("prompt_overrides", {})
    history = _ensure_prompt_baseline(db, prompt_id)
    next_version = max((int(v.get("version") or 0) for v in history), default=0) + 1
    entry = {
        "version": next_version,
        "text": text,
        "source": "user",
        "note": note or "",
        "createdAt": now_iso(),
    }
    history.append(entry)
    db["prompt_overrides"][prompt_id] = {
        "text": text,
        "version": next_version,
        "source": "user",
        "updatedAt": entry["createdAt"],
    }
    write_db(db)
    return prompt_service.get_prompt_detail(prompt_id)


def revert_prompt_to_version(prompt_id: str, version: int) -> dict:
    """Restore a previous version by appending it again as a new version (no destructive ops)."""
    if version <= 0:
        raise ApiError("Versión inválida", 400)
    db = read_db()
    history = _ensure_prompt_baseline(db, prompt_id)
    source_entry = next((v for v in history if int(v.get("version") or 0) == version), None)
    if not source_entry:
        raise ApiError(f"Versión {version} no encontrada", 404)
    next_version = max((int(v.get("version") or 0) for v in history), default=0) + 1
    new_entry = {
        "version": next_version,
        "text": source_entry.get("text", ""),
        "source": "revert",
        "note": f"Revert a v{version}",
        "createdAt": now_iso(),
    }
    history.append(new_entry)
    db.setdefault("prompt_overrides", {})[prompt_id] = {
        "text": new_entry["text"],
        "version": next_version,
        "source": "revert",
        "updatedAt": new_entry["createdAt"],
    }
    write_db(db)
    return prompt_service.get_prompt_detail(prompt_id)


def decorate_state(db: dict) -> dict:
    posts = [sanitize_post(p) for p in db.get("posts", [])]
    files = []
    for item in db.get("files", []):
        safe = dict(item)
        safe.pop("localPath", None)
        if not safe.get("localSourcePath"):
            safe.pop("localSourcePath", None)
        files.append(safe)
    counts = {
        "posts": len(posts),
        "draft": sum(1 for post in posts if post.get("status") == "draft"),
        "ready": sum(1 for post in posts if post.get("status") == "ready"),
        "published": sum(1 for post in posts if post.get("status") == "published"),
        "files": len(files),
        "ideas": sum(len(theme.get("usedIdeas", [])) for theme in db.get("themes", [])),
    }
    blogs = db.get("blogs", [])
    counts["blogs"] = len(blogs)
    counts["blogsDraft"] = sum(1 for b in blogs if b.get("status") == "draft")
    counts["blogsReady"] = sum(1 for b in blogs if b.get("status") == "ready")
    counts["blogsPublished"] = sum(1 for b in blogs if b.get("status") == "published")
    settings = dict(db.get("settings", {}))
    settings["blog"] = normalize_blog_settings(dict(settings.get("blog") or {}))
    return {
        "ok": True,
        "hasOpenAIKey": bool(os.getenv("OPENAI_API_KEY")),
        "hasSocialWebhook": bool(os.getenv("SOCIAL_WEBHOOK_URL")),
        "client": db.get("client", {}),
        "settings": settings,
        "themes": db.get("themes", []),
        "postTypes": db.get("postTypes", []),
        "files": files,
        "posts": posts,
        "blogs": blogs,
        "schedulerLog": db.get("schedulerLog", []),
        "counts": counts,
        "editorialOptions": editorial_options()["options"],
        "blogOptions": blog_options()["options"],
        "prompts": prompt_service.list_prompts_meta(),
    }


def editorial_options() -> dict:
    return {
        "ok": True,
        "options": {
            "channels": CHANNELS,
            "postTypes": POST_TYPES,
            "audiences": AUDIENCES,
            "objectives": OBJECTIVES,
            "ctaTypes": CTA_TYPES,
            "riskFlags": RISK_FLAGS,
            "promotionalLevels": {
                "bajo": "Bajo",
                "medio": "Medio",
            },
        },
    }


def read_db() -> dict:
    with DB_LOCK:
        return json.loads(DB_PATH.read_text(encoding="utf-8"))


def write_db(db: dict) -> None:
    with DB_LOCK:
        temp_path = DB_PATH.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(DB_PATH)


def normalize_theme(body: dict, previous: dict | None = None) -> dict:
    previous = previous or {}
    title = str(body.get("title") or previous.get("title") or "Nueva tematica").strip()
    return {
        "id": previous.get("id") or slugify(body.get("id") or title),
        "title": title,
        "audience": str(body.get("audience") or previous.get("audience") or "Audiencia B2B").strip(),
        "description": str(body.get("description") or previous.get("description") or "").strip(),
        "pillars": split_list(body.get("pillars", previous.get("pillars", []))),
        "active": bool(body["active"]) if "active" in body else previous.get("active", True),
        "usedIdeas": previous.get("usedIdeas", []),
    }


def normalize_post_type(body: dict, previous: dict | None = None) -> dict:
    previous = previous or {}
    label = str(body.get("label") or previous.get("label") or "Nuevo tipo de post").strip()
    return {
        "id": previous.get("id") or slugify(body.get("id") or label),
        "label": label,
        "platform": str(body.get("platform") or previous.get("platform") or "LinkedIn").strip(),
        "defaultStatus": normalize_status(body.get("defaultStatus") or previous.get("defaultStatus") or "draft"),
        "instructions": str(body.get("instructions") or previous.get("instructions") or "").strip(),
    }


def collect_used_ideas(db: dict, theme_id: str) -> list[str]:
    ideas = []
    theme = next((item for item in db["themes"] if item["id"] == theme_id), None)
    if theme:
        ideas.extend(item.get("idea") for item in theme.get("usedIdeas", []))
    ideas.extend(post.get("idea") for post in db["posts"] if post.get("themeId") == theme_id)
    return list(dict.fromkeys(item for item in ideas if item))[:80]


def normalize_status(status: str | None) -> str:
    if status in {"draft", "ready", "published", "scheduled"}:
        return status
    if status == "auto":
        return "ready"
    return "draft"


def status_from_mode(mode: str | None, fallback: str) -> str:
    if mode in {"ready", "auto"}:
        return "ready"
    return normalize_status(fallback)


def list_local_documents() -> list[dict]:
    roots = [ROOT / "Documentación Nexia", ROOT / "LinkedIn B2B Copywriting 2026.docx"]
    docs = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            docs.append({"path": root, "name": root.name, "category": "copywriting"})
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}:
                docs.append(
                    {
                        "path": path,
                        "name": path.name,
                        "category": "web" if "WEB" in [part.upper() for part in path.parts] else "brand",
                    }
                )
    return docs


def split_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[,;\n]", str(value or "")) if item.strip()]


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^\w.\- ]+", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "-", value).strip("-")
    return value[:120] or "archivo"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or uid("item")


def mime_from_filename(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def find_index(items: list[dict], item_id: str) -> int:
    for idx, item in enumerate(items):
        if item.get("id") == item_id:
            return idx
    return -1


def clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.write_text(
            json.dumps(
                {"client": {}, "settings": {}, "themes": [], "postTypes": [], "files": [], "posts": [], "blogs": [], "schedulerLog": [], "prompt_overrides": {}, "prompt_versions": {}},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return

    # Soft-migrate existing db.json: ensure top-level keys and settings.blog defaults.
    db = read_db()
    dirty = False
    for key, default in (("prompt_overrides", {}), ("prompt_versions", {}), ("blogs", []), ("schedulerLog", [])):
        if key not in db:
            db[key] = default
            dirty = True
    settings = db.setdefault("settings", {})
    blog_settings = settings.setdefault("blog", {})
    before = dict(blog_settings)
    normalize_blog_settings(blog_settings)
    if blog_settings != before:
        dirty = True
    if dirty:
        write_db(db)


if __name__ == "__main__":
    ensure_files()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    httpd = ThreadingHTTPServer(("localhost", PORT), AppHandler)
    print(f"Nexia GP Social AI running at http://localhost:{PORT}")
    httpd.serve_forever()
