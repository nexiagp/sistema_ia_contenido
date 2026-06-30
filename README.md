# Nexia GP Social AI

Sistema editorial local para generar **posts de LinkedIn** (con adaptaciones a X/Facebook) y
**articulos de blog** para Nexia Growth Partner, usando la Responses API de OpenAI, `file_search`
y Vector Stores con conocimiento sectorial de Canarias.

## Continuidad del proyecto

El estado actual y la documentacion completa estan en:
- **`PROJECT_STATE.md`** — fuente de verdad: arquitectura, Vector Store, endpoints, integridad de
  datos, calidad de contenido, UI, acciones de seguridad pendientes y proximos pasos.
- **`CHANGELOG.md`** — historial de cambios por sesion y commit.

Leer `PROJECT_STATE.md` SIEMPRE antes de retomar el desarrollo.

## Arranque

1. Crea `.env` a partir de `.env.example` y añade `OPENAI_API_KEY` (y, opcional, las claves de
   Cloudinary y `SOCIAL_WEBHOOK_URL`).
2. Instala dependencias (unica de terceros: Pillow):

```powershell
python -m pip install -r requirements.txt
```

3. Ejecuta:

```powershell
python server.py
```

4. Abre `http://localhost:8787`.

> Seguridad: nunca versionar `.env` ni claves en `.txt`. Si el proyecto vive en OneDrive, excluye
> los secretos de la sincronizacion. Ver la seccion *Seguridad* de `PROJECT_STATE.md`.

## Que incluye

- **Pipeline editorial multi-step**: planner -> retrieval -> writer -> validator -> adaptadores,
  con anti-repeticion de hooks, enforcement de 280 caracteres en X, normalizacion de hashtags de
  marca y voz diferenciada.
- **11 tipos de post** (7 tematicos + 4 de formato: founder-led, prueba social, encuesta,
  dato+opinion) y **3 prompts de blog**, todos editables y versionados desde la UI.
- **Generacion de blog** con SEO serio (JSON-LD, OG, enlazado interno) y preview fiel a nexiagp.com.
- **Biblioteca documental** con subida a OpenAI Files y Vector Store (incluye 34 PDFs sectoriales de
  Canarias por categoria).
- **Operacion de contenido en la UI**: edicion inline, filtros y busqueda (posts y blogs), export
  CSV/JSON, preview por canal (LinkedIn/X/Facebook) y metrica de tokens.
- **Integridad**: escrituras atomicas en `db.json` (`transaction()`), sin lost-update.
- **Registro de coste** de tokens (`usageStats`).
- Scheduler local por cadencia mientras el servidor este activo.
- Modo local (fallback) si no hay `OPENAI_API_KEY`, util para verificar las guardas sin coste.

## Estructura

```text
server.py                      # servidor + endpoints + integridad (transaction)
public/                        # SPA: index.html, app.js, styles.css, blog-preview.css
src/ai/prompts/                # base, planner, validator, post_types/ (11), transformers/ (2), blog
src/ai/schemas/                # esquemas JSON de salida
src/ai/services/               # openai_client, context_helpers, pipeline, blog_pipeline, image, ...
src/domain/                    # editorial.py (POST_TYPES...), blog.py
scripts/                       # upload_kb.py (subida resumible de la KB), download_kb.py
data/                          # db.json (estado), uploads/ (KB), images/
requirements.txt               # Pillow
```

## Publicacion automatica (stub)

Si defines `SOCIAL_WEBHOOK_URL`, el servidor envia el post en JSON a ese webhook en modo automatico.
Sin webhook, los posts automaticos quedan como `ready` para revision. La **publicacion/programacion
real** a redes (LinkedIn API / Buffer / Metricool) esta pendiente — ver `PROJECT_STATE.md`.
