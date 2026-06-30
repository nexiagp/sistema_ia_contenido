from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.ai.services.adaptation_service import AdaptationService
from src.ai.services.openai_client import OpenAIClient
from src.ai.services.planner_service import PlannerService
from src.ai.services.retrieval_service import RetrievalService
from src.ai.services.validator_service import ValidatorService
from src.ai.services.writer_service import WriterService


class EditorialPipeline:
    def __init__(self, model: str | None = None) -> None:
        self.client = OpenAIClient(model=model)
        self.planner = PlannerService(self.client)
        self.retrieval = RetrievalService(self.client)
        self.writer = WriterService(self.client)
        self.validator = ValidatorService(self.client)
        self.adapter = AdaptationService(self.client)

    def run(self, request: dict, db: dict) -> dict:
        responses: dict[str, str | None] = {}
        brief, responses["planner"] = self.planner.plan(request, db)
        retrieval = self.retrieval.retrieve(db, brief, request)
        generation, responses["writer"] = self.writer.write(request, brief, retrieval, db)
        validation, responses["validator"] = self.validator.validate(request, brief, retrieval, generation, db)

        generation["copy"]["final_post"] = validation["final_post"]
        generation["copy"]["cta"] = validation["cta"]
        generation["copy"]["hashtags"] = validation["hashtags"]
        generation["editorial_support"]["human_review_notes"] = list(
            dict.fromkeys(generation["editorial_support"].get("human_review_notes", []) + validation["validation_notes"])
        )
        generation["traceability"]["source_titles_used"] = [
            source["title"] for source in retrieval.get("sources", [])
        ][:8]
        generation["traceability"]["source_entities_used"] = list(
            dict.fromkeys(source["entity"] for source in retrieval.get("sources", []))
        )
        generation["traceability"]["confidence"] = retrieval.get("confidence", "medium")

        adaptations = None
        if request.get("necesita_adaptacion_multicanal", True):
            adaptations, responses["adaptation"] = self.adapter.adapt(generation, validation, db)

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        post = {
            "id": f"post_{uuid4().hex[:12]}",
            "createdAt": now,
            "updatedAt": now,
            "status": "draft",
            "provider": "openai" if self.client.enabled else "local_pipeline",
            "source": "editorial_pipeline",
            "request": normalize_request(request),
            "brief": brief,
            "retrieval": retrieval,
            "generation": generation,
            "validation": validation,
            "adaptations": adaptations,
            "responseIds": responses,
            "title": generation.get("strategy", {}).get("core_angle") or brief.get("core_angle"),
            "idea": brief.get("core_thesis"),
            "angle": brief.get("core_angle"),
            "platform": generation.get("meta", {}).get("channel", "linkedin"),
            "copy": generation.get("copy", {}).get("final_post", ""),
            "hashtags": generation.get("copy", {}).get("hashtags", []),
            "cta": generation.get("copy", {}).get("cta", ""),
            "themeId": brief.get("post_type"),
            "themeTitle": brief.get("pillar"),
            "postTypeId": brief.get("post_type"),
            "postTypeLabel": brief.get("post_type"),
            "publishedAt": None,
            "publishResult": None,
        }
        return {
            "ok": True,
            "post": post,
            "brief": brief,
            "retrieval": retrieval,
            "generation": generation,
            "validation": validation,
            "adaptations": adaptations,
        }

    def adapt_existing(self, post: dict, db: dict) -> dict:
        generation = post.get("generation") or {}
        validation = post.get("validation") or {
            "final_post": post.get("copy", ""),
            "cta": post.get("cta", ""),
            "hashtags": post.get("hashtags", []),
        }
        adaptations, response_id = self.adapter.adapt(generation, validation, db)
        post["adaptations"] = adaptations
        post.setdefault("responseIds", {})["adaptation"] = response_id
        post["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return adaptations


def normalize_request(request: dict[str, Any]) -> dict:
    return {
        "canal": request.get("canal") or "linkedin",
        "tipo_post": request.get("tipo_post") or "auto",
        "objetivo": request.get("objetivo") or "autoridad",
        "audiencia_principal": request.get("audiencia_principal") or "mixta",
        "sector": request.get("sector") or "",
        "marca_o_entidad": request.get("marca_o_entidad") or "",
        "tema_libre": request.get("tema_libre") or "",
        "cta_preferida": request.get("cta_preferida") or "comentario",
        "usar_enlace": bool(request.get("usar_enlace", False)),
        "nivel_promocional": request.get("nivel_promocional") or "bajo",
        "necesita_adaptacion_multicanal": bool(request.get("necesita_adaptacion_multicanal", True)),
        "notas_humanas": request.get("notas_humanas") or "",
        "regeneration_instruction": request.get("regeneration_instruction") or "",
    }
