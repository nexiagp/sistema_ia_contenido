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
from contextlib import contextmanager
from datetime import datetime, timezone
from http.cookies import CookieError, SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path

from src.ai.services.pipeline_service import EditorialPipeline
from src.ai.services.blog_pipeline import BlogPipeline
from src.ai.services.image_prompt_service import ImagePromptService
from src.ai.services.image_service import (
    DEFAULT_SIZE,
    ImageService,
    estimate_gpt_image_cost_cents,
    image_work_dir,
    normalize_image_request,
    uses_ephemeral_image_work_dir,
)
from src.ai.services.cloudinary_service import CloudinaryService
from src.ai.services.wordpress_service import WordPressError, WordPressService
from src.ai.services.frame_composer import compose_branded_frame
from src.ai.services.openai_client import OpenAIClient
from src.ai.services.context_helpers import normalize_hashtags
from src.ai.services.content_quality import blog_quality_gate, post_quality_gate, sanitize_article_html
from src.ai.services import prompt_service
from src.platform.supabase_store import SupabaseStore, SupabaseStoreError
from src.platform.team_auth import issue_session, valid_password_hash, valid_session_secret, verify_password, verify_session
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
from src.domain.visual import (
    COMPOSITIONS,
    DEFAULT_COMPOSITION,
    DEFAULT_DIRECTION,
    VISUAL_DIRECTIONS,
    normalize_visual_choice,
    public_visual_options,
    visual_direction_prompt,
)
from src.domain.manufacturer_sources import ensure_manufacturer_sources


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "db.json"
UPLOAD_DIR = DATA_DIR / "uploads"
IMAGES_DIR = image_work_dir()
OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.4-mini"
PORT = 8787
MAX_JSON_BODY_BYTES = 1_000_000
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_REJECTED_BODY_DRAIN_BYTES = MAX_JSON_BODY_BYTES + 64 * 1024
ALLOWED_UPLOAD_SUFFIXES = {".txt", ".md", ".pdf", ".docx", ".csv", ".xlsx"}
DB_LOCK = threading.RLock()
JOB_LOCK = threading.RLock()
GENERATION_JOBS: dict[str, dict] = {}
MAX_IMAGE_VARIANTS = 5
MAX_MANUFACTURER_SOURCE_PAGES = 5
MAX_MANUFACTURER_PAGE_BYTES = 1_000_000
MAX_MANUFACTURER_DOCUMENT_CHARS = 250_000
MANUFACTURER_FETCH_TIMEOUT_SECONDS = 20

