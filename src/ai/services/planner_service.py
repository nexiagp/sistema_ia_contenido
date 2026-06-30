from __future__ import annotations

from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import base_prompt, planner_prompt, schema
from src.domain.editorial import MASTER_POST_TYPES, POST_TYPES


class PlannerService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def plan(self, request: dict, db: dict) -> tuple[dict, str | None]:
        if self.client.enabled:
            try:
                user = self._build_user_prompt(request, db)
                return self.client.responses_json(
                    system=f"{base_prompt()}\n\n{planner_prompt()}",
                    user=user,
                    schema=schema("planner.schema.json"),
                    schema_name="nexiagp_planner",
                    model=db.get("settings", {}).get("model") or None,
                )
            except Exception:
                return self._fallback_plan(request), None
        return self._fallback_plan(request), None

    @staticmethod
    def _build_user_prompt(request: dict, db: dict) -> str:
        used = [
            post.get("idea") or post.get("title")
            for post in db.get("posts", [])[:30]
            if post.get("idea") or post.get("title")
        ]
        return (
            "Construye un brief estrategico para Nexia GP.\n"
            f"Solicitud del usuario: {request}\n"
            f"Tipos soportados: {MASTER_POST_TYPES}\n"
            f"Ideas recientes a evitar: {used}\n"
        )

    @staticmethod
    def _fallback_plan(request: dict) -> dict:
        post_type = request.get("tipo_post") or "auto"
        if post_type == "auto" or post_type not in POST_TYPES:
            post_type = PlannerService._infer_post_type(request)
        sector = request.get("sector") or "Canarias"
        entity = request.get("marca_o_entidad") or "Nexia GP"
        topic = request.get("tema_libre") or POST_TYPES[post_type]["description"]
        audience = request.get("audiencia_principal") or "mixta"
        objective = request.get("objetivo") or "autoridad"
        return {
            "channel": request.get("canal") or "linkedin",
            "post_type": post_type,
            "pillar": POST_TYPES[post_type]["pillar"],
            "objective": objective,
            "audience": audience,
            "core_angle": f"{topic} desde el criterio comercial de Nexia GP",
            "core_thesis": f"El crecimiento B2B en Canarias necesita algo mas que producto: necesita encaje de canal, soporte y lectura local.",
            "why_it_matters": "Ayuda a fabricantes y distribuidores a entender que la implantacion comercial requiere criterio, acompanamiento y coordinacion.",
            "cta_type": request.get("cta_preferida") or "comentario",
            "entity": entity,
            "sector": sector,
            "needs_link": bool(request.get("usar_enlace", False)),
            "factual_sensitivity": "high" if post_type in {"fabricante_colaborador", "actualidad_lectura_mercado", "proyecto_prescripcion"} else "medium",
            "promotional_intensity": "low" if request.get("nivel_promocional") == "bajo" else "medium",
            "human_review_level": "high" if post_type in {"fabricante_colaborador", "actualidad_lectura_mercado"} else "normal",
            "keywords": [sector, entity, topic, "fabricantes", "distribuidores", "Canarias"],
            "risk_notes": ["Plan generado sin llamada OpenAI; revisar claims concretos antes de publicar."],
        }

    @staticmethod
    def _infer_post_type(request: dict) -> str:
        text = " ".join(str(request.get(key, "")) for key in ["sector", "marca_o_entidad", "tema_libre"]).lower()
        if any(word in text for word in ["showroom", "logistica", "stock", "pedido", "incidencia", "operativa"]):
            return "servicio_proceso_operativa"
        if any(word in text for word in ["proyecto", "prescripcion", "hotel", "licitacion", "obra"]):
            return "proyecto_prescripcion"
        if any(word in text for word in ["marca", "fabricante", "colaborador", "partner"]):
            return "fabricante_colaborador"
        if any(word in text for word in ["noticia", "actualidad", "feria", "tendencia"]):
            return "actualidad_lectura_mercado"
        if request.get("sector"):
            return "sector_solucion"
        return "educativo_autoridad"
