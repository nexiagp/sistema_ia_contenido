# Nexia GP Social AI — Estado de continuidad

**Fecha de referencia: 2026-06-30**
**Ultima sesion documentada: Sesion 4 (30/06/2026) — Auditoria + Fases 0, 1 y 2**

Este archivo es la fuente de verdad del proyecto. Leerlo SIEMPRE antes de retomar trabajo.

---

## PUNTO ACTUAL DEL PROYECTO

El sistema esta operativo y completo en sus pilares principales, y en la sesion 4 se hizo una
auditoria completa (PM + experto en redes) seguida de tres fases de mejora ya implementadas,
verificadas y commiteadas:

1. **Generacion de posts** para LinkedIn/X/Facebook — funcional, con imagenes, prompts editables.
2. **Generacion de articulos de blog** — funcional, con imagenes ligeras, preview fiel al sitio web.
3. **Knowledge Base externa** — **SUBIDA**: 34 PDFs sectoriales de Canarias ya en el Vector Store.

**Lo que falta ahora mismo (unico gran pendiente de producto):**
- **Publicacion / programacion real** a redes (LinkedIn API o Buffer/Metricool). Hoy solo hay un
  stub por webhook (`SOCIAL_WEBHOOK_URL`). Requiere decision de plataforma + credenciales OAuth.
- **Calendario editorial** visual (asociado a la publicacion).
- Acciones manuales de seguridad pendientes (ver seccion Seguridad).

---

## Git y control de versiones

- El proyecto **ya es un repositorio git** (antes no lo era). Rama: `main`.
- `.gitignore` blindado: excluye `.env`, claves en `.txt`, backups `data/db.backup-*.json`,
  cache, `data/uploads/`, browser-profiles y capturas pesadas.
- Identidad de commits usada: `Sergio GP <sergio@sergiogp.com>`.
- **Historial (9 commits, sesion 4)** — ver `CHANGELOG.md` para el detalle:
  ```
  25ff27b feat(ux): export CSV/JSON, preview por canal y filtros en Blogs
  68ad85f feat(ux): edicion inline, filtros/busqueda, metrica de tokens, foco accesible
  f5826a0 feat(integridad+coste): escrituras atomicas en db.json y registro de tokens
  59c05bb feat(formatos): 4 nuevos tipos de post de alto engagement
  fe09c98 feat(voz): punto de vista y vocabulario propio de Nexia en el prompt base
  ba97415 feat(calidad): anti-repeticion de hooks, X<=280, hashtags de marca, completitud
  14a3713 data: sube la KB sectorial (34 PDFs de Canarias) al Vector Store
  1f72a9c fix: el importador local ahora detecta la KB externa (kb-externa)
  8dec1e8 chore: repo inicial + depuracion de seguridad y prompts
  ```

---

## Seguridad — ACCIONES MANUALES PENDIENTES (solo las puede hacer el usuario)

La sesion 4 detecto que las claves estaban en texto plano dentro de una carpeta **OneDrive**
(se sincronizan a la nube de Microsoft). Se eliminaron del control de versiones, pero:

1. **Rotar TODAS las claves** (OpenAI y Cloudinary): asumirlas comprometidas.
2. **Borrar manualmente** `API Key Project.txt` y `API CLOUDINARY.txt` de la raiz (ya estan en
   `.gitignore`, pero siguen en disco; el borrado quedo pendiente del usuario).
3. **Sacar el proyecto de OneDrive** o excluir `.env` y secretos de la sincronizacion.

Otras notas de seguridad (deuda conocida, no bloqueante en uso local mono-usuario):
- El servidor **no tiene autenticacion** (bindea a `localhost`). No exponerlo en red sin token.
- Inputs de usuario van directos a los prompts (riesgo teorico de prompt injection en local).

---

## App actual

- Aplicacion local para generar posts de LinkedIn (con adaptaciones a X y Facebook) y articulos
  de blog para Nexia Growth Partner.
