"""WordPress REST integration for reviewed Nexia GP blog articles.

The service deliberately knows nothing about the application database or
Supabase.  The HTTP layer supplies durable image bytes and persists the sync
record returned here.  This keeps credentials server-only and makes the core
transformation fully testable offline.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps, UnidentifiedImageError


PREFERRED_IMAGE_BYTES = 200 * 1024
MAX_WORDPRESS_IMAGE_BYTES = 1 * 1024 * 1024
_JPEG_QUALITIES = (82, 76, 70, 64, 58, 52, 46)
_IMAGE_WIDTHS = (1600, 1400, 1200, 1024, 900, 768)
_FIGURE_RE = re.compile(r"<figure\b(?P<attrs>[^>]*)>(?P<body>.*?)</figure\s*>", re.IGNORECASE | re.DOTALL)
_FIGURE_ID_RE = re.compile(r"\bdata-figure-id\s*=\s*(['\"])(?P<id>[^'\"]+)\1", re.IGNORECASE)
_BLOG_HEADER_RE = re.compile(r"<header\b[^>]*\bclass\s*=\s*(['\"])[^'\"]*\bblog-header\b[^'\"]*\1[^>]*>.*?</header\s*>", re.IGNORECASE | re.DOTALL)
_ARTICLE_OPEN_RE = re.compile(r"^\s*<article\b[^>]*\bblog-post\b[^>]*>", re.IGNORECASE)
_ARTICLE_CLOSE_RE = re.compile(r"</article\s*>\s*$", re.IGNORECASE)
_FIRST_H1_RE = re.compile(r"<h1\b[^>]*>.*?</h1\s*>", re.IGNORECASE | re.DOTALL)
_FILENAME_RE = re.compile(r"[^a-z0-9_-]+", re.IGNORECASE)
_RANK_MATH_META_FIELDS = (
    "rank_math_title",
    "rank_math_description",
    "rank_math_focus_keyword",
)


class WordPressError(RuntimeError):
    """A non-secret error that can be shown to the editor."""


@dataclass(frozen=True)
class PreparedImage:
    content: bytes
    filename: str
    content_type: str
    width: int
    height: int


def _safe_stem(value: str, fallback: str = "imagen-nexia") -> str:
    candidate = _FILENAME_RE.sub("-", value or "").strip("-").lower()
    return candidate[:90] or fallback


def _resized(image: Image.Image, max_width: int) -> Image.Image:
    if image.width <= max_width:
        return image
    ratio = max_width / image.width
    return image.resize((max_width, max(1, round(image.height * ratio))), Image.Resampling.LANCZOS)


def prepare_wordpress_image(source: bytes, filename: str) -> PreparedImage:
    """Convert an editorial image into a web-safe JPEG near the agreed target.

    WordPress receives an optimized derivative, while the original stays in the
    editorial library.  A detailed scene can need more than 200 KB; it is still
    accepted up to the meeting's hard cap of 1 MB.
    """
    try:
        with Image.open(BytesIO(source)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise WordPressError("Una imagen del blog no es un archivo válido para WordPress.") from exc

    best: tuple[bytes, Image.Image] | None = None
    for max_width in _IMAGE_WIDTHS:
        scaled = _resized(image, max_width)
        for quality in _JPEG_QUALITIES:
            output = BytesIO()
            scaled.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
            encoded = output.getvalue()
            if best is None or len(encoded) < len(best[0]):
                best = (encoded, scaled)
            if len(encoded) <= PREFERRED_IMAGE_BYTES:
                stem = _safe_stem(Path(filename).stem)
                return PreparedImage(encoded, f"{stem}.jpg", "image/jpeg", scaled.width, scaled.height)

    if best is None or len(best[0]) > MAX_WORDPRESS_IMAGE_BYTES:
        raise WordPressError("No se pudo optimizar una imagen por debajo del máximo de 1 MB.")
    stem = _safe_stem(Path(filename).stem)
    return PreparedImage(best[0], f"{stem}.jpg", "image/jpeg", best[1].width, best[1].height)


def clean_wordpress_article(article_html: str, media_by_figure: dict[str, dict]) -> str:
    """Replace Nexia figure placeholders with WordPress media and remove duplicate H1.

    WordPress' existing template supplies the article title.  Removing the
    editorial H1/header prevents two page titles while retaining the rest of
    the semantic article, CTA, links and captions.
    """
    content = str(article_html or "")
    content = _BLOG_HEADER_RE.sub("", content)
    content = _ARTICLE_OPEN_RE.sub("", content)
    content = _ARTICLE_CLOSE_RE.sub("", content)
    content = _FIRST_H1_RE.sub("", content, count=1)

    def replace_figure(match: re.Match[str]) -> str:
        id_match = _FIGURE_ID_RE.search(match.group("attrs"))
        figure_id = id_match.group("id") if id_match else ""
        media = media_by_figure.get(figure_id)
        if not media:
            return match.group(0)
        source_url = html.escape(str(media.get("sourceUrl") or ""), quote=True)
        media_id = int(media.get("mediaId") or 0)
        alt = html.escape(str(media.get("alt") or ""), quote=True)
        caption = html.escape(str(media.get("caption") or ""))
        class_name = f"wp-image-{media_id}" if media_id else ""
        caption_html = f'<figcaption class="wp-element-caption">{caption}</figcaption>' if caption else ""
        return (
            '<figure class="wp-block-image size-large">'
            f'<img class="{class_name}" src="{source_url}" alt="{alt}" loading="lazy" decoding="async">'
            f"{caption_html}</figure>"
        )

    return _FIGURE_RE.sub(replace_figure, content).strip()


def wordpress_content_hash(title: str, slug: str, content: str, excerpt: str) -> str:
    payload = "\n".join((title or "", slug or "", content or "", excerpt or ""))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class WordPressService:
    """Small, dependency-free client for the WordPress REST posts/media APIs."""

    def __init__(self, *, base_url: str | None = None, username: str | None = None, application_password: str | None = None) -> None:
        self.base_url = (base_url if base_url is not None else os.getenv("WORDPRESS_BASE_URL", "")).strip().rstrip("/")
        self.username = (username if username is not None else os.getenv("WORDPRESS_USERNAME", "")).strip()
        self.application_password = application_password if application_password is not None else os.getenv("WORDPRESS_APPLICATION_PASSWORD", "")

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.username and self.application_password)

    @property
    def api_root(self) -> str:
        return f"{self.base_url}/wp-json/wp/v2"

    def public_config(self) -> dict:
        return {"configured": self.enabled, "baseUrl": self.base_url or None}

    def _authorization(self) -> str:
        if not self.enabled:
            raise WordPressError("La conexión con WordPress no está configurada en el servidor.")
        token = base64.b64encode(f"{self.username}:{self.application_password}".encode("utf-8")).decode("ascii")
        return f"Basic {token}"

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict | list:
        body = data
        request_headers = {"authorization": self._authorization(), "accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            request_headers["content-type"] = "application/json; charset=utf-8"
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            f"{self.api_root}/{path.lstrip('/')}", data=body, headers=request_headers, method=method
        )
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=75) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise WordPressError("WordPress rechazó la autenticación. Revisa el usuario técnico y la contraseña de aplicación.") from exc
            raise WordPressError(f"WordPress no aceptó la operación (HTTP {exc.code}).") from exc
        except urllib.error.URLError as exc:
            raise WordPressError("No se pudo conectar con WordPress.") from exc
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError as exc:
            raise WordPressError("WordPress devolvió una respuesta no válida.") from exc
        if not isinstance(parsed, (dict, list)):
            raise WordPressError("WordPress devolvió un formato inesperado.")
        return parsed

    def validate(self) -> dict:
        response = self._request("users/me?context=edit&_fields=id,slug,roles")
        if not isinstance(response, dict) or not response.get("id"):
            raise WordPressError("WordPress no confirmó la identidad del usuario técnico.")
        return {"ok": True, "userId": int(response["id"]), "roles": list(response.get("roles") or [])}

    def upload_media(self, image: PreparedImage, *, alt: str, caption: str) -> dict:
        uploaded = self._request(
            "media",
            method="POST",
            data=image.content,
            headers={
                "content-type": image.content_type,
                "content-disposition": f'attachment; filename="{image.filename}"',
            },
        )
        if not isinstance(uploaded, dict) or not uploaded.get("id") or not uploaded.get("source_url"):
            raise WordPressError("WordPress no confirmó la subida de una imagen.")
        media_id = int(uploaded["id"])
        updated = self._request(
            f"media/{media_id}",
            method="POST",
            payload={"alt_text": alt[:240], "caption": caption[:500]},
        )
        response = updated if isinstance(updated, dict) else uploaded
        return {
            "mediaId": media_id,
            "sourceUrl": str(response.get("source_url") or uploaded["source_url"]),
            "bytes": len(image.content),
            "filename": image.filename,
            "width": image.width,
            "height": image.height,
        }

    def _find_owned_post_by_slug(self, slug: str, marker: str) -> dict | None:
        encoded_slug = urllib.parse.quote(slug, safe="")
        response = self._request(f"posts?slug={encoded_slug}&status=any&context=edit&_fields=id,status,content")
        if not isinstance(response, list):
            return None
        for item in response:
            content = item.get("content") if isinstance(item, dict) else {}
            raw_html = content.get("raw", "") if isinstance(content, dict) else ""
            if marker in str(raw_html):
                return item
        return None

    @staticmethod
    def _rank_math_meta_fields_from_options(response: dict | list) -> set[str]:
        """Find Rank Math fields registered in the posts REST schema.

        WordPress only accepts post meta through the REST API if the plugin has
        registered it with ``show_in_rest``.  The exact OPTIONS envelope varies
        between WordPress versions, so inspect both common shapes instead of
        assuming the plugin is writable just because it is installed.
        """
        if not isinstance(response, dict):
            return set()

        candidates: list[dict] = []
        schema = response.get("schema")
        if isinstance(schema, dict):
            candidates.append(schema)
        endpoints = response.get("endpoints")
        if isinstance(endpoints, list):
            for endpoint in endpoints:
                if isinstance(endpoint, dict):
                    args = endpoint.get("args")
                    meta = args.get("meta") if isinstance(args, dict) else None
                    if isinstance(meta, dict):
                        candidates.append({"properties": {"meta": meta}})
        routes = response.get("routes")
        if isinstance(routes, dict):
            for route in routes.values():
                if isinstance(route, dict):
                    candidates.append(route)
                    route_endpoints = route.get("endpoints")
                    if isinstance(route_endpoints, list):
                        candidates.extend(item for item in route_endpoints if isinstance(item, dict))

        available: set[str] = set()
        for candidate in candidates:
            args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
            properties = candidate.get("properties") if isinstance(candidate.get("properties"), dict) else {}
            meta = properties.get("meta") or args.get("meta")
            if not isinstance(meta, dict):
                continue
            meta_properties = meta.get("properties")
            if not isinstance(meta_properties, dict):
                schema = meta.get("schema")
                meta_properties = schema.get("properties") if isinstance(schema, dict) else {}
            if isinstance(meta_properties, dict):
                available.update(field for field in _RANK_MATH_META_FIELDS if field in meta_properties)
        return available

    def rank_math_meta_fields(self) -> set[str]:
        """Return the safe, REST-writable Rank Math fields for this site.

        Rank Math is an optional SEO layer.  A failed capability check must not
        prevent editors from creating a WordPress draft, so it falls back to an
        explicit manual review state.
        """
        try:
            response = self._request("posts?context=edit", method="OPTIONS")
        except WordPressError:
            return set()
        return self._rank_math_meta_fields_from_options(response)

    @staticmethod
    def rank_math_meta_values(
        available_fields: set[str],
        *,
        meta_title: str,
        meta_description: str,
        focus_keyword: str,
    ) -> dict[str, str]:
        source = {
            "rank_math_title": meta_title.strip()[:255],
            "rank_math_description": meta_description.strip()[:500],
            "rank_math_focus_keyword": focus_keyword.strip()[:255],
        }
        return {
            field: value
            for field, value in source.items()
            if field in available_fields and value
        }

    def upsert_draft(
        self,
        *,
        blog_id: str,
        title: str,
        slug: str,
        content: str,
        excerpt: str,
        featured_media_id: int | None,
        existing: dict | None = None,
        category_id: int | None = None,
        author_id: int | None = None,
        rank_math_meta: dict[str, str] | None = None,
    ) -> dict:
        if not title.strip() or not slug.strip() or not content.strip():
            raise WordPressError("El blog necesita título, slug y contenido antes de enviarlo a WordPress.")
        marker = f"<!-- nexiagp-blog-id:{blog_id} -->"
        target = dict(existing or {})
        if not target.get("postId"):
            target = self._find_owned_post_by_slug(slug, marker) or {}
        if str(target.get("status") or "") == "publish":
            raise WordPressError("El artículo ya está publicado en WordPress. No se sobrescribe desde el borrador.")
        payload = {
            "status": "draft",
            "title": title,
            "slug": slug,
            "content": f"{content}\n{marker}",
            "excerpt": excerpt,
        }
        if featured_media_id:
            payload["featured_media"] = int(featured_media_id)
        if category_id:
            payload["categories"] = [int(category_id)]
        if author_id:
            payload["author"] = int(author_id)
        safe_rank_math_meta = {
            key: str(value)
            for key, value in (rank_math_meta or {}).items()
            if key in _RANK_MATH_META_FIELDS and str(value).strip()
        }
        if safe_rank_math_meta:
            payload["meta"] = safe_rank_math_meta
        post_id = target.get("postId") or target.get("id")
        response = self._request(f"posts/{int(post_id)}" if post_id else "posts", method="POST", payload=payload)
        if not isinstance(response, dict) or not response.get("id") or not response.get("link"):
            raise WordPressError("WordPress no confirmó la creación del borrador.")
        resolved_post_id = int(response["id"])
        return {
            "postId": resolved_post_id,
            "postUrl": str(response["link"]),
            "editUrl": f"{self.base_url}/wp-admin/post.php?post={resolved_post_id}&action=edit",
            "status": str(response.get("status") or "draft"),
        }

    def sync_blog_draft(
        self,
        blog: dict,
        *,
        image_loader: Callable[[dict], tuple[bytes, str, str]],
        category_id: int | None = None,
        author_id: int | None = None,
    ) -> dict:
        figures = list(blog.get("figures") or [])
        missing = [str(item.get("figure_id") or "imagen") for item in figures if not isinstance(item.get("image"), dict)]
        if missing:
            raise WordPressError(f"Falta generar o seleccionar estas imágenes antes de enviar el blog: {', '.join(missing)}.")

        media_by_figure: dict[str, dict] = {}
        figure_sync: dict[str, dict] = {}
        uploaded = 0
        optimized_bytes = 0
        for figure in figures:
            figure_id = str(figure.get("figure_id") or "").strip()
            image = figure.get("image") or {}
            existing_media = figure.get("wordpress") if isinstance(figure.get("wordpress"), dict) else {}
            canonical_source = str(image.get("url") or "")
            if existing_media.get("mediaId") and existing_media.get("sourceImageUrl") == canonical_source:
                media = dict(existing_media)
            else:
                raw, _mime, source_name = image_loader(image)
                prepared = prepare_wordpress_image(raw, source_name)
                media = self.upload_media(prepared, alt=str(figure.get("caption") or ""), caption=str(figure.get("caption") or ""))
                media["sourceImageUrl"] = canonical_source
                uploaded += 1
                optimized_bytes += media["bytes"]
            media["alt"] = str(figure.get("caption") or "")
            media["caption"] = str(figure.get("caption") or "")
            media_by_figure[figure_id] = media
            figure_sync[figure_id] = {key: media[key] for key in ("mediaId", "sourceUrl", "sourceImageUrl", "bytes", "filename", "width", "height") if key in media}

        article = blog.get("article") or {}
        seo = blog.get("seo") or {}
        title = str(blog.get("title") or (blog.get("brief") or {}).get("h1") or "").strip()
        slug = str(blog.get("slug") or seo.get("slug") or "").strip()
        article_html = str(article.get("article_html_override") or article.get("article_html") or "")
        content = clean_wordpress_article(article_html, media_by_figure)
        excerpt = str(blog.get("metaDescription") or seo.get("meta_description") or "").strip()
        rank_math_fields = self.rank_math_meta_fields()
        rank_math_meta = self.rank_math_meta_values(
            rank_math_fields,
            meta_title=str(blog.get("metaTitle") or seo.get("meta_title") or title),
            meta_description=excerpt,
            focus_keyword=str((blog.get("brief") or {}).get("primary_keyword") or seo.get("primary_keyword") or ""),
        )
        featured = media_by_figure.get("hero") or next(iter(media_by_figure.values()), None)
        post = self.upsert_draft(
            blog_id=str(blog.get("id") or ""),
            title=title,
            slug=slug,
            content=content,
            excerpt=excerpt,
            featured_media_id=int(featured.get("mediaId")) if featured and featured.get("mediaId") else None,
            existing=blog.get("wordpress") if isinstance(blog.get("wordpress"), dict) else None,
            category_id=category_id,
            author_id=author_id,
            rank_math_meta=rank_math_meta,
        )
        post["rankMath"] = {
            "detected": bool(rank_math_fields),
            "applied": sorted(rank_math_meta),
            "manualReview": not bool(rank_math_meta),
        }
        return {
            "post": post,
            "figures": figure_sync,
            "uploadedImages": uploaded,
            "optimizedBytes": optimized_bytes,
            "contentHash": wordpress_content_hash(title, slug, content, excerpt),
        }
