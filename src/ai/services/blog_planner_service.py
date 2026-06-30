from __future__ import annotations

import json

from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import load_prompt, load_schema


class BlogPlannerService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def plan(self, request: dict, retrieval: dict | None, db: dict) -> tuple[dict, str | None]:
        system = load_prompt("blog_planner_v1.txt")
        user = self._build_user(request, retrieval)
        result, response_id = self.client.responses_json(
            system=system,
            user=user,
            schema=load_schema("blog_brief.schema.json"),
            schema_name="nexiagp_blog_brief",
            model=db.get("settings", {}).get("model") or None,
        )
        return result, response_id

    @staticmethod
    def _build_user(request: dict, retrieval: dict | None) -> str:
        retrieval_block = ""
        if retrieval and retrieval.get("sources"):
            sources_summary = "\n".join(
                f"- {s.get('title')}: {s.get('excerpt', '')[:240]}" for s in retrieval["sources"][:6]
            )
            retrieval_block = f"\n\nCONTEXTO RECUPERADO DE LA KB:\n{sources_summary}"
        return (
            "Construye el brief estrategico + outline completo del blog post.\n\n"
            f"SOLICITUD: {json.dumps(request, ensure_ascii=False)}"
            f"{retrieval_block}\n\n"
            "Devuelve SOLO JSON conforme al schema. No inventes datos ni marcas."
        )
