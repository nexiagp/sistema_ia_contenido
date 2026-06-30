from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.ai.services.blog_planner_service import BlogPlannerService
from src.ai.services.blog_seo_service import BlogSEOService
from src.ai.services.blog_writer_service import BlogWriterService
from src.ai.services.openai_client import OpenAIClient
from src.ai.services.retrieval_service import RetrievalService


class BlogPipeline:
    def __init__(self, model: str | None = None) -> None:
        self.client = OpenAIClient(model=model)
        self.planner = BlogPlannerService(self.client)
        self.retrieval = RetrievalService(self.client)
        self.writer = BlogWriterService(self.client)
        self.seo = BlogSEOService(self.client)

    def run(self, request: dict, db: dict) -> dict:
        responses: dict[str, str | None] = {}

        initial_brief = self._brief_for_retrieval(request)
        retrieval = self.retrieval.retrieve(db, initial_brief, request)

        brief, responses["planner"] = self.planner.plan(request, retrieval, db)

        post_planner_brief = self._brief_for_retrieval({**request, **{
            "tema_libre": brief.get("core_thesis", ""),
            "marca_o_entidad": brief.get("target_persona", ""),
        }})
        post_planner_brief.update({
            "core_angle": brief.get("thought_leadership_angle", ""),
            "core_thesis": brief.get("core_thesis", ""),
            "keywords": [brief.get("primary_keyword", "")] + brief.get("secondary_keywords", []),
        })
        retrieval = self.retrieval.retrieve(db, post_planner_brief, request)

        article, responses["writer"] = self.writer.write(request, brief, retrieval, db)
        seo, responses["seo"] = self.seo.build(brief, article, db)

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        blog = {
            "id": f"blog_{uuid4().hex[:12]}",
            "createdAt": now,
            "updatedAt": now,
            "status": "draft",
            "provider": "openai" if self.client.enabled else "local_pipeline",
            "source": "blog_pipeline",
            "request": normalize_request(request),
            "brief": brief,
            "retrieval": retrieval,
            "article": article,
            "seo": seo,
            "responseIds": responses,
            "title": brief.get("h1"),
            "slug": seo.get("slug"),
            "metaTitle": seo.get("meta_title"),
            "metaDescription": seo.get("meta_description"),
            "wordCount": article.get("word_count"),
            "figures": [
                {**slot, "image": None} for slot in (article.get("figure_slots") or [])
            ],
            "publishedAt": None,
        }
        return {
            "ok": True,
            "blog": blog,
            "brief": brief,
            "retrieval": retrieval,
            "article": article,
            "seo": seo,
        }

    @staticmethod
    def _brief_for_retrieval(request: dict[str, Any]) -> dict:
        return {
            "core_angle": request.get("tema_libre", ""),
            "core_thesis": request.get("tema_libre", ""),
            "sector": request.get("sector", ""),
            "entity": request.get("marca_o_entidad", ""),
            "keywords": [],
        }


def normalize_request(request: dict[str, Any]) -> dict:
    try:
        images = int(request.get("images_per_article")) if request.get("images_per_article") not in (None, "") else 2
    except (TypeError, ValueError):
        images = 2
    return {
        "topic": request.get("topic") or request.get("tema_libre") or "",
        "tema_libre": request.get("tema_libre") or request.get("topic") or "",
        "search_intent_hint": request.get("search_intent_hint") or "auto",
        "framework_hint": request.get("framework_hint") or "auto",
        "audience": request.get("audience") or "mixta",
        "sector": request.get("sector") or "",
        "length": request.get("length") or "medio",
        "cta_type": request.get("cta_type") or "consulta_servicios",
        "notas_humanas": request.get("notas_humanas") or "",
        "marca_o_entidad": request.get("marca_o_entidad") or "Nexia GP",
        "images_per_article": max(0, min(6, images)),
    }
