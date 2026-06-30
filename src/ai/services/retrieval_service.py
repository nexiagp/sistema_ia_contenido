from __future__ import annotations

import re
from pathlib import Path

from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import base_prompt, schema


ROOT = Path(__file__).resolve().parents[3]


class RetrievalService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def retrieve(self, db: dict, brief: dict, request: dict) -> dict:
        vector_store_id = db.get("settings", {}).get("vectorStoreId", "")
        if self.client.enabled and vector_store_id:
            try:
                return self._retrieve_with_file_search(vector_store_id, brief, request)
            except Exception as exc:
                local = self._retrieve_locally(brief, request)
                local["warnings"].append(f"file_search no disponible: {exc}")
                return local
        local = self._retrieve_locally(brief, request)
        if not vector_store_id:
            local["warnings"].append("Vector Store no configurada; retrieval local usado.")
        return local

    def _retrieve_with_file_search(self, vector_store_id: str, brief: dict, request: dict) -> dict:
        query = self._query_from(brief, request)
        user = (
            "Recupera contexto relevante para redactar un post de Nexia GP.\n"
            "Devuelve solo fuentes utiles y aprobadas para copy.\n"
            f"Brief: {brief}\n"
            f"Solicitud: {request}\n"
            f"Consulta: {query}"
        )
        result, _ = self.client.responses_json(
            system=base_prompt(),
            user=user,
            schema=schema("retrieval.schema.json"),
            schema_name="nexiagp_retrieval",
            tools=[{"type": "file_search", "vector_store_ids": [vector_store_id], "max_num_results": 8}],
        )
        return result

    def _retrieve_locally(self, brief: dict, request: dict) -> dict:
        query = self._query_from(brief, request)
        keywords = self._keywords(query)
        chunks = []
        for doc in self._local_docs():
            text = doc["text"]
            score = self._score(text, keywords)
            if score <= 0:
                continue
            excerpt = self._best_excerpt(text, keywords)
            chunks.append(
                {
                    "score": score,
                    "source_id": doc["source_id"],
                    "title": doc["title"],
                    "entity": doc["entity"],
                    "source_group": doc["source_group"],
                    "excerpt": excerpt,
                    "relevance": "high" if score >= 6 else "medium",
                }
            )
        chunks.sort(key=lambda item: item["score"], reverse=True)
        sources = [{key: value for key, value in item.items() if key != "score"} for item in chunks[:8]]
        if not sources:
            sources = self._fallback_sources()
        confidence = "high" if len(sources) >= 4 else "medium" if sources else "low"
        return {
            "query_used": query,
            "context_summary": self._summary_from_sources(sources),
            "sources": sources,
            "confidence": confidence,
            "warnings": [] if sources else ["No se encontro contexto documental suficiente."],
        }

    def _local_docs(self) -> list[dict]:
        roots = [ROOT / "Documentación Nexia", ROOT / "data" / "uploads"]
        docs: list[dict] = []
        seen_titles: set[str] = set()
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".txt", ".md"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                title = re.sub(r"^file_[a-f0-9]{12}-", "", path.stem)
                title_key = title.lower()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)
                docs.append(
                    {
                        "source_id": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "title": title,
                        "entity": "nexia",
                        "source_group": "web" if "WEB" in [part.upper() for part in path.parts] else "nexia_core",
                        "text": text,
                    }
                )
        return docs

    def _fallback_sources(self) -> list[dict]:
        return [
            {
                "source_id": "app/editorial_context",
                "title": "Contexto editorial Nexia GP",
                "entity": "nexia",
                "source_group": "nexia_core",
                "excerpt": "Nexia GP se comunica como partner comercial-tecnico B2B con conocimiento local, criterio de mercado y foco en fabricantes, distribuidores y clientes empresariales en Canarias.",
                "relevance": "medium",
            }
        ]

    @staticmethod
    def _query_from(brief: dict, request: dict) -> str:
        parts = [
            brief.get("core_angle", ""),
            brief.get("core_thesis", ""),
            brief.get("sector", ""),
            brief.get("entity", ""),
            request.get("tema_libre", ""),
            request.get("marca_o_entidad", ""),
            " ".join(brief.get("keywords", [])),
        ]
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def _keywords(text: str) -> list[str]:
        stop = {"para", "como", "desde", "sobre", "nexia", "canarias", "mercado", "post", "tema"}
        words = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9]{4,}", text.lower())
        return [word for word in dict.fromkeys(words) if word not in stop][:18]

    @staticmethod
    def _score(text: str, keywords: list[str]) -> int:
        low = text.lower()
        return sum(low.count(keyword.lower()) for keyword in keywords)

    @staticmethod
    def _best_excerpt(text: str, keywords: list[str]) -> str:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            return text[:900]
        best = max(paragraphs, key=lambda p: RetrievalService._score(p, keywords))
        return best[:1100]

    @staticmethod
    def _summary_from_sources(sources: list[dict]) -> str:
        titles = ", ".join(source["title"] for source in sources[:4])
        return f"Contexto recuperado de {titles}." if titles else "Sin contexto documental suficiente."
