"""Deterministic quality and safety controls for editorial content.

The model can propose content and source labels, but the application is the
authority for publication state, source traceability and exported HTML.  This
module keeps those decisions local, explicit and testable.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from html.parser import HTMLParser

from src.domain.blog import BLOG_LENGTH_TARGETS


SENSITIVE_POST_TYPES = {
    "dato_opinion",
    "actualidad_lectura_mercado",
    "social_proof_caso",
}

_ALLOWED_TAGS = {
    "article", "aside", "blockquote", "br", "div", "em", "figure",
    "figcaption", "h1", "h2", "h3", "header", "img", "li", "ol",
    "p", "span", "strong", "table", "tbody", "td", "th", "thead",
    "tr", "ul", "a",
}
_VOID_TAGS = {"br", "img"}
_BLOCKED_TAGS = {"embed", "iframe", "math", "object", "script", "style", "svg"}


def _normalise_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _filename_stem(value: object) -> str:
    name = str(value or "").replace("\\", "/").rsplit("/", 1)[-1]
    return re.sub(r"\.[^.]+$", "", name)


def _compact_text(value: object, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].strip()


def _source_group(category: object) -> str:
    value = str(category or "").strip().lower()
    if value.startswith("kb-") or value in {"official", "official_data"}:
        return "official_data"
    if value in {"brand", "nexia_core"}:
        return "nexia_core"
    if value == "web":
        return "web"
    return value or "unclassified"


def canonicalize_retrieval(
    retrieval: dict | None,
    files: list[dict] | None,
    *,
    allow_local_sources: bool = False,
) -> dict:
    """Replace model-proposed source IDs with IDs from the local file catalog.

    File search returns content, but a structured model response can still
    hallucinate identifiers or titles.  Remote results without a catalog match
    are intentionally excluded from publishable traceability.  Local fallback
    results are allowed to retain their controlled local path.
    """
    result = dict(retrieval or {})
    catalog: dict[str, dict] = {}
    for item in files or []:
        if not isinstance(item, dict):
            continue
        for candidate in (
            item.get("id"),
            item.get("openaiFileId"),
            item.get("vectorStoreFileId"),
            item.get("name"),
            _filename_stem(item.get("name")),
        ):
            key = _normalise_key(candidate)
            if key:
                catalog.setdefault(key, item)

    sources: list[dict] = []
    rejected = 0
    for raw in result.get("sources") or []:
        if not isinstance(raw, dict):
            rejected += 1
            continue
        item = catalog.get(_normalise_key(raw.get("source_id"))) or catalog.get(_normalise_key(raw.get("title")))
        excerpt = _compact_text(raw.get("excerpt"), 700)
        if item:
            sources.append(
                {
                    "source_id": str(item.get("id") or ""),
                    "title": str(item.get("name") or raw.get("title") or "Fuente catalogada"),
                    "entity": _compact_text(raw.get("entity") or "nexia", 80),
                    "source_group": _source_group(item.get("category")),
                    "excerpt": excerpt,
                    "relevance": raw.get("relevance") if raw.get("relevance") in {"high", "medium", "low"} else "medium",
                }
            )
            continue
        if allow_local_sources and str(raw.get("source_id") or "").startswith(("Documentación Nexia/", "data/uploads/")):
            sources.append(
                {
                    "source_id": str(raw.get("source_id")),
                    "title": _compact_text(raw.get("title"), 180) or "Fuente local",
                    "entity": _compact_text(raw.get("entity") or "nexia", 80),
                    "source_group": _source_group(raw.get("source_group")),
                    "excerpt": excerpt,
                    "relevance": raw.get("relevance") if raw.get("relevance") in {"high", "medium", "low"} else "medium",
                }
            )
            continue
        rejected += 1

    grouped_sources: list[dict] = []
    grouped_by_id: dict[str, dict] = {}
    for source in sources:
        source_id = source.get("source_id") or source.get("title")
        existing = grouped_by_id.get(source_id)
        if not existing:
            grouped_by_id[source_id] = source
            grouped_sources.append(source)
            continue
        excerpt = source.get("excerpt") or ""
        if excerpt and excerpt not in existing["excerpt"]:
            existing["excerpt"] = _compact_text(f"{existing['excerpt']}\n{excerpt}", 1_200)
        if source.get("relevance") == "high":
            existing["relevance"] = "high"

    warnings = [str(item) for item in result.get("warnings") or [] if str(item).strip()]
    if rejected:
        warnings.append(
            f"{rejected} fuente(s) propuesta(s) no coincidieron con la biblioteca y se excluyeron de la trazabilidad."
        )
    if not grouped_sources:
        warnings.append("No hay fuentes verificables disponibles para sostener claims concretos.")

    confidence = result.get("confidence") if result.get("confidence") in {"high", "medium", "low"} else "medium"
    if not grouped_sources:
        confidence = "low"
    elif rejected and confidence == "high":
        confidence = "medium"

    titles = ", ".join(item["title"] for item in grouped_sources[:4])
    result.update(
        {
            "sources": grouped_sources[:8],
            "warnings": list(dict.fromkeys(warnings)),
            "confidence": confidence,
            "context_summary": f"Contexto recuperado de {titles}." if titles else "Sin contexto documental suficiente.",
        }
    )
    return result


def compact_retrieval(retrieval: dict | None, *, source_limit: int = 4, excerpt_limit: int = 600) -> dict:
    """Return only the factual context a model needs for the next pipeline step."""
    payload = retrieval or {}
    return {
        "context_summary": _compact_text(payload.get("context_summary"), 420),
        "confidence": payload.get("confidence") or "low",
        "sources": [
            {
                "title": _compact_text(source.get("title"), 180),
                "source_group": _compact_text(source.get("source_group"), 40),
                "excerpt": _compact_text(source.get("excerpt"), excerpt_limit),
            }
            for source in (payload.get("sources") or [])[:source_limit]
            if isinstance(source, dict)
        ],
        "warnings": [_compact_text(item, 200) for item in (payload.get("warnings") or [])[:3]],
    }


def post_quality_gate(request: dict, brief: dict, retrieval: dict, validation: dict) -> dict:
    """Turn model flags and factual context into a deterministic ready-state gate."""
    post_type = brief.get("post_type") or request.get("tipo_post") or "auto"
    flags = [str(item) for item in validation.get("review_flags") or [] if str(item).strip()]
    sources = retrieval.get("sources") or []
    blockers: list[str] = []
    warnings: list[str] = [str(item) for item in retrieval.get("warnings") or [] if str(item).strip()]

    if flags:
        blockers.append(f"El validador ha marcado: {', '.join(flags)}.")
    if validation.get("human_review_required"):
        blockers.append("El validador solicita revisión humana antes de preparar la publicación.")
    if retrieval.get("confidence") == "low" or not sources:
        blockers.append("No hay base documental verificable para sostener esta pieza.")
    if post_type in SENSITIVE_POST_TYPES:
        blockers.append(f"El tipo «{post_type}» exige revisión humana y trazabilidad explícita.")
    if post_type == "dato_opinion" and not any(source.get("source_group") == "official_data" for source in sources):
        blockers.append("Un post de dato + opinión requiere al menos una fuente oficial o sectorial catalogada.")
    if brief.get("factual_sensitivity") == "high":
        blockers.append("La sensibilidad factual es alta; confirma nombres, fechas y claims antes de calendarizar.")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        validation["human_review_required"] = True
        if validation.get("risk_level") == "low":
            validation["risk_level"] = "medium"
        notes = validation.setdefault("validation_notes", [])
        notes.append("Puerta de calidad activada: requiere confirmación humana registrada.")
        validation["validation_notes"] = list(dict.fromkeys(str(item) for item in notes if str(item).strip()))

    return {
        "status": "review_required" if blockers else "passed",
        "can_mark_ready": not blockers,
        "blockers": blockers,
        "warnings": list(dict.fromkeys(warnings)),
        "source_count": len(sources),
    }


def is_safe_internal_path(value: object) -> bool:
    path = str(value or "").strip()
    return bool(
        path.startswith("/")
        and not path.startswith("//")
        and "\\" not in path
        and ".." not in path.split("/")
        and re.fullmatch(r"/[A-Za-z0-9._~%/?=&-]*", path)
    )


def _is_safe_href(value: object) -> bool:
    href = html.unescape(str(value or "")).strip()
    return href == "https://nexiagp.com/contacto/" or is_safe_internal_path(href)


def _is_safe_image_src(value: object) -> bool:
    src = html.unescape(str(value or "")).strip()
    return src.startswith("https://") or (src.startswith("/images/") and is_safe_internal_path(src))


def _safe_class(value: object) -> str:
    tokens = re.findall(r"[A-Za-z0-9_-]{1,48}", str(value or ""))
    return " ".join(tokens[:6])


class _SafeBlogHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.open_tags: list[tuple[str, str | None]] = []
        self.block_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.block_depth:
            if tag in _BLOCKED_TAGS:
                self.block_depth += 1
            return
        if tag in _BLOCKED_TAGS:
            self.block_depth = 1
            return
        if tag not in _ALLOWED_TAGS:
            self.open_tags.append((tag, None))
            return

        raw = dict(attrs)
        out_tag = tag
        out_attrs: list[tuple[str, str]] = []
        class_name = _safe_class(raw.get("class"))
        if class_name:
            out_attrs.append(("class", class_name))

        if tag == "a":
            if _is_safe_href(raw.get("href")):
                out_attrs.append(("href", html.unescape(str(raw["href"])).strip()))
            else:
                out_tag = "span"
                out_attrs = [("class", " ".join(item for item in [class_name, "lm-pending"] if item))]
        elif tag == "img":
            if _is_safe_image_src(raw.get("src")):
                out_attrs.append(("src", html.unescape(str(raw["src"])).strip()))
            else:
                return
            alt = _compact_text(raw.get("alt"), 240)
            if alt:
                out_attrs.append(("alt", alt))
        elif tag == "figure":
            for name in ("data-figure-id", "data-figure-prompt"):
                value = _compact_text(raw.get(name), 700 if name.endswith("prompt") else 80)
                if value:
                    out_attrs.append((name, value))
        elif tag == "th" and raw.get("scope") in {"col", "row"}:
            out_attrs.append(("scope", str(raw["scope"])))

        rendered_attrs = "".join(f' {name}="{html.escape(value, quote=True)}"' for name, value in out_attrs if value)
        self.parts.append(f"<{out_tag}{rendered_attrs}>")
        if tag not in _VOID_TAGS:
            self.open_tags.append((tag, out_tag))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.block_depth:
            if tag in _BLOCKED_TAGS:
                self.block_depth -= 1
            return
        for index in range(len(self.open_tags) - 1, -1, -1):
            original, rendered = self.open_tags[index]
            if original == tag:
                del self.open_tags[index:]
                if rendered:
                    self.parts.append(f"</{rendered}>")
                return

    def handle_data(self, data: str) -> None:
        if not self.block_depth:
            self.parts.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        if not self.block_depth:
            self.parts.append(html.escape(html.unescape(f"&{name};")))

    def handle_charref(self, name: str) -> None:
        if not self.block_depth:
            self.parts.append(html.escape(html.unescape(f"&#{name};")))


def sanitize_article_html(value: object) -> str:
    parser = _SafeBlogHTMLParser()
    parser.feed(str(value or ""))
    parser.close()
    return "".join(parser.parts).strip()


def _word_count(html_value: str) -> int:
    plain = re.sub(r"<[^>]+>", " ", html_value)
    plain = html.unescape(plain)
    return len(re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+(?:['’][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+)?", plain))


def _sanitize_seo(seo: dict | None) -> tuple[dict, list[str]]:
    clean = dict(seo or {})
    notes: list[str] = []
    slug_source = unicodedata.normalize("NFKD", str(clean.get("slug") or ""))
    slug_source = slug_source.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug_source).strip("-")
    if slug:
        clean["slug"] = slug[:90]
    canonical = str(clean.get("canonical_path") or "").strip()
    if not is_safe_internal_path(canonical):
        canonical = f"/{slug}/" if slug else ""
        notes.append("La ruta canonical no era segura o válida y se ha normalizado.")
    clean["canonical_path"] = canonical

    schema_raw = clean.get("schema_jsonld")
    if schema_raw:
        try:
            schema_obj = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw
            if not isinstance(schema_obj, dict):
                raise ValueError("El schema no es un objeto JSON.")
            clean["schema_jsonld"] = (
                json.dumps(schema_obj, ensure_ascii=False, separators=(",", ":"))
                .replace("<", "\\u003c")
                .replace(">", "\\u003e")
                .replace("&", "\\u0026")
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            clean["schema_jsonld"] = ""
            notes.append("El JSON-LD no era válido y se ha retirado de la exportación.")
    return clean, notes


def blog_quality_gate(
    request: dict,
    brief: dict,
    retrieval: dict,
    article: dict,
    seo: dict,
) -> tuple[dict, dict, dict]:
    """Sanitize a blog and produce a gate that controls the ready transition."""
    safe_article = dict(article or {})
    original_html = str(safe_article.get("article_html") or "")
    safe_html = sanitize_article_html(original_html)
    safe_article["article_html"] = safe_html
    safe_article["word_count"] = _word_count(safe_html)
    safe_article["internal_links_used"] = [
        dict(item)
        for item in (safe_article.get("internal_links_used") or [])
        if isinstance(item, dict) and is_safe_internal_path(item.get("url_path"))
    ]
    safe_seo, seo_notes = _sanitize_seo(seo)

    blockers: list[str] = []
    warnings: list[str] = []
    length = request.get("length") if request.get("length") in BLOG_LENGTH_TARGETS else "medio"
    target = BLOG_LENGTH_TARGETS[length]
    h1_count = len(re.findall(r"<h1(?:\s[^>]*)?>", safe_html, flags=re.IGNORECASE))
    figure_count = len(re.findall(r"<figure(?:\s[^>]*)?>", safe_html, flags=re.IGNORECASE))
    try:
        expected_figures = max(0, min(6, int(request.get("images_per_article", 2))))
    except (TypeError, ValueError):
        expected_figures = 2

    if h1_count != 1:
        blockers.append("El artículo debe contener exactamente un H1.")
    if safe_article["word_count"] < target["min"]:
        blockers.append(
            f"El artículo tiene {safe_article['word_count']} palabras y no alcanza el mínimo de {target['min']} para «{length}»."
        )
    if safe_article["word_count"] > target["max"]:
        warnings.append(
            f"El artículo supera el rango objetivo de {target['max']} palabras para «{length}»."
        )
    if figure_count != expected_figures:
        blockers.append(
            f"El HTML contiene {figure_count} figura(s) y la solicitud exige exactamente {expected_figures}."
        )
    if not retrieval.get("sources"):
        blockers.append("El blog no tiene fuentes verificables catalogadas.")
    if not safe_seo.get("schema_jsonld"):
        blockers.append("Falta un JSON-LD válido para la exportación SEO.")
    if "<script" in original_html.lower() or "<style" in original_html.lower():
        warnings.append("Se retiraron elementos HTML no permitidos antes de guardar el artículo.")

    seo_flags = [str(item) for item in safe_seo.get("seo_review_flags") or [] if str(item).strip()]
    if seo_flags:
        blockers.append(f"El control SEO ha marcado: {', '.join(seo_flags)}.")
    blockers.extend(seo_notes)
    blockers = list(dict.fromkeys(blockers))
    warnings.extend(str(item) for item in retrieval.get("warnings") or [] if str(item).strip())

    return (
        safe_article,
        safe_seo,
        {
            "status": "review_required" if blockers else "passed",
            "can_mark_ready": not blockers,
            "blockers": blockers,
            "warnings": list(dict.fromkeys(warnings)),
            "word_count": safe_article["word_count"],
            "h1_count": h1_count,
            "figure_count": figure_count,
            "expected_figure_count": expected_figures,
        },
    )