- Servidor canonico: `server.py` (Python `ThreadingHTTPServer` + `SimpleHTTPRequestHandler`).
- URL local: `http://localhost:8787`.
- Vistas principales (SPA en JS vanilla):
  - `#generator` — formulario de generacion de posts (pipeline editorial).
  - `#posts` — revision editorial de posts **con filtros, busqueda, edicion inline, export y
    preview por canal** (nuevo en sesion 4).
  - `#blogs` — creacion y revision de articulos de blog **con filtros y busqueda** (nuevo).
  - `#library` — biblioteca de archivos y Vector Store.
  - `#strategy` (Tematicas) — informativo de tipos/prompts.
  - `#automation` — scheduler por cadencia.
  - `#settings` — ajustes (General / Posts / Blog / Prompts).
- La clave API esta en `.env`; no imprimirla ni moverla a archivos versionables.

---

## Estado de datos (db.json)

- 5 posts (4 draft, 1 ready) — todos con imagenes generadas. Sirven de muestra; NO borrar.
- 2 blogs (ambos draft) — ambos con imagenes generadas.
- **46 archivos** sincronizados con el Vector Store: 12 (web + copywriting de Nexia) + **34 de la
  KB externa sectorial** (subidos en sesion 4).
- 0 overrides de prompt (los `.txt` estan activos; `prompt_overrides` y `prompt_versions` vacios).
- **`usageStats`** (nuevo): acumulado de tokens por generacion (`generations`, `calls`,
  `input_tokens`, `output_tokens`, `total_tokens`).
- Almacenamiento: JSON flat-file local (`data/db.json`). NO Supabase.
- **Escrituras atomicas** (nuevo): todo read-modify-write pasa por `transaction()` con un unico
  lock (ver seccion Integridad). `write_db` sigue siendo atomico a nivel de fichero (`.tmp`+replace).

---

## OpenAI

- Modelo de texto: `gpt-5.4-mini` (Responses API). Modelo de imagen: `gpt-image-2`.
  **IMPORTANTE: ambos modelos SON reales y funcionan** (probado por `responseIds` reales y por las
  imagenes generadas). Auditorias con corte de conocimiento antiguo los marcan por error como
  "inexistentes": es un falso positivo, NO cambiarlos.
- Vector Store activo: `vs_69e91ba9d27c819197a522a6a07dae20` (Nexia GP Knowledge Base), ya con web +
  copywriting + KB sectorial (46 archivos).
- El cliente ignora proxies heredados invalidos via `urllib.request.ProxyHandler({})`.
- **Registro de coste** (nuevo): `OpenAIClient` acumula `usage` por instancia; el pipeline lo
  adjunta a cada post; `record_usage()` lo suma en `db.usageStats`.

---

## Cloudinary

- Dos variantes por imagen: `rawUrl` (sin overlay, blog) y `brandedUrl` (con logo, posts).
- Cuenta: `dg3peytgm`, carpetas `nexiagp/posts/` y `nexiagp/blogs/`.

---

## Knowledge Base externa (KB) — SUBIDA (sesion 4)

- **34 PDFs sectoriales de Canarias** subidos al Vector Store, con **categoria por sector**:
  `kb-economia` (8), `kb-fiscal` (6), `kb-turismo` (5), `kb-logistica` (3), `kb-industria` (4),
  `kb-demografia` (4), `kb-digital` (3), `kb-garden` (1).
- Origen en disco: `data/uploads/kb-externa/` (sin tocar; el script apunta a esos PDFs sin duplicar).
- Subida hecha con `scripts/upload_kb.py` (resumible: guarda db.json por archivo, salta los ya
  subidos). El endpoint/boton de la app tambien funciona ya (ver fix abajo).
- **Pendiente (no bloqueante):** falta 1 doc, el **OTLE Informe Anual 2024** (logistica), bloqueado
  por anti-bot. Descargar manualmente a `data/uploads/kb-externa/D-logistica/` y re-ejecutar
  `python scripts/upload_kb.py` (subira solo ese).