GENERATION_STEPS = {
    "editorial": [
        ("planner", "Brief estratégico"),
        ("retrieval", "Fuentes y contexto"),
        ("writer", "Redacción"),
        ("validator", "Validación editorial"),
        ("adaptation", "Adaptaciones multicanal"),
        ("finalizing", "Guardado y trazabilidad"),
    ],
    "blog": [
        ("retrieval", "Fuentes iniciales"),
        ("planner", "Plan SEO y editorial"),
        ("retrieval_refined", "Fuentes afinadas"),
        ("writer", "Redacción del artículo"),
        ("seo", "Revisión SEO"),
        ("finalizing", "Guardado y trazabilidad"),
    ],
}


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
SUPABASE_STORE = SupabaseStore()
STATE_VERSION_KEY = "__nexiagp_state_version"
AUTH_COOKIE_NAME = "nexiagp_session"
AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 8


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
        if not is_path_within(target, PUBLIC_DIR) or not target.is_file():
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
            if self.command == "GET" and path == "/api/auth/config":
                self.send_json(auth_public_config())
                return

            if self.command == "POST" and path == "/api/auth/session":
                if auth_mode() != "supabase":
                    raise ApiError("Este método de acceso no está activo.", 404)
                self.require_same_origin()
                user = self.authenticate_request(require_bearer=True)
                self.send_json({"ok": True, "user": public_user(user)}, extra_headers={"set-cookie": auth_cookie_header(self.bearer_token())})
                return

            if self.command == "POST" and path == "/api/auth/password":
                if auth_mode() != "password":
                    raise ApiError("Este método de acceso no está activo.", 404)
                self.require_same_origin()
                if not auth_is_configured():
                    raise ApiError("El acceso protegido no está configurado todavía.", 503, "auth_not_configured")
                password = self.read_json().get("password")
                if not verify_password(password, os.getenv("NEXIAGP_SHARED_PASSWORD_HASH", "")):
                    raise ApiError("Contraseña incorrecta.", 401, "invalid_credentials")
                token = issue_session(os.getenv("NEXIAGP_SESSION_SECRET", ""))
                user = {"role": "admin", "label": "Equipo Nexia GP"}
                self.send_json({"ok": True, "user": public_user(user)}, extra_headers={"set-cookie": auth_cookie_header(token)})
                return

            if self.command == "GET" and path == "/api/auth/session":
                user = self.authenticate_request()
                self.send_json({"ok": True, "user": public_user(user)})
                return

            if self.command == "POST" and path == "/api/auth/logout":
                self.require_same_origin()
                self.send_json({"ok": True}, extra_headers={"set-cookie": expired_auth_cookie_header()})
                return

            if self.command == "GET" and path == "/api/health":
                if auth_is_required():
                    self.send_json({"ok": True, "authRequired": True, "authConfigured": auth_is_configured()})
                    return
                db = read_db()
                self.send_json(
                    {
                        "ok": True,
                        "hasOpenAIKey": bool(os.getenv("OPENAI_API_KEY")),
                        "hasSocialWebhook": bool(os.getenv("SOCIAL_WEBHOOK_URL")),
                        "hasWordPressConfig": WordPressService().enabled,
                        "model": db["settings"].get("model") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL,
                        "vectorStoreId": db["settings"].get("vectorStoreId", ""),
                    }
                )
                return

            if self.command == "GET" and path == "/api/cron/daily":
                self.require_cron_secret()
                result = run_daily_maintenance()
                self.send_json({"ok": True, **result})
                return

            if auth_is_required():
                self.authenticate_request()
                if self.command in {"POST", "PATCH", "PUT", "DELETE"}:
                    self.require_same_origin()

            if self.command == "GET" and path == "/api/state":
                self.send_json(decorate_state(read_db()))
                return

            job_match = re.match(r"^/api/jobs/([^/]+)$", path)
            if job_match and self.command == "GET":
                self.send_json(get_generation_job(job_match.group(1)))
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
                db["settings"]["schedulerEnabled"] = as_bool(db["settings"].get("schedulerEnabled"), False)
                if db["settings"].get("publishMode") not in {"draft", "ready", "auto"}:
                    db["settings"]["publishMode"] = "draft"
                if db["settings"].get("publishMode") == "auto":
                    db["settings"]["publishMode"] = "ready"
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

            if self.command == "POST" and path == "/api/jobs/editorial":
                self.send_json(start_generation_job("editorial", self.read_json()), status=202)
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

            select_post_image_match = re.match(r"^/api/posts/([^/]+)/images/([^/]+)/select$", path)
            if select_post_image_match and self.command == "POST":
                result = select_post_image_variant(
                    select_post_image_match.group(1), select_post_image_match.group(2)
                )
                self.send_json(result, status=200)
                return

            review_post_image_match = re.match(r"^/api/posts/([^/]+)/images/([^/]+)/review$", path)
            if review_post_image_match and self.command == "POST":
                body = self.read_json()
                result = review_post_image_variant(
                    review_post_image_match.group(1), review_post_image_match.group(2), body
                )
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

            if self.command == "POST" and path == "/api/jobs/blog":
                self.send_json(start_generation_job("blog", self.read_json()), status=202)
                return

            if self.command == "POST" and path == "/api/wordpress/validate":
                self.require_wordpress_sync_access()
                self.send_json(validate_wordpress_connection())
                return

            wordpress_draft_match = re.match(r"^/api/blogs/([^/]+)/wordpress/draft$", path)
            if wordpress_draft_match and self.command == "POST":
                self.require_wordpress_sync_access()
                self.read_json()  # Reserve a request body for future explicit sync options.
                self.send_json(sync_blog_to_wordpress_draft(wordpress_draft_match.group(1)))
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
                body = self.read_json()
                requested_ids = body.get("fileIds")
                if requested_ids is not None and (
                    not isinstance(requested_ids, list)
                    or any(not isinstance(item, str) or not item.strip() for item in requested_ids)
                ):
                    raise ApiError("fileIds debe ser una lista de identificadores de archivo.", 400)
                self.send_json(
                    sync_files_to_openai({item.strip() for item in requested_ids} if requested_ids is not None else None),
                    status=200,
                )
                return

            if self.command == "POST" and path == "/api/manufacturer-sources/bootstrap":
                with transaction() as db:
                    sources = ensure_manufacturer_sources(db)
                    state = decorate_state(db)
                self.send_json({"ok": True, "sources": sources, "state": state})
                return

            manufacturer_match = re.match(r"^/api/manufacturer-sources/([^/]+)$", path)
            if manufacturer_match and self.command == "PATCH":
                result = update_manufacturer_source(manufacturer_match.group(1), self.read_json())
                self.send_json(result)
                return

            manufacturer_sync_match = re.match(r"^/api/manufacturer-sources/([^/]+)/sync$", path)
            if manufacturer_sync_match and self.command == "POST":
                body = self.read_json()
                result = sync_manufacturer_source(
                    manufacturer_sync_match.group(1),
                    include_x=as_bool(body.get("syncX"), False),
                    include_web=as_bool(body.get("syncWeb"), True),
                )
                self.send_json(result)
                return

            file_match = re.match(r"^/api/files/([^/]+)$", path)
            if file_match and self.command == "DELETE":
                snapshot = read_db()
                file_item = next((item for item in snapshot["files"] if item["id"] == file_match.group(1)), None)
                if not file_item:
                    raise ApiError("Archivo no encontrado", 404)
                delete_remote_file_if_possible(file_item)
                with transaction() as db:
                    db["files"] = [item for item in db["files"] if item["id"] != file_item["id"]]
                    state = decorate_state(db)
                delete_source_file_if_possible(file_item)
                self.send_json(state)
                return

            post_match = re.match(r"^/api/posts/([^/]+)$", path)
            if post_match and self.command == "PATCH":
                body = self.read_json()
                with transaction() as db:
                    post = next((item for item in db["posts"] if item["id"] == post_match.group(1)), None)
                    if not post:
                        raise ApiError("Post no encontrado", 404)
                    apply_post_edits(post, body)
                    post["updatedAt"] = now_iso()
                    state = decorate_state(db)
                self.send_json(state)
                return

            if post_match and self.command == "DELETE":
                with transaction() as db:
                    db["posts"] = [item for item in db["posts"] if item["id"] != post_match.group(1)]
                    state = decorate_state(db)
                self.send_json(state)
                return

            publish_match = re.match(r"^/api/posts/([^/]+)/publish$", path)
            if publish_match and self.command == "POST":
                with transaction() as db:
                    post = next((item for item in db["posts"] if item["id"] == publish_match.group(1)), None)
                    if not post:
                        raise ApiError("Post no encontrado", 404)
                    publish_post(db, post, require_webhook=True)
                    state = decorate_state(db)
                self.send_json(state)
                return

            raise ApiError("Ruta no encontrada", 404)
        except ApiError as exc:
            self.send_json({"ok": False, "error": exc.message, "code": exc.code}, status=exc.status)
        except Exception as exc:
            print("API error:", repr(exc))
            self.send_json(
                {"ok": False, "error": "Error interno. Revisa el registro local para más detalle.", "code": "server_error"},
                status=500,
            )

    def handle_upload(self) -> dict:
        length = read_content_length(self.headers)
        if length > MAX_UPLOAD_BYTES:
            self.discard_request_body(length)
            raise ApiError("El archivo supera el límite de 50 MB.", 413, "payload_too_large")
        if not self.headers.get("content-type", "").lower().startswith("multipart/form-data"):
            raise ApiError("La carga debe usar multipart/form-data.", 415, "unsupported_media_type")
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
        file_name = sanitize_filename(file_item.filename)
        if Path(file_name).suffix.lower() not in ALLOWED_UPLOAD_SUFFIXES:
            raise ApiError("Formato no admitido. Usa TXT, MD, PDF, DOCX, CSV o XLSX.", 415, "unsupported_media_type")
        category = re.sub(r"[^a-z0-9_-]+", "-", str(form.getfirst("category", "general")).lower()).strip("-")[:60] or "general"
        buffer = file_item.file.read(MAX_UPLOAD_BYTES + 1)
        if len(buffer) > MAX_UPLOAD_BYTES:
            raise ApiError("El archivo supera el límite de 50 MB.", 413, "payload_too_large")
        db = read_db()
        registered = register_file(
            db,
            file_name=file_name,
            mime_type=file_item.type or "application/octet-stream",
            buffer=buffer,
            category=category,
            source="upload",
        )
        write_db(db)
        return {"ok": True, "file": registered, "state": decorate_state(db)}

    def serve_image_file(self) -> None:
        if auth_is_required():
            try:
                self.authenticate_request()
            except ApiError as exc:
                self.send_json({"ok": False, "error": exc.message, "code": exc.code}, status=exc.status)
                return
        filename = urllib.parse.unquote(self.path[len("/images/"):].split("?")[0])
        if SUPABASE_STORE.enabled:
            if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
                self.send_json({"ok": False, "error": "Imagen no encontrada"}, status=404)
                return
            try:
                data, headers = SUPABASE_STORE.download_object("editorial-images", filename)
            except SupabaseStoreError:
                self.send_json({"ok": False, "error": "Imagen no encontrada"}, status=404)
                return
            content_type = headers.get("Content-Type") or headers.get("content-type") or mime_from_filename(filename)
            self.send_response(200)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(data)))
            self.send_header(
                "cache-control",
                "private, no-store" if auth_is_required() else "public, max-age=31536000, immutable",
            )
            self.end_headers()
            self.wfile.write(data)
            return
        target = (IMAGES_DIR / filename).resolve()
        if not is_path_within(target, IMAGES_DIR) or not target.is_file():
            self.send_json({"ok": False, "error": "Imagen no encontrada"}, status=404)
            return
        ext = target.suffix.lower()
        content_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(target.stat().st_size))
        self.send_header(
            "cache-control",
            "private, no-store" if auth_is_required() else "public, max-age=31536000, immutable",
        )
        self.end_headers()
        with target.open("rb") as fh:
            shutil.copyfileobj(fh, self.wfile)

    def read_json(self) -> dict:
        length = read_content_length(self.headers)
        if not length:
            return {}
        if length > MAX_JSON_BODY_BYTES:
            self.discard_request_body(length)
            raise ApiError("La solicitud JSON supera el límite permitido.", 413, "payload_too_large")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("El JSON de la solicitud no es válido.", 400, "invalid_json") from exc
        if not isinstance(payload, dict):
            raise ApiError("El JSON de la solicitud debe ser un objeto.", 400, "invalid_json")
        return payload

    def discard_request_body(self, length: int) -> None:
        """Drain bounded rejected bodies so ordinary clients receive their 413."""
        remaining = min(length, MAX_REJECTED_BODY_DRAIN_BYTES)
        while remaining > 0:
            chunk = self.rfile.read(min(64 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
        if length > MAX_REJECTED_BODY_DRAIN_BYTES:
            self.close_connection = True

    def bearer_token(self) -> str:
        authorization = self.headers.get("authorization", "")
        prefix = "Bearer "
        if authorization.startswith(prefix):
            return authorization[len(prefix):].strip()
        return ""

    def cookie_token(self) -> str:
        raw_cookie = self.headers.get("cookie", "")
        if not raw_cookie:
            return ""
        parsed = SimpleCookie()
        try:
            parsed.load(raw_cookie)
        except (CookieError, ValueError):
            return ""
        morsel = parsed.get(AUTH_COOKIE_NAME)
        return morsel.value if morsel else ""

    def authenticate_request(self, require_bearer: bool = False) -> dict:
        if not auth_is_configured():
            raise ApiError("El acceso protegido no está configurado todavía.", 503, "auth_not_configured")
        if auth_mode() == "password":
            token = "" if require_bearer else self.cookie_token()
            if not token:
                raise ApiError("Inicia sesión para continuar.", 401, "authentication_required")
            if not verify_session(token, os.getenv("NEXIAGP_SESSION_SECRET", "")):
                raise ApiError("La sesión no es válida o ha caducado.", 401, "invalid_session")
            return {"role": "admin", "label": "Equipo Nexia GP"}
        token = self.bearer_token() if require_bearer else (self.bearer_token() or self.cookie_token())
        if not token:
            raise ApiError("Inicia sesión para continuar.", 401, "authentication_required")
        try:
            identity = SUPABASE_STORE.authenticated_user(token)
            member = SUPABASE_STORE.active_member(identity["id"])
        except SupabaseStoreError as exc:
            raise ApiError("La sesión no es válida o ha caducado.", 401, "invalid_session") from exc
        if not member:
            raise ApiError("Tu cuenta no tiene acceso a Nexia GP Content.", 403, "access_denied")
        return {"id": identity["id"], "email": str(identity.get("email") or ""), "role": member.get("role", "viewer")}

    def require_same_origin(self) -> None:
        origin = self.headers.get("origin", "")
        host = self.headers.get("host", "")
        proto = (self.headers.get("x-forwarded-proto", "https").split(",")[0].strip() or "https")
        expected = f"{proto}://{host}"
        if not origin or not host or origin != expected:
            raise ApiError("Solicitud rechazada por protección de origen.", 403, "invalid_origin")

    def require_cron_secret(self) -> None:
        secret = os.getenv("CRON_SECRET", "")
        if not secret:
            raise ApiError("El cron no está configurado.", 503, "cron_not_configured")
        if self.headers.get("authorization", "") != f"Bearer {secret}":
            raise ApiError("Cron no autorizado.", 401, "cron_unauthorized")

    def require_wordpress_sync_access(self) -> None:
        """Do not let a publicly browsable editor trigger an external CMS write."""
        if os.getenv("VERCEL") == "1" and not auth_is_required():
            raise ApiError(
                "Para sincronizar WordPress activa la autenticación de Nexia GP en producción.",
                503,
                "wordpress_auth_required",
            )

    def send_json(self, payload: dict, status: int = 200, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "http_error") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def auth_mode() -> str:
    return os.getenv("NEXIAGP_AUTH_MODE", "supabase").strip().lower() or "supabase"


def auth_is_required() -> bool:
    """Use an explicit setting, while remaining fail-closed on Vercel by default."""
    if auth_mode() != "supabase":
        return True
    configured = os.getenv("NEXIAGP_AUTH_REQUIRED", "").strip().lower()
    if configured in {"0", "false", "no", "off"}:
        return False
    if configured in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("VERCEL") == "1"


def auth_is_configured() -> bool:
    if auth_mode() == "password":
        return valid_password_hash(os.getenv("NEXIAGP_SHARED_PASSWORD_HASH", "")) and valid_session_secret(
            os.getenv("NEXIAGP_SESSION_SECRET", "")
        )
    if auth_mode() != "supabase":
        return False
    return bool(
        SUPABASE_STORE.enabled
        and os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    )


def auth_public_config() -> dict:
    required = auth_is_required()
    configured = auth_is_configured()
    payload = {"ok": True, "required": required, "configured": configured, "mode": auth_mode()}
    if required and configured and auth_mode() == "supabase":
        payload.update(
            {
                "url": SUPABASE_STORE.url,
                "publishableKey": os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
            }
        )
    return payload


def public_user(user: dict) -> dict:
    return {"email": user.get("email", ""), "label": user.get("label", ""), "role": user.get("role", "viewer")}


def auth_cookie_header(token: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", token or ""):
        raise ApiError("La sesión recibida no tiene un formato válido.", 401, "invalid_session")
    return (
        f"{AUTH_COOKIE_NAME}={token}; Path=/; Max-Age={AUTH_COOKIE_MAX_AGE_SECONDS}; "
        "HttpOnly; Secure; SameSite=Strict"
    )


def expired_auth_cookie_header() -> str:
    return f"{AUTH_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict"


def read_content_length(headers) -> int:
    raw = headers.get("content-length", "0") or "0"
    try:
        length = int(raw)
    except (TypeError, ValueError) as exc:
        raise ApiError("Content-Length inválido.", 400, "invalid_content_length") from exc
    if length < 0:
        raise ApiError("Content-Length inválido.", 400, "invalid_content_length")
    return length


def is_path_within(target: Path, parent: Path) -> bool:
    try:
        target.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


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
        post_status = "review" if item.get("statusRecommendation") == "ready" or status in {"ready", "scheduled", "published"} else "draft"
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

    new_idea_entries = [
        {
            "id": uid("idea"),
            "postId": post["id"],
            "idea": post["idea"],
            "angle": post["angle"],
            "createdAt": created_at,
        }
        for post in new_posts
    ]
    with transaction() as fresh:  # persistencia atomica del delta sobre estado fresco
        fresh["posts"] = new_posts + fresh.get("posts", [])
        theme_ref = next((item for item in fresh.get("themes", []) if item["id"] == theme["id"]), None)
        if theme_ref is not None:
            theme_ref["usedIdeas"] = (new_idea_entries + theme_ref.get("usedIdeas", []))[:200]
        state = decorate_state(fresh)
    return {"ok": True, "posts": new_posts, "provider": provider, "state": state}


def run_editorial_pipeline(request: dict, on_progress=None) -> dict:
    snapshot = read_db()
    pipeline = EditorialPipeline(model=snapshot.get("settings", {}).get("model"))
    result = pipeline.run(request, snapshot, on_step=on_progress)
    post = result["post"]
    with transaction() as db:  # re-lectura fresca + insercion atomica del delta
        db.setdefault("posts", []).insert(0, post)
        register_editorial_idea(db, post)
        record_usage(db, result.get("usage"))
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
    with transaction() as fresh:
        fresh.setdefault("posts", []).insert(0, result["post"])
        register_editorial_idea(fresh, result["post"])
        record_usage(fresh, result.get("usage"))
        result["state"] = decorate_state(fresh)
    return result


def adapt_editorial_post(post_id: str) -> dict:
    snapshot = read_db()
    post = next((item for item in snapshot.get("posts", []) if item.get("id") == post_id), None)
    if not post:
        raise ApiError("Post no encontrado", 404)
    pipeline = EditorialPipeline(model=snapshot.get("settings", {}).get("model"))
    adaptations = pipeline.adapt_existing(post, snapshot)  # trabajo lento sobre snapshot
    with transaction() as fresh:
        fresh_post = next((p for p in fresh.get("posts", []) if p.get("id") == post_id), None)
        if fresh_post is None:
            raise ApiError("Post no encontrado", 404)
        fresh_post["adaptations"] = adaptations
        fresh_post.setdefault("responseIds", {})["adaptation"] = post.get("responseIds", {}).get("adaptation")
        fresh_post["updatedAt"] = now_iso()
        state = decorate_state(fresh)
    return {"ok": True, "adaptations": adaptations, "state": state}


def _ensure_image_variant_id(image: dict) -> str:
    """Give legacy and newly generated images a durable, local identifier."""
    image_id = str(image.get("id") or "").strip()
    if image_id:
        return image_id
    fingerprint = str(
        image.get("url")
        or image.get("displayUrl")
        or image.get("generatedAt")
        or "nexia-image"
    )
    image_id = f"img_{uuid.uuid5(uuid.NAMESPACE_URL, fingerprint).hex[:16]}"
    image["id"] = image_id
    return image_id


def post_image_variants(post: dict) -> list[dict]:
    """Return a de-duplicated, newest-first set of reusable visual concepts."""
    candidates: list[dict] = []
    active_image = post.get("image")
    if isinstance(active_image, dict):
        candidates.append(active_image)
    candidates.extend(item for item in post.get("imageVariants", []) if isinstance(item, dict))

    variants: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        image_id = _ensure_image_variant_id(candidate)
        if image_id in seen:
            continue
        seen.add(image_id)
        variants.append(candidate)
    return variants[:MAX_IMAGE_VARIANTS]


def _find_post_image_variant(post: dict, image_id: str) -> tuple[list[dict], dict]:
    variants = post_image_variants(post)
    target = next((item for item in variants if item.get("id") == image_id), None)
    if target is None:
        raise ApiError("Concepto visual no encontrado", 404)
    return variants, target


def select_post_image_variant(post_id: str, image_id: str) -> dict:
    """Make a retained visual concept the image currently used by the draft."""
    with transaction() as fresh:
        post = next((item for item in fresh.get("posts", []) if item.get("id") == post_id), None)
        if post is None:
            raise ApiError("Post no encontrado", 404)
        variants, target = _find_post_image_variant(post, image_id)
        post["imageVariants"] = variants
        post["image"] = target
        post["updatedAt"] = now_iso()
        state = decorate_state(fresh)
    return {"ok": True, "image": target, "state": state}


def review_post_image_variant(post_id: str, image_id: str, payload: dict) -> dict:
    """Persist a deliberately small human approval signal for the chosen visual."""
    approved = as_bool(payload.get("approved"), True)
    with transaction() as fresh:
        post = next((item for item in fresh.get("posts", []) if item.get("id") == post_id), None)
        if post is None:
            raise ApiError("Post no encontrado", 404)
        variants, target = _find_post_image_variant(post, image_id)
        target["review"] = {
            "status": "approved" if approved else "pending",
            "reviewedAt": now_iso() if approved else None,
            "checklistVersion": 1,
        }
        post["imageVariants"] = variants
        if isinstance(post.get("image"), dict) and post["image"].get("id") == image_id:
            post["image"] = target
        post["updatedAt"] = now_iso()
        state = decorate_state(fresh)
    return {"ok": True, "image": target, "state": state}


def brand_treatment_label(with_frame: bool, with_logo: bool) -> str:
    if with_frame and with_logo:
        return "frame_logo"
    if with_frame:
        return "frame"
    if with_logo:
        return "logo"
    return "clean"


def brand_asset_suffix(with_frame: bool, with_logo: bool) -> str:
    return {
        "frame_logo": "_frame-logo",
        "frame": "_frame",
        "logo": "_logo",
    }[brand_treatment_label(with_frame, with_logo)]


def generate_post_image(post_id: str, config: dict) -> dict:
    db = read_db()
    post = next((item for item in db.get("posts", []) if item.get("id") == post_id), None)
    if not post:
        raise ApiError("Post no encontrado", 404)
    if not os.getenv("OPENAI_API_KEY"):
        raise ApiError("Falta OPENAI_API_KEY", 400)
    if uses_ephemeral_image_work_dir() and not SUPABASE_STORE.enabled:
        raise ApiError(
            "El almacenamiento persistente de imágenes no está configurado en este entorno.",
            503,
        )

    user_notes = config.get("userNotes") or ""
    size, quality = normalize_image_request(config.get("size") or DEFAULT_SIZE, config.get("quality") or "medium")
    with_frame = as_bool(config.get("withFrame"), True)
    # Legacy images exposed one switch. Preserve that decision as frame + logo
    # whenever a stored or API caller does not yet send ``withLogo``.
    with_logo = as_bool(config.get("withLogo"), with_frame)
    has_brand_treatment = with_frame or with_logo
    direction, composition = normalize_visual_choice(
        config.get("direction") or DEFAULT_DIRECTION,
        config.get("composition") or DEFAULT_COMPOSITION,
    )
    style = f"{VISUAL_DIRECTIONS[direction]['label']} · {COMPOSITIONS[composition]['label']}"

    client = OpenAIClient(model=db.get("settings", {}).get("model"))
    prompt_result, prompt_response_id = ImagePromptService(client).generate_prompt(
        post,
        direction,
        composition,
        user_notes,
        with_branding=has_brand_treatment,
    )
    image_prompt = prompt_result["image_prompt"]
    generated_image = ImageService().generate(image_prompt, size=size, quality=quality)
    filename = generated_image.filename
    local_path = IMAGES_DIR / filename

    if has_brand_treatment:
        public_id_suffix = brand_asset_suffix(with_frame, with_logo)
        upload_path = IMAGES_DIR / f"{Path(filename).stem}{public_id_suffix}.png"
        compose_branded_frame(local_path, upload_path, with_frame=with_frame, with_logo=with_logo)
    else:
        upload_path = local_path
        public_id_suffix = ""
    local_display_url = f"/images/{upload_path.name}"
    if SUPABASE_STORE.enabled:
        # Persist both original and composed assets before the serverless
        # invocation ends: Vercel's filesystem is only temporary.
        SUPABASE_STORE.upload_object("editorial-images", filename, local_path.read_bytes(), "image/png")
        if upload_path.name != filename:
            SUPABASE_STORE.upload_object("editorial-images", upload_path.name, upload_path.read_bytes(), "image/png")

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
                # The compositor embeds the selected treatment locally. The CDN
                # only delivers that exact result; it never adds a second overlay.
                "brandedUrl": upload_result.get("secure_url") if has_brand_treatment else None,
                "withFrame": with_frame,
                "withLogo": with_logo,
            }
        except Exception as exc:
            print("Cloudinary upload error:", exc)

    now = now_iso()
    image_obj = {
        "id": uid("img"),
        "url": f"/images/{filename}",
        "displayUrl": (
            cloudinary_data.get("brandedUrl") if cloudinary_data and has_brand_treatment
            else cloudinary_data.get("rawUrl") if cloudinary_data
            else local_display_url
        ),
        "brandedUrl": cloudinary_data["brandedUrl"] if cloudinary_data else local_display_url if has_brand_treatment else None,
        "cloudinary": cloudinary_data,
        "prompt": image_prompt,
        "sceneRationale": prompt_result.get("scene_rationale", ""),
        "config": {
            "style": style,
            "direction": direction,
            "composition": composition,
            "size": size,
            "quality": quality,
            "userNotes": user_notes,
            "withFrame": with_frame,
            "withLogo": with_logo,
            "brandTreatment": brand_treatment_label(with_frame, with_logo),
        },
        "review": {"status": "pending", "reviewedAt": None, "checklistVersion": 1},
        "generatedAt": now,
        "promptResponseId": prompt_response_id,
        "sizeBytes": generated_image.size_bytes,
        "validation": generated_image.validation(),
    }
    with transaction() as fresh:  # re-localiza el post en estado fresco y aplica el delta
        fresh_post = next((p for p in fresh.get("posts", []) if p.get("id") == post_id), None)
        if fresh_post is None:
            raise ApiError("Post no encontrado", 404)
        existing_variants = [
            item for item in post_image_variants(fresh_post)
            if item.get("id") != image_obj["id"]
        ]
        fresh_post["imageVariants"] = [image_obj, *existing_variants][:MAX_IMAGE_VARIANTS]
        fresh_post["image"] = image_obj
        # A Vercel path belongs to /tmp and disappears with the invocation.  The
        # durable asset is the matching object already uploaded to Supabase.
        if uses_ephemeral_image_work_dir():
            fresh_post.pop("imageLocalPath", None)
        else:
            fresh_post["imageLocalPath"] = str(local_path)
        fresh_post["updatedAt"] = now
        state = decorate_state(fresh)
    if uses_ephemeral_image_work_dir():
        for staged_path in {local_path, upload_path}:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError as exc:
                print(f"No se pudo limpiar la imagen temporal {staged_path.name}: {exc}")
    return {"ok": True, "image": image_obj, "state": state}


def run_blog_pipeline(request: dict, on_progress=None) -> dict:
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
    result = pipeline.run(enriched_request, db, on_step=on_progress)
    blog = result["blog"]
    with transaction() as fresh:
        fresh.setdefault("blogs", []).insert(0, blog)
        record_usage(fresh, result.get("usage"))
        result["state"] = decorate_state(fresh)
    return result


def start_generation_job(kind: str, request: dict) -> dict:
    """Launch an editorial or blog run without holding an HTTP request open.

    The local application retains its responsive in-memory worker. In a managed
    environment the job is first persisted in Supabase and then claimed by the
    current Vercel invocation, so an interrupted function leaves a recoverable
    job rather than silently losing the request.
    """
    if kind not in GENERATION_STEPS:
        raise ApiError("Tipo de generación no soportado", 400)

    now = now_iso()
    job_id = uid("job")
    job = {
        "id": job_id,
        "kind": kind,
        "status": "queued",
        "message": "Preparando la generación…",
        "createdAt": now,
        "updatedAt": now,
        "resultId": None,
        "error": None,
        "steps": [
            {"id": step_id, "label": label, "status": "pending"}
            for step_id, label in GENERATION_STEPS[kind]
        ],
    }
    if SUPABASE_STORE.enabled:
        SUPABASE_STORE.create_generation_job(job_id, kind, request, generation_job_progress(job))
        process_one_remote_generation_job()
        remote = SUPABASE_STORE.get_generation_job(job_id)
        if not remote:
            raise ApiError("No se ha podido recuperar el trabajo de generación.", 500, "job_not_found")
        return generation_job_snapshot(remote_generation_job(remote))

    with JOB_LOCK:
        GENERATION_JOBS[job_id] = job
        # Keep memory bounded when the local server stays open for weeks.
        completed_ids = [
            key for key, value in GENERATION_JOBS.items()
            if value.get("status") in {"completed", "failed"}
        ]
        for old_id in completed_ids[:-40]:
            GENERATION_JOBS.pop(old_id, None)

    def progress(step_id: str, message: str) -> None:
        with JOB_LOCK:
            target = GENERATION_JOBS.get(job_id)
            if not target:
                return
            target["status"] = "running"
            target["message"] = message
            target["updatedAt"] = now_iso()
            active_index = next((i for i, item in enumerate(target["steps"]) if item["id"] == step_id), None)
            if active_index is None:
                return
            for index, item in enumerate(target["steps"]):
                if index < active_index and item["status"] == "pending":
                    item["status"] = "completed"
                elif index == active_index:
                    item["status"] = "running"

    def worker() -> None:
        try:
            progress(GENERATION_STEPS[kind][0][0], "Iniciando el flujo editorial…")
            result = (
                run_editorial_pipeline(request, on_progress=progress)
                if kind == "editorial"
                else run_blog_pipeline(request, on_progress=progress)
            )
            with JOB_LOCK:
                target = GENERATION_JOBS.get(job_id)
                if not target:
                    return
                for item in target["steps"]:
                    item["status"] = "completed"
                target["status"] = "completed"
                target["message"] = "Generación completada y guardada para revisión."
                target["resultId"] = (result.get("post") or result.get("blog") or {}).get("id")
                target["updatedAt"] = now_iso()
        except Exception as exc:
            with JOB_LOCK:
                target = GENERATION_JOBS.get(job_id)
                if not target:
                    return
                target["status"] = "failed"
                target["message"] = "La generación no se ha completado."
                target["error"] = str(exc)
                target["updatedAt"] = now_iso()

    threading.Thread(target=worker, daemon=True, name=f"nexia-{kind}-{job_id}").start()
    return generation_job_snapshot(job)


def generation_job_snapshot(job: dict) -> dict:
    return {
        "ok": True,
        "job": {
            "id": job["id"],
            "kind": job["kind"],
            "status": job["status"],
            "message": job["message"],
            "createdAt": job["createdAt"],
            "updatedAt": job["updatedAt"],
            "resultId": job.get("resultId"),
            "error": job.get("error"),
            "steps": [dict(item) for item in job.get("steps", [])],
        },
    }


def get_generation_job(job_id: str) -> dict:
    if SUPABASE_STORE.enabled:
        job = SUPABASE_STORE.get_generation_job(job_id)
        if not job:
            raise ApiError("Trabajo de generación no encontrado o caducado", 404)
        return generation_job_snapshot(remote_generation_job(job))
    with JOB_LOCK:
        job = GENERATION_JOBS.get(job_id)
        if not job:
            raise ApiError("Trabajo de generación no encontrado o caducado", 404)
        return generation_job_snapshot(job)


def generation_job_progress(job: dict) -> dict:
    return {
        "message": job.get("message") or "Preparando la generación…",
        "createdAt": job.get("createdAt") or now_iso(),
        "updatedAt": job.get("updatedAt") or now_iso(),
        "resultId": job.get("resultId"),
        "steps": [dict(item) for item in job.get("steps", [])],
    }


def remote_generation_job(row: dict) -> dict:
    progress = dict(row.get("progress") or {})
    result = dict(row.get("result") or {})
    error = row.get("error") or {}
    if isinstance(error, str):
        error = {"message": error}
    return {
        "id": row.get("id"),
        "kind": row.get("kind"),
        "status": row.get("status"),
        "message": progress.get("message") or "Preparando la generación…",
        "createdAt": progress.get("createdAt") or row.get("created_at") or now_iso(),
        "updatedAt": progress.get("updatedAt") or row.get("updated_at") or now_iso(),
        "resultId": progress.get("resultId") or result.get("resultId"),
        "error": error.get("message") if isinstance(error, dict) else None,
        "steps": [dict(item) for item in progress.get("steps", [])],
    }


def persist_remote_generation_job(job: dict, **extra: object) -> dict:
    values = {"status": job["status"], "progress": generation_job_progress(job), **extra}
    return SUPABASE_STORE.update_generation_job(job["id"], values)


def process_one_remote_generation_job() -> dict | None:
    """Claim and process one durable job within the current serverless request."""
    if not SUPABASE_STORE.enabled:
        return None
    claimed = SUPABASE_STORE.claim_generation_job(lease_seconds=780)
    if not claimed:
        return None
    job = remote_generation_job(claimed)
    request = dict(claimed.get("request") or {})
    kind = job.get("kind")
    if kind not in GENERATION_STEPS:
        job.update({"status": "failed", "message": "Tipo de generación no soportado.", "error": "Tipo de generación no soportado.", "updatedAt": now_iso()})
        persist_remote_generation_job(job, error={"message": job["error"]}, completed_at=now_iso(), locked_until=None)
        return generation_job_snapshot(job)

    def progress(step_id: str, message: str) -> None:
        job["status"] = "running"
        job["message"] = message
        job["updatedAt"] = now_iso()
        active_index = next((i for i, item in enumerate(job["steps"]) if item["id"] == step_id), None)
        if active_index is not None:
            for index, item in enumerate(job["steps"]):
                if index < active_index and item["status"] == "pending":
                    item["status"] = "completed"
                elif index == active_index:
                    item["status"] = "running"
        persist_remote_generation_job(job)

    try:
        progress(GENERATION_STEPS[kind][0][0], "Iniciando el flujo editorial…")
        result = (
            run_editorial_pipeline(request, on_progress=progress)
            if kind == "editorial"
            else run_blog_pipeline(request, on_progress=progress)
        )
        for item in job["steps"]:
            item["status"] = "completed"
        job["status"] = "completed"
        job["message"] = "Generación completada y guardada para revisión."
        job["resultId"] = (result.get("post") or result.get("blog") or {}).get("id")
        job["updatedAt"] = now_iso()
        persisted = persist_remote_generation_job(
            job,
            result={"resultId": job["resultId"]},
            error=None,
            completed_at=now_iso(),
            locked_until=None,
        )
        return generation_job_snapshot(remote_generation_job(persisted))
    except Exception as exc:
        job["status"] = "failed"
        job["message"] = "La generación no se ha completado."
        job["error"] = str(exc)[:1200]
        job["updatedAt"] = now_iso()
        persisted = persist_remote_generation_job(
            job,
            error={"message": job["error"]},
            completed_at=now_iso(),
            locked_until=None,
        )
        return generation_job_snapshot(remote_generation_job(persisted))


def refresh_blog_quality_gate(blog: dict) -> dict:
    """Sanitize the effective article and refresh its deterministic ready gate."""
    previous_gate = blog.get("qualityGate")
    article = blog.setdefault("article", {})
    effective_article = dict(article)
    has_override = isinstance(article.get("article_html_override"), str) and article.get("article_html_override").strip()
    if has_override:
        effective_article["article_html"] = article["article_html_override"]
    safe_article, safe_seo, quality_gate = blog_quality_gate(
        blog.get("request") or {},
        blog.get("brief") or {},
        blog.get("retrieval") or {},
        effective_article,
        blog.get("seo") or {},
    )
    if has_override:
        article["article_html_override"] = safe_article.get("article_html", "")
        article["word_count"] = safe_article.get("word_count", 0)
        article["internal_links_used"] = safe_article.get("internal_links_used", [])
    else:
        blog["article"] = safe_article
    blog["seo"] = safe_seo
    blog["wordCount"] = safe_article.get("word_count", 0)
    # A sync re-runs the deterministic checks to avoid sending stale content,
    # but it must not discard the editorial acknowledgement already recorded
    # for that same content.  Losing it made an approved blog appear pending
    # again when the WordPress draft action was pressed.
    if isinstance(previous_gate, dict) and previous_gate.get("reviewAcknowledgedAt"):
        quality_gate["reviewAcknowledgedAt"] = previous_gate["reviewAcknowledgedAt"]
        quality_gate["reviewAcknowledged"] = True
        quality_gate["can_mark_ready"] = True
    blog["qualityGate"] = quality_gate
    return quality_gate


def acknowledge_quality_gate(content: dict) -> None:
    gate = content.get("qualityGate")
    if not isinstance(gate, dict) or not gate.get("blockers"):
        return
    gate["reviewAcknowledgedAt"] = now_iso()
    gate["reviewAcknowledged"] = True
    gate["can_mark_ready"] = True


def has_unacknowledged_quality_gate(content: dict) -> bool:
    gate = content.get("qualityGate")
    if isinstance(gate, dict):
        return bool(gate.get("blockers")) and not bool(gate.get("reviewAcknowledgedAt"))
    validation = content.get("validation") or {}
    return bool(validation.get("human_review_required") or validation.get("review_flags"))


def patch_blog(blog_id: str, body: dict) -> dict:
    allowed_fields = {"status", "scheduledFor", "metaTitle", "metaDescription", "slug", "title", "articleHtmlOverride"}
    with transaction() as db:
        blog = next((item for item in db.get("blogs", []) if item.get("id") == blog_id), None)
        if not blog:
            raise ApiError("Blog no encontrado", 404)
        for key in allowed_fields:
            if key in body:
                if key == "status" and body[key] not in BLOG_STATUSES:
                    continue
                if key == "scheduledFor":
                    continue
                if key == "articleHtmlOverride":
                    if not isinstance(body[key], str):
                        raise ApiError("El HTML del artículo debe ser texto.", 400)
                    blog.setdefault("article", {})["article_html_override"] = body[key]
                elif key != "status":
                    blog[key] = body[key]
        # Any editorial change requires a fresh human acknowledgement.  A
        # status-only update or a WordPress re-sync keeps the prior approval.
        if any(key in body for key in {"metaTitle", "metaDescription", "slug", "title", "articleHtmlOverride"}):
            existing_gate = blog.get("qualityGate")
            if isinstance(existing_gate, dict) and existing_gate.get("blockers"):
                existing_gate.pop("reviewAcknowledgedAt", None)
                existing_gate.pop("reviewAcknowledged", None)
                existing_gate["can_mark_ready"] = False
        quality_gate = refresh_blog_quality_gate(blog)
        if as_bool(body.get("reviewAcknowledged"), False):
            acknowledge_quality_gate(blog)
        requested_status = body.get("status") if body.get("status") in BLOG_STATUSES else None
        if requested_status == "published":
            raise ApiError("La publicación de blogs no está conectada todavía; usa el estado listo.", 409)
        if "scheduledFor" in body:
            if has_unacknowledged_quality_gate(blog):
                raise ApiError(
                    "El blog requiere revisión humana registrada antes de programarlo.",
                    409,
                    "quality_review_required",
                )
            raw_date = body.get("scheduledFor")
            if not isinstance(raw_date, str) or not raw_date.strip():
                raise ApiError("Indica una fecha válida para planificar el blog", 400)
            try:
                planned_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ApiError("La fecha de planificación no es válida", 400) from exc
            if planned_at.tzinfo is None:
                planned_at = planned_at.replace(tzinfo=timezone.utc)
            blog["scheduledFor"] = planned_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            blog["status"] = "scheduled"
        elif requested_status:
            if requested_status == "scheduled":
                raise ApiError("Indica una fecha y una hora para programar el blog", 400)
            if requested_status in {"ready", "published"} and has_unacknowledged_quality_gate(blog):
                raise ApiError(
                    "El blog requiere revisión humana registrada antes de marcarlo como listo.",
                    409,
                    "quality_review_required",
                )
            blog["status"] = requested_status
            if requested_status != "scheduled":
                blog.pop("scheduledFor", None)
        blog["updatedAt"] = now_iso()
        return {"ok": True, "blog": blog, "state": decorate_state(db)}


def _wordpress_optional_id(name: str) -> int | None:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ApiError(f"La configuración {name} debe ser un identificador numérico.", 503, "wordpress_configuration") from exc
    return value if value > 0 else None


def wordpress_public_config() -> dict:
    """Return editor-safe status only; credentials never leave the server."""
    config = WordPressService().public_config()
    config["imageTargetBytes"] = 200 * 1024
    config["imageMaximumBytes"] = 1 * 1024 * 1024
    config["publicationCadenceDays"] = 15
    config["scheduledPublishingEnabled"] = False
    return config


def validate_wordpress_connection() -> dict:
    service = WordPressService()
    if not service.enabled:
        raise ApiError("La conexión con WordPress no está configurada en el servidor.", 503, "wordpress_not_configured")
    try:
        verification = service.validate()
    except WordPressError as exc:
        raise ApiError(exc.args[0], 502, "wordpress_connection_failed") from exc
    return {"ok": True, "wordpress": {**wordpress_public_config(), "verified": True, "roles": verification["roles"]}}


def wordpress_image_bytes(image: dict) -> tuple[bytes, str, str]:
    """Load the canonical editorial image without exposing a private asset URL."""
    raw_url = str(image.get("url") or "")
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/images/"):
        raise WordPressError("La imagen no tiene un activo editorial válido para enviarse a WordPress.")
    filename = urllib.parse.unquote(parsed.path[len("/images/"):])
    if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise WordPressError("La imagen del blog no se pudo localizar de forma segura.")
    if SUPABASE_STORE.enabled:
        try:
            data, headers = SUPABASE_STORE.download_object("editorial-images", filename)
        except SupabaseStoreError as exc:
            raise WordPressError("No se pudo recuperar una imagen del almacenamiento editorial.") from exc
        content_type = headers.get("Content-Type") or headers.get("content-type") or mime_from_filename(filename)
        return data, content_type, filename
    target = (IMAGES_DIR / filename).resolve()
    if not is_path_within(target, IMAGES_DIR) or not target.is_file():
        raise WordPressError("No se pudo recuperar una imagen del almacenamiento editorial.")
    return target.read_bytes(), mime_from_filename(filename), filename


def sync_blog_to_wordpress_draft(blog_id: str) -> dict:
    """Upload a reviewed blog as a WordPress draft and persist only public traceability."""
    service = WordPressService()
    if not service.enabled:
        raise ApiError("La conexión con WordPress no está configurada en el servidor.", 503, "wordpress_not_configured")
    snapshot = read_db()
    blog = next((item for item in snapshot.get("blogs", []) if item.get("id") == blog_id), None)
    if not blog:
        raise ApiError("Blog no encontrado", 404)
    refresh_blog_quality_gate(blog)
    if has_unacknowledged_quality_gate(blog):
        raise ApiError(
            "El blog requiere una revisión humana registrada antes de enviarlo a WordPress.",
            409,
            "quality_review_required",
        )
    if blog.get("status") not in {"ready", "scheduled"}:
        raise ApiError(
            "Aprueba primero el contenido para WordPress antes de crear su borrador.",
            409,
            "blog_not_ready_for_wordpress",
        )
    try:
        sync = service.sync_blog_draft(
            blog,
            image_loader=wordpress_image_bytes,
            category_id=_wordpress_optional_id("WORDPRESS_DEFAULT_CATEGORY_ID"),
            author_id=_wordpress_optional_id("WORDPRESS_AUTHOR_ID"),
        )
    except WordPressError as exc:
        message = exc.args[0] if exc.args else "No se pudo sincronizar el borrador con WordPress."
        with transaction() as fresh:
            target = next((item for item in fresh.get("blogs", []) if item.get("id") == blog_id), None)
            if target:
                target["wordpress"] = {
                    **(target.get("wordpress") if isinstance(target.get("wordpress"), dict) else {}),
                    "lastError": message,
                    "lastAttemptAt": now_iso(),
                }
                target["updatedAt"] = now_iso()
        raise ApiError(message, 502, "wordpress_sync_failed") from exc

    with transaction() as fresh:
        target = next((item for item in fresh.get("blogs", []) if item.get("id") == blog_id), None)
        if not target:
            raise ApiError("Blog no encontrado", 404)
        figures_by_id = {str(item.get("figure_id") or ""): item for item in target.get("figures", [])}
        for figure_id, wordpress_figure in sync["figures"].items():
            if figure_id in figures_by_id:
                figures_by_id[figure_id]["wordpress"] = wordpress_figure
        target["wordpress"] = {
            **(target.get("wordpress") if isinstance(target.get("wordpress"), dict) else {}),
            **sync["post"],
            "contentHash": sync["contentHash"],
            "lastSyncAt": now_iso(),
            "lastAttemptAt": now_iso(),
            "lastError": None,
            "uploadedImages": sync["uploadedImages"],
            "optimizedBytes": sync["optimizedBytes"],
        }
        target["updatedAt"] = now_iso()
        state = decorate_state(fresh)
        return {
            "ok": True,
            "blog": target,
            "wordpress": target["wordpress"],
            "state": state,
        }


def delete_blog(blog_id: str) -> dict:
    with transaction() as db:
        before = len(db.get("blogs", []))
        db["blogs"] = [item for item in db.get("blogs", []) if item.get("id") != blog_id]
        if len(db["blogs"]) == before:
            raise ApiError("Blog no encontrado", 404)
        return {"ok": True, "state": decorate_state(db)}


def estimate_stored_blog_figure_cents(image: dict | None) -> float:
    """Use persisted data when available, and safely price legacy figures too."""
    if not isinstance(image, dict):
        return 0.0
    try:
        explicit = image.get("estimatedCostCents")
        if explicit is not None:
            return float(explicit)
        config = image.get("config") or {}
        return estimate_gpt_image_cost_cents(config.get("size"), config.get("quality"))
    except (TypeError, ValueError, KeyError):
        return 0.0


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
    if uses_ephemeral_image_work_dir() and not SUPABASE_STORE.enabled:
        raise ApiError(
            "El almacenamiento persistente de imágenes no está configurado en este entorno.",
            503,
        )

    blog_settings = normalize_blog_settings(dict(db.get("settings", {}).get("blog") or {}))
    # Map settings.blog.imageQuality (low|standard|high) to the image-service quality values.
    quality_map = {"low": "low", "standard": "medium", "high": "high"}
    default_quality = quality_map.get(blog_settings.get("imageQuality", "standard"), "medium")

    user_notes = config.get("userNotes") or ""
    size, quality = normalize_image_request(config.get("size") or DEFAULT_SIZE, config.get("quality") or default_quality)
    # Blog images are clean by default. Editors can independently opt into a
    # frame, the Nexia logo, or both.
    with_frame = as_bool(config.get("withFrame"), False)
    with_logo = as_bool(config.get("withLogo"), with_frame)
    has_brand_treatment = with_frame or with_logo
    direction, composition = normalize_visual_choice(
        config.get("direction") or "territorio_infraestructura",
        config.get("composition") or "contexto_amplio",
    )
    style = f"{VISUAL_DIRECTIONS[direction]['label']} · {COMPOSITIONS[composition]['label']}"
    image_cost_cents = estimate_gpt_image_cost_cents(size, quality)
    image_budget_cents = float(blog_settings.get("costTargetCents") or 0)
    # Regenerating a figure replaces its prior asset, so only other figures
    # count against the per-article media budget at preflight time.
    current_estimated_cents = sum(
        estimate_stored_blog_figure_cents(item.get("image"))
        for item in blog.get("figures", [])
        if item.get("figure_id") != figure_id
    )
    if image_budget_cents > 0 and current_estimated_cents + image_cost_cents > image_budget_cents:
        raise ApiError(
            "La imagen no se ha solicitado: el coste estimado de las figuras "
            f"({current_estimated_cents + image_cost_cents:.1f} c) supera el tope de "
            f"{image_budget_cents:.0f} c del artículo. Baja calidad/formato o aumenta el límite.",
            400,
        )

    # Combine the figure's image_prompt with any user notes; bypass the AI prompt
    # generator since the brief already has a precise image_brief.
    combined_prompt = figure.get("image_prompt", "")
    combined_prompt += "\n\n" + visual_direction_prompt(direction, composition, with_frame=has_brand_treatment)
    if user_notes:
        combined_prompt += f"\n\nUser notes: {user_notes}"
    if has_brand_treatment:
        combined_prompt += (
            "\n\nComposition note: keep the lower-right 18% visually calm and free of key subjects, "
            "signage or high-contrast detail; an exact logo is composited there after generation."
        )

    generated_image = ImageService().generate(combined_prompt, size=size, quality=quality)
    filename = generated_image.filename
    local_path = IMAGES_DIR / filename

    if has_brand_treatment:
        public_id_suffix = brand_asset_suffix(with_frame, with_logo)
        upload_path = IMAGES_DIR / f"{Path(filename).stem}{public_id_suffix}.png"
        compose_branded_frame(local_path, upload_path, with_frame=with_frame, with_logo=with_logo)
    else:
        upload_path = local_path
        public_id_suffix = ""
    local_display_url = f"/images/{upload_path.name}"
    if SUPABASE_STORE.enabled:
        SUPABASE_STORE.upload_object("editorial-images", filename, local_path.read_bytes(), "image/png")
        if upload_path.name != filename:
            SUPABASE_STORE.upload_object("editorial-images", upload_path.name, upload_path.read_bytes(), "image/png")

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
                "brandedUrl": upload_result.get("secure_url") if has_brand_treatment else None,
                "withFrame": with_frame,
                "withLogo": with_logo,
            }
        except Exception as exc:
            print("Cloudinary upload error (blog figure):", exc)

    now = now_iso()
    # The local frame already carries the approved logo. Cloudinary is delivery-only,
    # never a dependency for applying brand artwork.
    if cloudinary_data:
        display_url = (cloudinary_data.get("brandedUrl") if has_brand_treatment else cloudinary_data.get("rawUrl")) or local_display_url
    else:
        display_url = local_display_url
    image_obj = {
        "url": f"/images/{filename}",
        "displayUrl": display_url,
        "brandedUrl": (cloudinary_data or {}).get("brandedUrl") or (local_display_url if has_brand_treatment else None),
        "cloudinary": cloudinary_data,
        "prompt": combined_prompt,
        "config": {
            "style": style,
            "direction": direction,
            "composition": composition,
            "size": size,
            "quality": quality,
            "userNotes": user_notes,
            "withFrame": with_frame,
            "withLogo": with_logo,
            "brandTreatment": brand_treatment_label(with_frame, with_logo),
        },
        "generatedAt": now,
        "sizeBytes": generated_image.size_bytes,
        "estimatedCostCents": image_cost_cents,
        "validation": generated_image.validation(),
    }
    with transaction() as fresh:  # re-localiza blog+figura en estado fresco
        fresh_blog = next((b for b in fresh.get("blogs", []) if b.get("id") == blog_id), None)
        if fresh_blog is None:
            raise ApiError("Blog no encontrado", 404)
        fresh_figure = next((f for f in fresh_blog.get("figures", []) if f.get("figure_id") == figure_id), None)
        if fresh_figure is None:
            raise ApiError("Figura no encontrada", 404)
        fresh_figure["image"] = image_obj
        fresh_blog["updatedAt"] = now
        result = {"ok": True, "figure": fresh_figure, "blog": fresh_blog, "state": decorate_state(fresh)}
    if uses_ephemeral_image_work_dir():
        for staged_path in {local_path, upload_path}:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError as exc:
                print(f"No se pudo limpiar la imagen temporal {staged_path.name}: {exc}")
    return result


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
        "store": False,
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


def sync_files_to_openai(file_ids: set[str] | None = None) -> dict:
    """Synchronise every pending file, or an explicitly bounded subset.

    The optional subset lets the production worker handle large source imports
    in safe batches without changing the existing editor action, which sends
    an empty body and still processes the entire library.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise ApiError("Falta OPENAI_API_KEY", 400)
    db = read_db()
    synced = []
    errors = []
    for item in db.get("files", []):
        if file_ids is not None and item.get("id") not in file_ids:
            continue
        # A refreshed manufacturer document keeps one logical source file. Its
        # previous vector-store attachment is removed only when the editor
        # explicitly runs this synchronisation, then the current contents are
        # uploaded in its place.
        if item.get("needsVectorRefresh"):
            delete_remote_file_if_possible(item)
            item["openaiFileId"] = None
            item["vectorStoreFileId"] = None
            item["vectorStoreId"] = db["settings"].get("vectorStoreId", "")
            item["needsVectorRefresh"] = False
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
        try:
            buffer = read_source_file_bytes(item)
        except (OSError, SupabaseStoreError):
            errors.append({"id": item.get("id"), "name": item.get("name"), "error": "Archivo local no encontrado"})
            continue
        try:
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


def read_source_file_bytes(item: dict) -> bytes:
    """Read a knowledge file in local or Supabase Storage mode."""
    location = str(item.get("localPath") or "")
    prefix = "supabase://source-library/"
    if location.startswith(prefix):
        if not SUPABASE_STORE.enabled:
            raise OSError("El almacenamiento gestionado no está configurado")
        data, _headers = SUPABASE_STORE.download_object("source-library", location[len(prefix):])
        return data
    if not location or not Path(location).is_file():
        raise OSError("Archivo no encontrado")
    return Path(location).read_bytes()


def delete_source_file_if_possible(item: dict) -> None:
    location = str(item.get("localPath") or "")
    prefix = "supabase://source-library/"
    if location.startswith(prefix):
        if SUPABASE_STORE.enabled:
            try:
                SUPABASE_STORE.delete_object("source-library", location[len(prefix):])
            except SupabaseStoreError:
                pass
        return
    local_path = Path(location)
    if local_path and is_path_within(local_path, UPLOAD_DIR) and local_path.is_file():
        local_path.unlink()


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
    file_id = uid("file")
    safe_name = sanitize_filename(file_name)
    stored_name = f"{file_id}-{safe_name}"
    if SUPABASE_STORE.enabled:
        object_path = f"sources/{stored_name}"
        SUPABASE_STORE.upload_object("source-library", object_path, buffer, mime_type)
        stored_path_value = f"supabase://source-library/{object_path}"
    else:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stored_path = UPLOAD_DIR / stored_name
        stored_path.write_bytes(buffer)
        stored_path_value = str(stored_path)
    now = now_iso()
    item = {
        "id": file_id,
        "name": safe_name,
        "category": category,
        "source": source,
        "localPath": stored_path_value,
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


class ManufacturerPageParser(HTMLParser):
    """Small dependency-free extractor for the public text of official sites."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        normalized = " ".join(data.split())
        if not normalized:
            return
        if self._in_title:
            self.title_parts.append(normalized)
        self.text_parts.append(normalized)


def _normalise_https_url(value: str) -> str | None:
    parsed = urllib.parse.urlsplit(str(value or "").strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return None
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        return None
    clean = parsed._replace(fragment="")
    return urllib.parse.urlunsplit(clean)


def _same_manufacturer_site(candidate: str, root_url: str) -> bool:
    candidate_url = _normalise_https_url(candidate)
    root = urllib.parse.urlsplit(root_url)
    parsed = urllib.parse.urlsplit(candidate_url or "")
    if not candidate_url or not parsed.hostname or not root.hostname:
        return False
    def without_www(host: str) -> str:
        return host.lower().removeprefix("www.")
    return without_www(parsed.hostname) == without_www(root.hostname)


def _manufacturer_social_link(value: str) -> dict | None:
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host in {"x.com", "twitter.com"}:
        parts = [part for part in parsed.path.split("/") if part]
        handle = parts[0].lstrip("@") if parts else ""
        if handle.lower() in {"home", "search", "share", "intent", "i"}:
            handle = ""
        return {"network": "x", "url": value, "candidateHandle": handle[:30]}
    if host in {"instagram.com"}:
        return {"network": "instagram", "url": value}
    if host in {"linkedin.com", "es.linkedin.com"}:
        return {"network": "linkedin", "url": value}
    return None


def _fetch_manufacturer_page(url: str, root_url: str) -> dict:
    safe_url = _normalise_https_url(url)
    if not safe_url or not _same_manufacturer_site(safe_url, root_url):
        raise ApiError("La URL del fabricante no es una página HTTPS del dominio verificado.", 400)
    request = urllib.request.Request(
        safe_url,
        headers={
            "user-agent": "NexiaGP-Content-Research/1.0 (+https://nexiagp.com)",
            "accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=MANUFACTURER_FETCH_TIMEOUT_SECONDS) as response:
            final_url = _normalise_https_url(response.geturl())
            if not final_url or not _same_manufacturer_site(final_url, root_url):
                raise ApiError("La web redirigió fuera del dominio verificado.", 400)
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ApiError("La URL no devolvió una página HTML pública.", 415)
            raw = response.read(MAX_MANUFACTURER_PAGE_BYTES + 1)
            if len(raw) > MAX_MANUFACTURER_PAGE_BYTES:
                raise ApiError("La página supera el límite seguro de lectura.", 413)
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        raise ApiError(f"La web respondió HTTP {exc.code}.", 502) from exc
    except urllib.error.URLError as exc:
        raise ApiError("No se pudo conectar con la web del fabricante.", 502) from exc
    except TimeoutError as exc:
        raise ApiError("La web del fabricante agotó el tiempo de espera.", 504) from exc

    try:
        document = raw.decode(charset, errors="replace")
    except LookupError:
        document = raw.decode("utf-8", errors="replace")
    parser = ManufacturerPageParser()
    parser.feed(document)
    parser.close()
    text = "\n".join(parser.text_parts)
    text = re.sub(r"(?:\s*\n){3,}", "\n\n", text).strip()
    return {
        "url": final_url,
        "title": " ".join(parser.title_parts).strip()[:500],
        "text": text[:MAX_MANUFACTURER_DOCUMENT_CHARS],
        "links": parser.links,
    }


def _candidate_manufacturer_pages(page: dict, root_url: str) -> list[str]:
    priority = (
        "noticias", "news", "actualidad", "blog", "productos", "products",
        "catalogo", "catalog", "soluciones", "solutions", "empresa", "about",
        "quienes-somos", "sostenibilidad", "innovation",
    )
    candidates: list[str] = []
    seen: set[str] = {page["url"]}
    for href in page.get("links", []):
        candidate = _normalise_https_url(urllib.parse.urljoin(page["url"], href))
        if not candidate or candidate in seen or not _same_manufacturer_site(candidate, root_url):
            continue
        path = urllib.parse.urlsplit(candidate).path.lower()
        if not any(term in path for term in priority):
            continue
        if Path(path).suffix.lower() in {".pdf", ".zip", ".jpg", ".jpeg", ".png", ".webp"}:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates[: MAX_MANUFACTURER_SOURCE_PAGES - 1]


def crawl_manufacturer_website(source: dict) -> dict:
    """Fetch the home page plus a bounded set of relevant official sections."""
    root_url = source.get("website", {}).get("url", "")
    try:
        root_page = _fetch_manufacturer_page(root_url, root_url)
    except ApiError as original_error:
        root_page = None
        for fallback_url in source.get("website", {}).get("fallbackUrls", []):
            try:
                root_page = _fetch_manufacturer_page(fallback_url, root_url)
                break
            except ApiError:
                continue
        if root_page is None:
            raise original_error
    pages = [root_page]
    for candidate in _candidate_manufacturer_pages(root_page, root_url):
        try:
            pages.append(_fetch_manufacturer_page(candidate, root_url))
        except ApiError:
            # A broken section should not discard useful information recovered
            # from the official landing page.
            continue
    socials: list[dict] = []
    seen_social_urls: set[str] = set()
    for page in pages:
        for href in page.get("links", []):
            absolute = _normalise_https_url(urllib.parse.urljoin(page["url"], href))
            social = _manufacturer_social_link(absolute or "")
            if social and social["url"] not in seen_social_urls:
                seen_social_urls.add(social["url"])
                socials.append(social)
    return {"pages": pages, "socials": socials}


def manufacturer_web_document(source: dict, crawl: dict) -> bytes:
    sections = [
        f"# Fuente oficial de fabricante: {source['name']}",
        "",
        f"Sector: {source.get('sector', '')}",
        f"Web oficial: {source.get('website', {}).get('url', '')}",
        f"Actualizada por Nexia GP: {now_iso()}",
        "",
        "Esta fuente contiene texto público extraído de la web oficial. Requiere revisión editorial antes de atribuir afirmaciones, novedades o especificaciones.",
    ]
    for page in crawl["pages"]:
        sections.extend([
            "",
            f"## {page.get('title') or page['url']}",
            f"URL: {page['url']}",
            "",
            page.get("text") or "(Sin texto público extraíble)",
        ])
    return "\n".join(sections)[:MAX_MANUFACTURER_DOCUMENT_CHARS].encode("utf-8")


def _write_registered_source_bytes(item: dict, buffer: bytes, mime_type: str) -> None:
    location = str(item.get("localPath") or "")
    prefix = "supabase://source-library/"
    if location.startswith(prefix):
        if not SUPABASE_STORE.enabled:
            raise OSError("El almacenamiento gestionado no está configurado")
        SUPABASE_STORE.upload_object("source-library", location[len(prefix):], buffer, mime_type)
        return
    path = Path(location)
    if not path or not is_path_within(path, UPLOAD_DIR):
        raise OSError("La fuente existente no pertenece a la biblioteca gestionada")
    path.write_bytes(buffer)


def upsert_manufacturer_document(db: dict, source: dict, *, kind: str, buffer: bytes) -> dict:
    file_source = "manufacturer_web" if kind == "web" else "manufacturer_x"
    existing = next(
        (
            item for item in db.get("files", [])
            if item.get("manufacturerSourceId") == source["id"] and item.get("manufacturerSourceKind") == kind
        ),
        None,
    )
    filename = f"fabricante-{source['id']}-{kind}.md"
    if existing is None:
        existing = register_file(
            db,
            file_name=filename,
            mime_type="text/markdown; charset=utf-8",
            buffer=buffer,
            category="fabricante",
            source=file_source,
            sync_remote=False,
        )
        existing["manufacturerSourceId"] = source["id"]
        existing["manufacturerSourceKind"] = kind
    else:
        _write_registered_source_bytes(existing, buffer, "text/markdown; charset=utf-8")
        existing["name"] = filename
        existing["size"] = len(buffer)
        existing["status"] = "local_only"
        existing["error"] = None
        existing["updatedAt"] = now_iso()
        if existing.get("openaiFileId") or existing.get("vectorStoreFileId"):
            existing["needsVectorRefresh"] = True
    return existing


def _find_manufacturer_source(db: dict, source_id: str) -> dict:
    ensure_manufacturer_sources(db)
    source = next((item for item in db["manufacturerSources"] if item.get("id") == source_id), None)
    if source is None:
        raise ApiError("Fabricante no encontrado", 404)
    return source


def update_manufacturer_source(source_id: str, payload: dict) -> dict:
    with transaction() as db:
        source = _find_manufacturer_source(db, source_id)
        website = source.setdefault("website", {})
        x_source = source.setdefault("social", {}).setdefault("x", {})
        if "websiteEnabled" in payload:
            website["enabled"] = as_bool(payload.get("websiteEnabled"), True)
        if "xEnabled" in payload:
            x_source["enabled"] = as_bool(payload.get("xEnabled"), False)
        if "xHandle" in payload:
            handle = str(payload.get("xHandle") or "").strip().lstrip("@")
            if handle and not re.fullmatch(r"[A-Za-z0-9_]{1,30}", handle):
                raise ApiError("El usuario de X solo puede contener letras, números o guion bajo.", 400)
            x_source["handle"] = handle
            x_source["status"] = "pending" if handle else "needs_handle"
        if x_source.get("enabled") and not os.getenv("X_API_BEARER_TOKEN"):
            x_source["status"] = "needs_credentials"
        state = decorate_state(db)
    return {"ok": True, "source": source, "state": state}


def _x_api_json(url: str, bearer_token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "authorization": f"Bearer {bearer_token}",
            "accept": "application/json",
            "user-agent": "NexiaGP-Content-Research/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=MANUFACTURER_FETCH_TIMEOUT_SECONDS) as response:
            return json.loads(response.read(MAX_MANUFACTURER_PAGE_BYTES).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ApiError(f"X API respondió HTTP {exc.code}.", 502) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ApiError("No se pudo conectar con X API.", 502) from exc


def fetch_x_posts(x_source: dict) -> list[dict]:
    token = os.getenv("X_API_BEARER_TOKEN")
    if not token:
        raise ApiError("Falta X_API_BEARER_TOKEN para consultar X.", 400)
    handle = str(x_source.get("handle") or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,30}", handle):
        raise ApiError("Confirma un usuario válido de X antes de activar la consulta.", 400)
    user_data = _x_api_json(
        f"https://api.x.com/2/users/by/username/{urllib.parse.quote(handle)}",
        token,
    )
    user_id = (user_data.get("data") or {}).get("id")
    if not user_id:
        raise ApiError("X no devolvió un perfil para el usuario configurado.", 404)
    query = urllib.parse.urlencode({
        "max_results": 10,
        "exclude": "retweets,replies",
        "tweet.fields": "created_at,entities,public_metrics",
    })
    response = _x_api_json(f"https://api.x.com/2/users/{urllib.parse.quote(user_id)}/tweets?{query}", token)
    return [item for item in response.get("data", []) if isinstance(item, dict)]


def manufacturer_x_document(source: dict, handle: str, posts: list[dict]) -> bytes:
    lines = [
        f"# Publicaciones oficiales de X: {source['name']}",
        "",
        f"Cuenta confirmada: @{handle}",
        f"Consulta realizada por Nexia GP: {now_iso()}",
        "",
        "Contenido público recuperado mediante X API oficial. Requiere revisión editorial antes de reutilizarlo.",
    ]
    for post in posts:
        lines.extend([
            "",
            f"## Publicación {post.get('id', '')}",
            f"Fecha: {post.get('created_at', '')}",
            f"Enlace: https://x.com/{handle}/status/{post.get('id', '')}",
            "",
            str(post.get("text") or ""),
        ])
    return "\n".join(lines).encode("utf-8")


def sync_manufacturer_source(source_id: str, *, include_x: bool, include_web: bool = True) -> dict:
    """Refresh one official web source and, only when configured, its X feed."""
    snapshot = read_db()
    source = _find_manufacturer_source(snapshot, source_id)
    website_enabled = as_bool(source.get("website", {}).get("enabled"), True)
    x_source = source.get("social", {}).get("x", {})
    crawl: dict | None = None
    web_error: str | None = None
    if include_web and website_enabled:
        try:
            crawl = crawl_manufacturer_website(source)
        except ApiError as exc:
            web_error = exc.message

    x_posts: list[dict] | None = None
    x_error: str | None = None
    if include_x and as_bool(x_source.get("enabled"), False):
        try:
            x_posts = fetch_x_posts(x_source)
        except ApiError as exc:
            x_error = exc.message

    with transaction() as db:
        fresh_source = _find_manufacturer_source(db, source_id)
        fresh_website = fresh_source.setdefault("website", {})
        if crawl is not None:
            document = upsert_manufacturer_document(
                db, fresh_source, kind="web", buffer=manufacturer_web_document(fresh_source, crawl)
            )
            fresh_website.update({
                "lastStatus": "updated",
                "lastSyncAt": now_iso(),
                "lastError": None,
                "pages": len(crawl["pages"]),
                "documentId": document["id"],
            })
            fresh_source["discoveredSocials"] = crawl["socials"]
            candidate = next(
                (item.get("candidateHandle") for item in crawl["socials"] if item.get("network") == "x" and item.get("candidateHandle")),
                "",
            )
            fresh_x = fresh_source.setdefault("social", {}).setdefault("x", {})
            if candidate and not fresh_x.get("handle"):
                fresh_x["candidateHandle"] = candidate
        elif include_web and website_enabled:
            fresh_website.update({"lastStatus": "error", "lastSyncAt": now_iso(), "lastError": (web_error or "No se pudo actualizar la web.")[:300]})

        fresh_x = fresh_source.setdefault("social", {}).setdefault("x", {})
        x_result = {"requested": include_x, "updated": False, "newPosts": 0}
        if include_x and not fresh_x.get("enabled"):
            x_result["reason"] = "X permanece desactivado para este fabricante."
        elif include_x and x_posts is not None:
            seen = {str(value) for value in fresh_x.get("seenPostIds", [])}
            new_posts = [post for post in x_posts if str(post.get("id")) not in seen]
            if new_posts:
                upsert_manufacturer_document(
                    db,
                    fresh_source,
                    kind="x",
                    buffer=manufacturer_x_document(fresh_source, str(fresh_x.get("handle") or ""), new_posts),
                )
            fresh_x.update({
                "status": "updated",
                "lastSyncAt": now_iso(),
                "lastError": None,
                "seenPostIds": ([str(post.get("id")) for post in x_posts] + list(seen))[:100],
            })
            x_result.update({"updated": True, "newPosts": len(new_posts)})
        elif include_x and fresh_x.get("enabled"):
            fresh_x.update({
                "status": "error" if x_error else "needs_credentials",
                "lastSyncAt": now_iso(),
                "lastError": (x_error or "Falta configurar X_API_BEARER_TOKEN.")[:300],
            })
            x_result["reason"] = fresh_x["lastError"]
        state = decorate_state(db)
    return {"ok": True, "source": fresh_source, "website": {"updated": crawl is not None, "error": web_error}, "x": x_result, "state": state}


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


def next_scheduled_theme(db: dict) -> tuple[dict | None, int]:
    """Choose one active theme in stable round-robin order.

    A single post per run keeps a three-day cadence genuinely varied instead
    of recreating the same first few topics as a batch. The cursor is advanced
    after every attempted automatic/manual run, including an error, so one
    problematic topic cannot stall the editorial calendar.
    """
    active_themes = [theme for theme in db.get("themes", []) if theme.get("active", True)]
    if not active_themes:
        return None, 0
    try:
        cursor = max(0, int(db.get("settings", {}).get("schedulerThemeCursor") or 0))
    except (TypeError, ValueError):
        cursor = 0
    index = cursor % len(active_themes)
    return active_themes[index], (index + 1) % len(active_themes)


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

    selected_theme, next_theme_cursor = next_scheduled_theme(db)
    if selected_theme is None:
        return {
            "ok": True,
            "skipped": True,
            "reason": "No hay temáticas activas para alternar",
            "state": decorate_state(db),
        }
    post_type_id = db["settings"].get("defaultPostTypeId") or db["postTypes"][0]["id"]
    generated = []
    errors = []
    pipeline = EditorialPipeline(model=db.get("settings", {}).get("model"))
    try:
        request = {
            "canal": "linkedin",
            "tipo_post": selected_theme.get("id") if selected_theme.get("id") in POST_TYPES and selected_theme.get("id") != "auto" else post_type_id,
            "objetivo": "autoridad",
            "audiencia_principal": "mixta",
            "sector": ", ".join(selected_theme.get("pillars", [])[:2]),
            "marca_o_entidad": "Nexia GP",
            "tema_libre": selected_theme.get("description", ""),
            "cta_preferida": "comentario",
            "usar_enlace": False,
            "nivel_promocional": "bajo",
            "necesita_adaptacion_multicanal": True,
            "notas_humanas": "Generación automática por cadencia editorial y rotación de temáticas. Evitar repetir ideas usadas.",
        }
        result = pipeline.run(request, db)
        post = result["post"]
        # The scheduler never spends image-generation credits by itself, but
        # its draft declares the approved default for the first visual an
        # editor requests: Nexia frame plus logo.
        post["imageDefaults"] = {"withFrame": True, "withLogo": True}
        if db["settings"].get("publishMode") in {"ready", "auto"} and not has_unacknowledged_quality_gate(post):
            post["status"] = "review"
            post["schedulerReviewReason"] = "Pendiente de aprobación editorial y fecha programada."
        elif db["settings"].get("publishMode") in {"ready", "auto"}:
            post["schedulerReviewReason"] = "La puerta de calidad mantuvo el post en borrador."
        generated.append(post)
    except Exception as exc:
        errors.append({"themeId": selected_theme["id"], "error": str(exc)})

    with transaction() as fresh:  # persistencia atomica de toda la tanda del scheduler
        for post in generated:
            fresh.setdefault("posts", []).insert(0, post)
            register_editorial_idea(fresh, post)
            record_usage(fresh, post.get("usage"))
        run_at = now_iso()
        fresh["settings"]["lastSchedulerRun"] = run_at
        fresh["settings"]["schedulerThemeCursor"] = next_theme_cursor
        fresh["schedulerLog"] = ([
            {
                "id": uid("run"),
                "createdAt": run_at,
                "source": source,
                "generated": len(generated),
                "errors": errors,
                "themeId": selected_theme["id"],
            }
        ] + fresh.get("schedulerLog", []))[:50]
        state = decorate_state(fresh)
    return {"ok": True, "skipped": False, "generated": generated, "errors": errors, "state": state}


def scheduler_loop() -> None:
    while True:
        time.sleep(3600)
        try:
            run_scheduler(force=False, source="timer")
        except Exception as exc:
            print("Scheduler error:", exc)


def sync_enabled_manufacturer_x_sources() -> dict:
    """Daily, opt-in polling for confirmed X accounts only.

    The Vercel cron is short lived, so it polls recent posts instead of keeping
    a stream connection open. No network call is made until an editor enables a
    source, confirms its handle, and a private API token is configured.
    """
    if not os.getenv("X_API_BEARER_TOKEN"):
        return {"checked": 0, "updated": 0, "skipped": "X_API_BEARER_TOKEN no configurado"}
    snapshot = read_db()
    sources = ensure_manufacturer_sources(snapshot)
    source_ids = [
        source["id"]
        for source in sources
        if as_bool(source.get("social", {}).get("x", {}).get("enabled"), False)
        and str(source.get("social", {}).get("x", {}).get("handle") or "").strip()
    ][:10]
    updated = 0
    errors: list[dict] = []
    for source_id in source_ids:
        try:
            result = sync_manufacturer_source(source_id, include_x=True, include_web=False)
            if result.get("x", {}).get("updated"):
                updated += 1
        except Exception as exc:
            errors.append({"sourceId": source_id, "error": str(exc)[:300]})
    return {"checked": len(source_ids), "updated": updated, "errors": errors}


def run_daily_maintenance() -> dict:
    """Run the work that Vercel Hobby can guarantee: one daily invocation.

    Manual jobs are attempted immediately by their request. This daily route is
    the recovery path for an invocation interrupted before completion and also
    replaces the local scheduler thread once the app runs on Vercel.
    """
    scheduler = run_scheduler(force=False, source="vercel-daily")
    manufacturer_x = sync_enabled_manufacturer_x_sources()
    recovered_job = None
    if scheduler.get("skipped"):
        recovered_job = process_one_remote_generation_job()
    return {"scheduler": scheduler, "manufacturerX": manufacturer_x, "recoveredJob": recovered_job}


def publish_post(db: dict, post: dict, *, require_webhook: bool = False) -> None:
    refresh_post_quality_gate(post)
    if has_unacknowledged_quality_gate(post):
        raise ApiError(
            "El post requiere revisión humana registrada antes de publicarse.",
            409,
            "quality_review_required",
        )
    if post.get("status") != "scheduled" or not post.get("editorialApprovedAt"):
        raise ApiError("Aprueba el post y prográmalo antes de publicarlo.", 409, "editorial_schedule_required")
    try:
        scheduled_at = datetime.fromisoformat(str(post.get("scheduledFor") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError("La fecha programada no es válida.", 409, "editorial_schedule_required") from exc
    if scheduled_at.tzinfo is None or scheduled_at > datetime.now(timezone.utc):
        raise ApiError("El post todavía no ha llegado a su fecha programada.", 409, "scheduled_time_pending")
    webhook = os.getenv("SOCIAL_WEBHOOK_URL")
    if not webhook:
        if require_webhook:
            raise ApiError("La publicación automática no está conectada. El post sigue listo para revisión.", 409)
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


def apply_post_edits(post: dict, body: dict) -> None:
    """Aplica ediciones inline a un post manteniendo sincronizadas las tres capas:
    el campo plano que lee la UI, generation.copy y validation."""
    gen_copy = post.setdefault("generation", {}).setdefault("copy", {})
    validation = post.get("validation") if isinstance(post.get("validation"), dict) else None
    refresh_post_quality_gate(post)

    if as_bool(body.get("reviewAcknowledged"), False):
        acknowledge_quality_gate(post)

    if "status" in body:
        requested_status = normalize_status(body.get("status") or post.get("status"))
        if requested_status in {"published", "scheduled"}:
            raise ApiError("Usa la programación y la publicación verificadas para cambiar este estado.", 409)
        if requested_status in {"ready", "scheduled"} and has_unacknowledged_quality_gate(post):
            raise ApiError(
                "El post requiere revisión humana registrada antes de prepararlo para calendario.",
                409,
                "quality_review_required",
            )
        post["status"] = requested_status
        post.pop("scheduledFor", None)
        if requested_status == "ready":
            post["editorialApprovedAt"] = now_iso()
        else:
            post.pop("editorialApprovedAt", None)

    if "scheduledFor" in body:
        if post.get("status") not in {"ready", "scheduled"} or not post.get("editorialApprovedAt"):
            raise ApiError("Aprueba el post antes de asignarle fecha.", 409, "editorial_approval_required")
        if has_unacknowledged_quality_gate(post):
            raise ApiError(
                "El post requiere revisión humana registrada antes de programarlo.",
                409,
                "quality_review_required",
            )
        raw_date = body.get("scheduledFor")
        if not isinstance(raw_date, str) or not raw_date.strip():
            raise ApiError("Indica una fecha válida para planificar el post", 400)
        try:
            planned_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ApiError("La fecha de planificación no es válida", 400) from exc
        if planned_at.tzinfo is None:
            planned_at = planned_at.replace(tzinfo=timezone.utc)
        if planned_at <= datetime.now(timezone.utc):
            raise ApiError("Elige una fecha futura para programar el post.", 400, "future_date_required")
        post["scheduledFor"] = planned_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        post["status"] = "scheduled"

    if isinstance(body.get("copy"), str):
        text = body["copy"].strip()
        post["copy"] = text
        gen_copy["final_post"] = text
        if validation is not None:
            validation["final_post"] = text

    if isinstance(body.get("cta"), str):
        cta = body["cta"].strip()
        post["cta"] = cta
        gen_copy["cta"] = cta
        if validation is not None:
            validation["cta"] = cta

    if "hashtags" in body:
        raw = body["hashtags"]
        if isinstance(raw, str):
            raw = re.split(r"[\s,]+", raw)
        tags = normalize_hashtags(raw if isinstance(raw, list) else [])
        post["hashtags"] = tags
        gen_copy["hashtags"] = tags
        if validation is not None:
            validation["hashtags"] = tags

    if isinstance(body.get("title"), str):
        post["title"] = body["title"].strip()

    if any(key in body for key in ("copy", "cta", "hashtags", "title")):
        post["edited"] = True
        if post.get("editorialApprovedAt") or post.get("scheduledFor"):
            post.pop("editorialApprovedAt", None)
            post.pop("scheduledFor", None)
            post["status"] = "review"
        gate = post.get("qualityGate")
        if isinstance(gate, dict) and gate.get("blockers"):
            gate.pop("reviewAcknowledgedAt", None)
            gate.pop("reviewAcknowledged", None)
            gate["can_mark_ready"] = False
    if post.get("status") in {"ready", "scheduled"} and has_unacknowledged_quality_gate(post):
        raise ApiError(
            "Los cambios editoriales requieren una nueva revisión humana antes de preparar el post.",
            409,
            "quality_review_required",
        )


def sanitize_post(post: dict) -> dict:
    safe = json.loads(json.dumps(post, ensure_ascii=False))
    refresh_post_quality_gate(safe)
    if isinstance(safe.get("image"), dict):
        _ensure_image_variant_id(safe["image"])
    variants = post_image_variants(safe)
    if variants:
        safe["imageVariants"] = variants
    safe.pop("imageLocalPath", None)
    return safe


def refresh_post_quality_gate(post: dict) -> dict:
    validation = post.get("validation")
    if not isinstance(validation, dict):
        validation = {}
        post["validation"] = validation
    quality_gate = post_quality_gate(
        post.get("request") or {},
        post.get("brief") or {},
        post.get("retrieval") or {},
        validation,
    )
    existing = post.get("qualityGate")
    if isinstance(existing, dict) and existing.get("reviewAcknowledgedAt"):
        quality_gate["reviewAcknowledgedAt"] = existing["reviewAcknowledgedAt"]
        quality_gate["reviewAcknowledged"] = True
        quality_gate["can_mark_ready"] = True
    post["qualityGate"] = quality_gate
    return quality_gate


def sanitize_blog_for_client(blog: dict) -> dict:
    """Return a safe, quality-annotated view without mutating legacy drafts."""
    safe = json.loads(json.dumps(blog, ensure_ascii=False))
    try:
        refresh_blog_quality_gate(safe)
    except Exception:
        article = safe.get("article")
        if isinstance(article, dict):
            article["article_html"] = sanitize_article_html(article.get("article_html"))
            if isinstance(article.get("article_html_override"), str):
                article["article_html_override"] = sanitize_article_html(article["article_html_override"])
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
    if blog.get("defaultLength") not in BLOG_LENGTH_TARGETS:
        blog["defaultLength"] = BLOG_SETTINGS_DEFAULTS["defaultLength"]
    if blog.get("defaultFramework") not in BLOG_FRAMEWORKS:
        blog["defaultFramework"] = BLOG_SETTINGS_DEFAULTS["defaultFramework"]
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
        "scheduled": sum(1 for post in posts if post.get("status") == "scheduled"),
        "published": sum(1 for post in posts if post.get("status") == "published"),
        "files": len(files),
        "ideas": sum(len(theme.get("usedIdeas", [])) for theme in db.get("themes", [])),
    }
    blogs = [sanitize_blog_for_client(item) for item in db.get("blogs", [])]
    counts["blogs"] = len(blogs)
    counts["blogsDraft"] = sum(1 for b in blogs if b.get("status") == "draft")
    counts["blogsReady"] = sum(1 for b in blogs if b.get("status") == "ready")
    counts["blogsScheduled"] = sum(1 for b in blogs if b.get("status") == "scheduled")
    counts["blogsPublished"] = sum(1 for b in blogs if b.get("status") == "published")
    settings = dict(db.get("settings", {}))
    settings["blog"] = normalize_blog_settings(dict(settings.get("blog") or {}))
    next_theme, _next_cursor = next_scheduled_theme(db)
    settings["schedulerNextThemeId"] = next_theme.get("id") if next_theme else None
    settings["schedulerNextThemeTitle"] = next_theme.get("title") if next_theme else None
    manufacturer_sources = json.loads(json.dumps(ensure_manufacturer_sources(db), ensure_ascii=False))
    for source in manufacturer_sources:
        x_source = source.get("social", {}).get("x", {})
        # The token itself never leaves the server; the UI only needs to know
        # whether the official X API connection can be completed.
        x_source["credentialsConfigured"] = bool(os.getenv("X_API_BEARER_TOKEN"))
        x_source.pop("seenPostIds", None)
    return {
        "ok": True,
        "hasOpenAIKey": bool(os.getenv("OPENAI_API_KEY")),
        "hasSocialWebhook": bool(os.getenv("SOCIAL_WEBHOOK_URL")),
        "wordpress": wordpress_public_config(),
        "client": db.get("client", {}),
        "settings": settings,
        "themes": db.get("themes", []),
        "postTypes": db.get("postTypes", []),
        "files": files,
        "manufacturerSources": manufacturer_sources,
        "posts": posts,
        "blogs": blogs,
        "schedulerLog": db.get("schedulerLog", []),
        "counts": counts,
        "usageStats": db.get("usageStats", {"generations": 0, "calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}),
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
            "visual": public_visual_options(),
            "promotionalLevels": {
                "bajo": "Bajo",
                "medio": "Medio",
            },
        },
    }


def read_db() -> dict:
    if SUPABASE_STORE.enabled:
        remote = SUPABASE_STORE.read_state()
        # Pipelines mutate snapshots freely. Return an isolated object and retain
        # the version only locally for the compare-and-swap write.
        db = json.loads(json.dumps(remote.state, ensure_ascii=False))
        db[STATE_VERSION_KEY] = remote.version
        return db
    with DB_LOCK:
        return json.loads(DB_PATH.read_text(encoding="utf-8"))


def write_db(db: dict) -> None:
    if SUPABASE_STORE.enabled:
        version = int(db.pop(STATE_VERSION_KEY, 0) or 0)
        if not version:
            raise SupabaseStoreError("No se puede guardar estado remoto sin versión de control.")
        try:
            new_version = SUPABASE_STORE.replace_state(db, version)
        except SupabaseStoreError as exc:
            if "40001" in str(exc) or "version conflict" in str(exc):
                raise ApiError("El contenido cambió en otra sesión. Recarga y repite la operación.", 409, "state_conflict") from exc
            raise
        db[STATE_VERSION_KEY] = new_version
        return
    with DB_LOCK:
        temp_path = DB_PATH.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(DB_PATH)


@contextmanager
def transaction():
    """Read-modify-write atomico de db.json bajo un unico lock.

    Mantiene el lock durante toda la operacion (leer -> mutar -> escribir), de modo
    que dos peticiones concurrentes no se pisen ('lost update'). Para los handlers
    largos (generacion con OpenAI) el patron es: hacer el trabajo lento sobre un
    snapshot read_db() y persistir SOLO el delta dentro de un transaction() corto.
    """
    if SUPABASE_STORE.enabled:
        db = read_db()
        yield db
        write_db(db)
        return
    with DB_LOCK:
        db = json.loads(DB_PATH.read_text(encoding="utf-8"))
        yield db
        temp_path = DB_PATH.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(DB_PATH)


prompt_service.configure_db_reader(read_db)


def record_usage(db: dict, usage: dict | None) -> None:
    """Acumula el consumo de tokens de una generacion en db['usageStats'] (best-effort)."""
    if not isinstance(usage, dict):
        return
    stats = db.setdefault(
        "usageStats",
        {"generations": 0, "calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    )
    stats["generations"] = int(stats.get("generations", 0) or 0) + 1
    stats["calls"] = int(stats.get("calls", 0) or 0) + int(usage.get("calls") or 0)
    stats["input_tokens"] = int(stats.get("input_tokens", 0) or 0) + int(usage.get("input_tokens") or 0)
    stats["output_tokens"] = int(stats.get("output_tokens", 0) or 0) + int(usage.get("output_tokens") or 0)
    stats["total_tokens"] = int(stats.get("total_tokens", 0) or 0) + int(usage.get("total_tokens") or 0)
    stats["updatedAt"] = now_iso()


def normalize_theme(body: dict, previous: dict | None = None) -> dict:
    previous = previous or {}
    title = str(body.get("title") or previous.get("title") or "Nueva tematica").strip()
    return {
        "id": previous.get("id") or slugify(body.get("id") or title),
        "title": title,
        "audience": str(body.get("audience") or previous.get("audience") or "Audiencia B2B").strip(),
        "description": str(body.get("description") or previous.get("description") or "").strip(),
        "pillars": split_list(body.get("pillars", previous.get("pillars", []))),
        "active": as_bool(body["active"], True) if "active" in body else previous.get("active", True),
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
    if status in {"draft", "review", "ready", "published", "scheduled"}:
        return status
    if status == "auto":
        return "ready"
    return "draft"


def status_from_mode(mode: str | None, fallback: str) -> str:
    if mode in {"ready", "auto"}:
        return "ready"
    return normalize_status(fallback)


def list_local_documents() -> list[dict]:
    roots = [
        ROOT / "Documentación Nexia",
        ROOT / "LinkedIn B2B Copywriting 2026.docx",
        UPLOAD_DIR / "kb-externa",
    ]
    docs = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            docs.append({"path": root, "name": root.name, "category": "copywriting"})
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}:
                parts_upper = [part.upper() for part in path.parts]
                if "KB-EXTERNA" in parts_upper:
                    # Categoria por subcarpeta sectorial: "A-economia" -> "kb-economia"
                    sector = re.sub(r"^[A-Za-z]-", "", path.parent.name) or "externa"
                    category = f"kb-{sector}"
                elif "WEB" in parts_upper:
                    category = "web"
                else:
                    category = "brand"
                docs.append({"path": path, "name": path.name, "category": category})
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


def as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "si", "sí", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    if value is None:
        return default
    return bool(value)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_files() -> None:
    if SUPABASE_STORE.enabled:
        # Production state is seeded by the checked migration importer. Do not
        # create an empty cloud state implicitly, which could mask a bad deploy.
        read_db()
        return
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
