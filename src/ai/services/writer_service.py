from __future__ import annotations

from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import base_prompt, post_type_prompt, schema


class WriterService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def write(self, request: dict, brief: dict, retrieval: dict, db: dict) -> tuple[dict, str | None]:
        if self.client.enabled:
            try:
                user = self._build_user_prompt(request, brief, retrieval)
                system = f"{base_prompt()}\n\n{post_type_prompt(brief['post_type'])}"
                return self.client.responses_json(
                    system=system,
                    user=user,
                    schema=schema("generation.schema.json"),
                    schema_name="nexiagp_generation",
                    model=db.get("settings", {}).get("model") or None,
                )
            except Exception:
                return self._fallback_write(request, brief, retrieval), None
        return self._fallback_write(request, brief, retrieval), None

    @staticmethod
    def _build_user_prompt(request: dict, brief: dict, retrieval: dict) -> str:
        return (
            "Redacta el contenido con salida estructurada.\n"
            f"Solicitud original: {request}\n"
            f"Brief estrategico: {brief}\n"
            f"Contexto recuperado: {retrieval}\n"
            "No uses ninguna fuente fuera del briefing y del contexto recuperado."
        )

    @staticmethod
    def _fallback_write(request: dict, brief: dict, retrieval: dict) -> dict:
        source_titles = [source["title"] for source in retrieval.get("sources", [])]
        source_entities = list(dict.fromkeys(source["entity"] for source in retrieval.get("sources", [])))
        hashtags = ["#NexiaGP", "#Canarias", "#B2B"]
        if brief.get("sector") and brief["sector"].lower() not in {"canarias", "general"}:
            hashtags.append("#Distribucion")
        hook1 = WriterService._hook_for(brief)
        hook2 = "Tener buen producto ayuda. Pero no sustituye el criterio de canal."
        topic = request.get("tema_libre") or brief.get("core_angle", "")
        evidence = WriterService._evidence_sentence(topic, retrieval)
        final_post = "\n\n".join(
            [
                hook1,
                brief.get("core_thesis", ""),
                f"En este caso, la idea central es clara: {topic}.",
                evidence,
                "Por eso Nexia GP trabaja como partner comercial-tecnico: conecta fabricantes, distribuidores y clientes empresariales desde una vision practica del mercado canario.",
                "La diferencia no esta en hacer mas ruido. Esta en desarrollar mercado con orden, contexto y continuidad.",
            ]
        )
        cta = WriterService._cta(brief.get("cta_type", "comentario"))
        return {
            "meta": {
                "channel": brief.get("channel", "linkedin"),
                "post_type": brief.get("post_type", "educativo_autoridad"),
                "pillar": brief.get("pillar", ""),
                "audience": brief.get("audience", "mixta"),
                "objective": brief.get("objective", "autoridad"),
            },
            "strategy": {
                "core_angle": brief.get("core_angle", ""),
                "core_thesis": brief.get("core_thesis", ""),
                "why_it_matters": brief.get("why_it_matters", ""),
                "risk_notes": brief.get("risk_notes", []),
            },
            "copy": {
                "hook_option_1": hook1,
                "hook_option_2": hook2,
                "final_post": final_post,
                "cta": cta,
                "hashtags": hashtags[:4],
            },
            "editorial_support": {
                "reactivation_comment_8_24h": "Un matiz importante: en Canarias, la continuidad comercial suele pesar tanto como la entrada inicial.",
                "visual_brief": "Imagen sobria de canal profesional en Canarias: fabricante, distribuidor y soporte tecnico conectados por Nexia.",
                "human_review_notes": ["Version local generada con contexto disponible; revisar si se mencionan marcas o hechos concretos."],
            },
            "traceability": {
                "source_titles_used": source_titles[:8],
                "source_entities_used": source_entities[:6],
                "confidence": retrieval.get("confidence", "medium"),
            },
        }

    @staticmethod
    def _hook_for(brief: dict) -> str:
        post_type = brief.get("post_type")
        if post_type == "marca_propuesta_valor":
            return "Hay una diferencia importante entre vender producto y desarrollar mercado."
        if post_type == "fabricante_colaborador":
            return "Una marca no encaja en un mercado solo por tener buen producto."
        if post_type == "proyecto_prescripcion":
            return "En proyecto, la entrada no se decide solo en el catalogo."
        if post_type == "servicio_proceso_operativa":
            return "La operativa tambien posiciona una marca."
        if post_type == "actualidad_lectura_mercado":
            return "La actualidad solo importa si deja una lectura util para el canal."
        if post_type == "sector_solucion":
            return "Una solucion funciona mejor cuando entiende el canal donde debe rotar."
        return "Muchos fabricantes creen que entrar en Canarias es cuestion de producto. Normalmente no lo es."

    @staticmethod
    def _cta(cta_type: str) -> str:
        mapping = {
            "contacto": "Si quieres contrastar el encaje de una marca en Canarias, hablemos.",
            "comentario": "Que otros factores crees que pesan al desarrollar mercado en Canarias?",
            "visita_showroom": "Si eres distribuidor o cliente profesional, podemos valorar una visita con cita previa.",
            "mas_info": "Podemos ampliar la conversacion con mas contexto si tiene sentido para tu canal.",
            "sin_cta_directa": "",
        }
        return mapping.get(cta_type, mapping["comentario"])

    @staticmethod
    def _evidence_sentence(topic: str, retrieval: dict) -> str:
        text = " ".join(source.get("excerpt", "") for source in retrieval.get("sources", [])[:4]).lower()
        topic_low = topic.lower()
        if any(word in topic_low for word in ["reposicion", "logistica", "stock"]):
            if "almac" in text or "reposici" in text:
                return "La documentacion de Nexia permite apoyar esta lectura: la reposicion, el seguimiento y la coordinacion logistica no son detalles administrativos; reducen friccion comercial y ayudan a sostener la confianza del canal."
            return "La reposicion y la coordinacion logistica no son detalles administrativos; reducen friccion comercial y ayudan a sostener la confianza del canal."
        if any(word in topic_low for word in ["showroom", "exhibicion"]):
            return "Un showroom B2B no funciona como escaparate aislado: sirve para facilitar decisiones profesionales, acercar producto y reforzar la relacion con el distribuidor."
        if any(word in topic_low for word in ["prescripcion", "proyecto", "obra", "hotel"]):
            return "En proyectos, el valor aparece cuando la parte tecnica, la distribucion y la disponibilidad comercial se coordinan desde el principio."
        if any(word in topic_low for word in ["fabricante", "marca", "colaborador"]):
            return "Para una marca, entrar acompanada en Canarias ayuda a leer mejor canales, distribuidores y oportunidades reales antes de convertir presencia en simple exposicion."
        return "En un mercado insular, el encaje no depende solo de la propuesta tecnica. Tambien importan la red de distribuidores, la lectura local, el soporte y la capacidad de acompanar la implantacion con criterio."
