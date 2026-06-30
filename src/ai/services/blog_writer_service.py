from __future__ import annotations

import json

from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import load_prompt, load_schema


class BlogWriterService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def write(self, request: dict, brief: dict, retrieval: dict | None, db: dict) -> tuple[dict, str | None]:
        system = load_prompt("blog_writer_v1.txt")
        user = self._build_user(request, brief, retrieval)
        result, response_id = self.client.responses_json(
            system=system,
            user=user,
            schema=load_schema("blog_article.schema.json"),
            schema_name="nexiagp_blog_article",
            model=db.get("settings", {}).get("model") or None,
        )
        return result, response_id

    @staticmethod
    def _build_user(request: dict, brief: dict, retrieval: dict | None) -> str:
        retrieval_block = ""
        if retrieval and retrieval.get("sources"):
            sources_summary = "\n".join(
                f"- [{s.get('title')}] {s.get('excerpt', '')[:280]}" for s in retrieval["sources"][:6]
            )
            retrieval_block = f"\n\nCONTEXTO RECUPERADO (usar como fuente factual; no inventar mas):\n{sources_summary}"
        return (
            "Redacta el articulo COMPLETO en HTML siguiendo el brief al pie.\n\n"
            f"SOLICITUD ORIGINAL: {json.dumps(request, ensure_ascii=False)}\n\n"
            f"BRIEF ESTRATEGICO + OUTLINE:\n{json.dumps(brief, ensure_ascii=False, indent=2)}"
            f"{retrieval_block}\n\n"
            "Devuelve SOLO JSON conforme al schema. El article_html debe contener TODO el contenido del articulo (article, header, secciones, figures, CTA)."
        )
