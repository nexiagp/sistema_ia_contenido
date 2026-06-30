# Nexia GP Social AI

Sistema editorial local para generar posts de LinkedIn y adaptaciones a X/Facebook para Nexia Growth Partner usando Responses API, `file_search` y Vector Stores.

## Continuidad del proyecto

El estado actual para retomar el desarrollo esta documentado en `PROJECT_STATE.md`. Incluye arquitectura, Vector Store activo, endpoints, comandos de arranque, reglas para no consumir tokens accidentalmente y notas sobre la UI de revision editorial.

## Arranque

1. Crea un archivo `.env` a partir de `.env.example`.
2. Añade `OPENAI_API_KEY`.
3. Ejecuta con Python:

```powershell
python server.py
```

Tambien puedes usar Node si lo tienes disponible:

```powershell
node server.js
```

4. Abre `http://localhost:8787`.

## Que incluye

- Pipeline editorial multi-step: planner -> retrieval -> writer -> validator -> adaptadores.
- 1 prompt base, planner, validator, 7 prompts maestros y 2 transformadores versionados en `src/ai/prompts`.
- Schemas JSON en `src/ai/schemas`, incluyendo `schema_salida_nexiagp.json`.
- Servicios separados en `src/ai/services` para OpenAI, retrieval, planner, writer, validator y adaptacion.
- UI para canal, tipo de post, audiencia, objetivo, sector, marca/tema, CTA, nivel promocional y notas humanas.
- Brief estrategico visible, fuentes usadas, flags de revision, hooks alternativos y comentario de reactivacion 8-24h.
- Adaptacion multicanal a X y Facebook.
- Biblioteca documental con subida a OpenAI Files y asociacion a Vector Store.
- Scheduler local por cadencia de dias mientras el servidor este activo.
- Modo local si no hay `OPENAI_API_KEY`, con retrieval basico sobre documentos `.txt`/`.md`.

## Estructura editorial

```text
src/ai/prompts/
  base_global_v1.txt
  planner_v1.txt
  validator_v1.txt
  post_types/*.txt
  transformers/*.txt

src/ai/services/
  openai_client.py
  retrieval_service.py
  planner_service.py
  writer_service.py
  validator_service.py
  adaptation_service.py
  pipeline_service.py
```

## Publicacion automatica

Si defines `SOCIAL_WEBHOOK_URL`, el servidor enviara el post en JSON a ese webhook cuando el modo sea automatico. Sin webhook, los posts automaticos quedan como `ready` para revision.
