from __future__ import annotations

from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import base_prompt, schema, transformer_prompt


class AdaptationService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def adapt(self, generation: dict, validation: dict, db: dict) -> tuple[dict, str | None]:
        if self.client.enabled:
            try:
                user = (
                    "Adapta el post canonico validado de Nexia GP a X y Facebook.\n"
                    f"Post canonico: {validation.get('final_post')}\n"
                    f"CTA: {validation.get('cta')}\n"
                    f"Hashtags: {validation.get('hashtags')}\n"
                    f"Contexto de salida original: {generation}"
                )
                system = "\n\n".join(
                    [
                        base_prompt(),
                        transformer_prompt("adaptacion_x"),
                        transformer_prompt("adaptacion_facebook"),
                    ]
                )
                return self.client.responses_json(
                    system=system,
                    user=user,
                    schema=schema("adaptation.schema.json"),
                    schema_name="nexiagp_adaptations",
                    model=db.get("settings", {}).get("model") or None,
                )
            except Exception:
                return self._fallback_adapt(validation), None
        return self._fallback_adapt(validation), None

    @staticmethod
    def _fallback_adapt(validation: dict) -> dict:
        post = validation.get("final_post", "")
        paragraphs = [part.strip() for part in post.split("\n\n") if part.strip()]
        hook = paragraphs[0] if paragraphs else post[:180]
        thesis = paragraphs[1] if len(paragraphs) > 1 else "El desarrollo comercial necesita criterio de canal, no solo producto."
        x_short = f"{hook}\n\n{thesis[:190]}"
        thread = [hook, thesis[:240], "En Canarias, el encaje comercial se construye con red local, soporte y continuidad."]
        facebook = "\n\n".join(
            [
                hook,
                "La idea es sencilla: crecer en un mercado como Canarias requiere entender el canal, acompanar la implantacion y trabajar con criterio B2B.",
                validation.get("cta") or "Si tiene sentido para tu empresa, podemos abrir conversacion.",
            ]
        )
        return {
            "x": {
                "short_version": x_short[:280],
                "alternative": "Entrar en un mercado no es solo llegar. Es entender el canal, sostener la operativa y construir confianza.",
                "thread": thread[:3],
            },
            "facebook": {
                "final_post": facebook,
                "cta": validation.get("cta", ""),
            },
        }
