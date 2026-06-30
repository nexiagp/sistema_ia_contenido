from __future__ import annotations

import json

from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import load_prompt, load_schema


class BlogSEOService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def build(self, brief: dict, article: dict, db: dict) -> tuple[dict, str | None]:
        system = load_prompt("blog_seo_v1.txt")
        user = (
            "Genera el paquete SEO completo para este blog post.\n\n"
            f"BRIEF:\n{json.dumps(brief, ensure_ascii=False)}\n\n"
            f"ARTICULO (HTML):\n{article.get('article_html', '')[:8000]}"
        )
        result, response_id = self.client.responses_json(
            system=system,
            user=user,
            schema=load_schema("blog_seo.schema.json"),
            schema_name="nexiagp_blog_seo",
            model=db.get("settings", {}).get("model") or None,
        )
        return result, response_id