- **Fix asociado:** `list_local_documents()` antes NO escaneaba `data/uploads/kb-externa/` (solo
  `Documentacion Nexia` y el docx), por lo que el "Importar local" documentado no funcionaba.
  Corregido: ahora detecta la KB y asigna categoria sectorial.

---

## Arquitectura editorial — Posts

Flujo multi-step (`src/ai/services/pipeline_service.py`):
1. `planner` — decide tipo, audiencia, objetivo, brief. **Recibe los hooks y angulos recientes para
   no repetir** y prohibe el patron clonico "En Canarias, una buena X no basta" (anti-repeticion).
2. `retrieval` — busca en el Vector Store (ahora con datos sectoriales reales de la KB).
3. `writer` — genera el post. **Tambien recibe las aperturas recientes a evitar.**
4. `validator` — valida calidad, riesgos, marca. Comprueba hashtag unico #NexiaGP y apertura no clonica.
5. Adaptadores multicanal X y Facebook con **guardas deterministas** (ver Calidad de contenido).

Tras el pipeline, en `pipeline_service.run`: se **normalizan los hashtags** (`#NexiaGP` unico,
dedup, max 6) y se garantiza la **completitud** de adaptaciones (nunca `{}` vacio).

---

## Arquitectura editorial — Blog

Flujo: `blog_planner` -> `retrieval` -> `blog_writer` (HTML semantico, CTA fija "¿Comenzamos? ·
Contactar") -> `seo_reviewer` -> generacion de imagenes de figura. Settings en `settings.blog`
(`defaultModel`, `defaultLength`, `defaultFramework`, `defaultAudience`, `imagesPerArticle`,
`imageQuality`, `costTargetCents`).

---

## Calidad de contenido (mejoras de sesion 4)

Correcciones de los defectos verificados en la auditoria, cada una con **guarda de codigo
determinista + refuerzo de prompt** (porque "solo pedirlo" fallaba):

- **Anti-repeticion de hooks**: planner y writer reciben los hooks/angulos recientes
  (`context_helpers.recent_openings/recent_angles`) + prohibicion del patron clonico.
- **X <= 280**: `adaptation_service` re-prompt acotado + `clip_text` determinista de seguridad
  (antes las "versiones cortas" salian a 428-554 caracteres).
- **Facebook real**: guarda de similitud Jaccard que reescribe FB si es calco de LinkedIn.
- **Hashtags de marca**: `normalize_hashtags` colapsa variantes a `#NexiaGP`, dedup, cap 6.
- **Completitud**: el pipeline garantiza adaptaciones X + Facebook.
- **Voz de marca**: bloque de convicciones ROTATORIAS + vocabulario propio en `base_global_v1.txt`
  (para dejar de sonar a agencia intercambiable).

---

## Tipos de post (11) y prompts (19)

**11 tipos** en `src/domain/editorial.py` (POST_TYPES) y `prompt_service` (POST_TYPE_PROMPTS +
PROMPT_REGISTRY) y en el enum de `planner.schema.json`:

Originales (7): `marca_propuesta_valor`, `educativo_autoridad`, `sector_solucion`,
`fabricante_colaborador`, `proyecto_prescripcion`, `servicio_proceso_operativa`,
`actualidad_lectura_mercado`.

**Nuevos en sesion 4 (4 formatos de alto engagement)** — redactados y revisados de forma adversarial
por un workflow de 8 agentes:
- `founder_pov` — voz del fundador en 1a persona, conviccion abierta a debate.
- `social_proof_caso` — prueba social cualitativa (guardarrail anti-invencion de cifras/clientes).
- `encuesta_pulso` — encuesta nativa de LinkedIn con opciones de voto.
- `dato_opinion` — dato/senal del sector + tesis con postura (DATO -> TESIS -> CONSECUENCIA).

**19 prompts en PROMPT_REGISTRY**: 3 core (base/planner/validator) + 11 post types + 2 transformers
(X/Facebook) + 3 blog (planner/writer/seo). Editables desde Settings > Prompts, con versionado
append-only en `db.json` (override-aware: `prompt_overrides[name].text` tiene prioridad sobre el `.txt`).

---

## Integridad de datos (nuevo en sesion 4)

- `DB_LOCK` paso de `Lock` a `RLock` (reentrante).
- `transaction()` (context manager): mantiene un unico lock durante leer -> mutar -> escribir, para
  que dos peticiones concurrentes no se pisen (fin del *lost update*).
- Patron para handlers largos (generacion con OpenAI): el trabajo lento se hace sobre un snapshot
  `read_db()` y SOLO el delta se persiste en un `transaction()` corto (no se retiene el lock minutos).
- Convertidos: `run_editorial_pipeline`, `regenerate_editorial_post`, `generate_post_image`,
  `run_blog_pipeline`, `generate_blog_figure_image`, `generate_posts`, `run_scheduler` (daemon),
  `adapt_editorial_post`, `patch_blog`, `delete_blog`, y los handlers PATCH/DELETE/publish de posts.
- Deuda restante: `settings`/themes/post-types CRUD y `sync_files_to_openai` aun usan el patron
  read_db/write_db simple (bajo riesgo). Backups: hay copias `data/db.backup-*.json` (gitignoradas).

---

## UI — funcionalidades (sesion 4)

En `public/app.js` + `public/styles.css`:
- **Edicion inline de posts**: boton "Editar" -> textarea de copy + inputs de hashtags/CTA ->
  Guardar (PATCH /api/posts/:id) / Cancelar. Sincroniza campo plano + `generation.copy` +
  `validation` y normaliza hashtags. Marca "editado".
- **Filtros + busqueda** en Posts y Blogs (chips de estado + buscador). La lista vive en su propio
  contenedor (`#postsList` / `#blogList`) y solo se re-renderiza ella -> el buscador no pierde foco
  (paso hacia render incremental; el resto sigue siendo render por innerHTML).
- **Metrica de Tokens** en la banda superior (usa `usageStats`).
- **Export CSV / JSON** del conjunto filtrado (client-side).
- **Preview por canal**: mockups de feed LinkedIn / X / Facebook con contador de caracteres; X
  muestra N/280 y marca en rojo si excede.
- **`:focus-visible`** global (accesibilidad de teclado).
- Verificacion: la app se levanta con `.claude/launch.json` (Preview) — `python server.py` en :8787.

---

## Servicios principales

- `src/ai/services/openai_client.py` — cliente Responses API + **registro de usage**.
- `src/ai/services/context_helpers.py` — **NUEVO**: helpers puros (recent_openings, recent_angles,
  normalize_hashtags, clip_text). Testeables sin OpenAI.
- `src/ai/services/retrieval_service.py`, `planner_service.py`, `writer_service.py`,
  `validator_service.py`, `adaptation_service.py` (con guardas X-280 y FB), `pipeline_service.py`.
- `src/ai/services/prompt_service.py` — PROMPT_REGISTRY (19), POST_TYPE_PROMPTS (11), override-aware.
- `src/ai/services/blog_pipeline.py`, `blog_planner_service.py`, `blog_writer_service.py`,
  `blog_seo_service.py`.
- `src/ai/services/image_prompt_service.py`, `image_service.py`, `frame_composer.py` (Pillow),
  `cloudinary_service.py`.

Dependencias: **`requirements.txt`** (unica de terceros: Pillow). El resto es libreria estandar.

---

## Imagenes

### Posts
- Modelo `gpt-image-2` | 1344x768 (default) | calidad medium.
- Frame: blur strip + linea chocolate (Pillow) + logo NGP via Cloudinary (ON por defecto).

### Blog
- 1024x576 | calidad standard. Frame/overlay OFF por defecto (rawUrl). Figuras distribuidas en el HTML.

---

## Endpoints utiles

```
GET   /api/health                                — estado de clave, modelo, VS
GET   /api/state                                 — estado completo (incluye usageStats)

POST  /api/editorial/generate                    — genera post completo [CONSUME OPENAI]
POST  /api/editorial/posts/:id/regenerate        — regenera post [CONSUME OPENAI]
POST  /api/editorial/posts/:id/adapt             — regenera adaptaciones X/FB [CONSUME OPENAI]
POST  /api/posts/:id/generate-image              — genera imagen de post [CONSUME OPENAI]
PATCH /api/posts/:id                             — edita status Y copy/cta/hashtags/title (inline)
DELETE/api/posts/:id                             — elimina post
POST  /api/posts/:id/publish                     — publica (webhook stub si SOCIAL_WEBHOOK_URL)

POST  /api/blogs/generate                        — genera blog completo [CONSUME OPENAI]
POST  /api/blogs/:id/figures/:fid/generate-image — imagen de figura [CONSUME OPENAI]
PATCH /api/blogs/:id                             — actualiza estado/campos del blog
DELETE/api/blogs/:id                             — elimina blog

GET   /api/settings  · PATCH /api/settings
GET   /api/prompts   · GET/PUT /api/prompts/:id  · POST /api/prompts/:id/revert
POST  /api/files/upload · /api/files/import-local · /api/files/sync-openai · DELETE /api/files/:id
POST  /api/scheduler/run
```

(El export CSV/JSON es client-side, no endpoint.)

---

## Arranque

```powershell
python server.py
```

Abrir `http://localhost:8787`. Si el puerto esta ocupado:
```powershell
netstat -ano | findstr :8787
```

Tambien se puede previsualizar con el Preview de Claude Code (`.claude/launch.json`, nombre `nexiagp`).

---

## Verificacion sin consumir tokens

```powershell
# Salud del servidor
Invoke-RestMethod -Uri 'http://localhost:8787/api/health' | ConvertTo-Json -Depth 5

# Compilacion de modulos Python
python -m py_compile server.py (ver lista completa en sesiones anteriores)

# Sintaxis del frontend
node --check public/app.js
```

El pipeline completo se puede probar en **modo fallback** (sin OPENAI_API_KEY) para verificar las
guardas (anti-repeticion, X<=280, hashtags, completitud) sin coste.

---

## Reglas de continuidad

- **NO lanzar** endpoints que consuman OpenAI (`/api/editorial/generate`, `/api/blogs/generate`,
  imagenes, ni `sync-openai`) salvo peticion EXPLICITA del usuario.
- No borrar posts/blogs de muestra.
- No imprimir ni exponer la API key. Recordar las acciones de seguridad pendientes.
- Mantener prompts separados y versionados.
- Los modelos `gpt-5.4-mini` y `gpt-image-2` son reales; no "corregirlos".
- Al tocar la UI, no perder acciones existentes (copiar, editar, adaptar, regenerar, publicar,
  marcar listo, eliminar, filtrar, exportar, previsualizar).

---

## PROXIMOS PASOS — Por orden de prioridad

### 1. Acciones manuales de seguridad (usuario)
Rotar claves, borrar los `.txt` de secretos, sacar de OneDrive (ver seccion Seguridad).

### 2. Publicacion / programacion real (mayor salto de producto)
- Decidir plataforma: **LinkedIn API directa** vs **Buffer/Metricool** (agregadores).
- Implica OAuth + credenciales. Es lo unico que cierra la cadena de valor (hoy la app crea pero no
  publica). Asociar un **calendario editorial** visual.

### 3. Descargar el OTLE y completar la KB
Descargar el OTLE Informe Anual 2024 a `data/uploads/kb-externa/D-logistica/` y
`python scripts/upload_kb.py` (subira solo ese).

### 4. Pulido / deuda tecnica (opcional)
- SSE/progreso real durante la generacion (hoy spinner; los pasos no avanzan en vivo).
- Migrar `db.json` a SQLite si crece mucho (la transaccion atomica ya mitiga lo urgente).
- Tests automatizados (no hay suite).
- Aplicar `costTargetCents` como limite real usando `usageStats`.
- Historial de versiones del contenido de posts (como ya existe para prompts).

---

## Scripts utiles

```powershell
# Subir / completar la KB externa al Vector Store (resumible)
python scripts/upload_kb.py

# Re-descargar la KB externa (otra maquina)
python scripts/download_kb.py
```
