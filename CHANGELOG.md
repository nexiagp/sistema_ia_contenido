# Changelog — Nexia GP Social AI

Formato: por sesion y por fase. Cada entrada referencia el commit (`git log`).

---

## Sesion 4 — 2026-06-30 — Auditoria + Fases 0, 1 y 2

Auditoria completa (Product Manager + experto en redes B2B) y tres fases de mejora implementadas,
verificadas y commiteadas. 9 commits en `main`.

### Auditoria (sin commit — diagnostico)
Tres tracks en paralelo (backend, frontend/UX, calidad de contenido) + verificacion manual.
Hallazgos clave confirmados con datos reales:
- Seguridad: claves en `.txt` dentro de OneDrive, `.gitignore` incompleto, sin auth.
- Integridad: race conditions (lost-update) en `db.json` flat-file, sin git, sin backups.
- Retrieval infrautilizado: la KB sectorial (34 PDFs) llevaba sin subir desde la sesion 3.
- Contenido: hooks clonicos (4/5 iguales), versiones de X a 428-554 chars (>280), Facebook
  calcado de LinkedIn, hashtags de marca inconsistentes, voz intercambiable.
- Falso positivo corregido: los modelos `gpt-5.4-mini`/`gpt-image-2` SI existen y funcionan
  (probado por `responseIds` reales e imagenes generadas).

### Fase 0 — Depurar

**`8dec1e8` chore: repo inicial + depuracion de seguridad y prompts**
- `git init` + primer commit en `main`; identidad `Sergio GP <sergio@sergiogp.com>`.
- `.gitignore` blindado (secretos, datos pesados/transitorios). 0 secretos en el repo.
- `requirements.txt` (Pillow; resto libreria estandar).
- Prompt de X (`adaptacion_x_v1`): limite duro de 280 caracteres por pieza + tono mas directo.
- Prompt base (`base_global_v1`): hashtag de marca unico `#NexiaGP`, tildes consistentes,
  CTA orientada a comentarios.

**`1f72a9c` fix: el importador local ahora detecta la KB externa**
- `list_local_documents()` ahora escanea `data/uploads/kb-externa/` y asigna categoria por sector
  (antes solo miraba `Documentacion Nexia` y el docx -> la KB nunca se importaba).
- `scripts/upload_kb.py`: subida resumible al Vector Store (guarda db.json por archivo, salta los ya
  subidos, solo toca categorias `kb-*`, apunta a los PDFs existentes sin duplicar en disco).

**`14a3713` data: sube la KB sectorial (34 PDFs de Canarias) al Vector Store**
- 34 PDFs subidos a `vs_69e91ba9...`, 0 fallidos. Categorias: kb-economia (8), kb-fiscal (6),
  kb-turismo (5), kb-logistica (3), kb-industria (4), kb-demografia (4), kb-digital (3),
  kb-garden (1). `db.files` pasa de 12 a 46.

### Fase 1 — Afinar + Ampliar (calidad de contenido)

**`ba97415` feat(calidad): anti-repeticion, X<=280, hashtags, completitud**
- `src/ai/services/context_helpers.py` (NUEVO): helpers puros y testeados
  (`recent_openings`, `recent_angles`, `normalize_hashtags`, `clip_text`).
- Anti-repeticion: planner y writer reciben los hooks/angulos recientes + prohibicion del patron
  clonico "En Canarias, una buena X no basta".
- X <= 280: `adaptation_service` con re-prompt acotado + clip determinista de seguridad.
- Facebook real: guarda de similitud Jaccard que reescribe si es calco de LinkedIn + prompt reforzado.
- Hashtags: `normalize_hashtags` aplicado en el pipeline (#NexiaGP unico, dedup, cap 6).
- Completitud: el pipeline garantiza adaptaciones X+Facebook (nunca `{}`).
- Validador: comprueba hashtag de marca y apertura no clonica.

**`fe09c98` feat(voz): punto de vista y vocabulario propio de Nexia**
- `base_global_v1.txt`: bloque de convicciones ROTATORIAS (varias para no repetir) + vocabulario
  de marca + registro propio. Ataca la "voz intercambiable".

**`59c05bb` feat(formatos): 4 nuevos tipos de post de alto engagement**
- 4 prompts nuevos redactados y revisados de forma adversarial (workflow de 8 agentes):
  `founder_pov`, `social_proof_caso`, `encuesta_pulso`, `dato_opinion`.
- Cableado completo: `domain/editorial.py` (POST_TYPES), `prompt_service` (POST_TYPE_PROMPTS +
  PROMPT_REGISTRY), enum de `planner.schema.json`. La UI los recoge sola. 11 tipos coherentes en
  todas las capas; smoke-test del pipeline OK para los 4.

### Fase 2 — Producto y operacion de contenido

**`f5826a0` feat(integridad+coste): escrituras atomicas + registro de tokens**
- `transaction()` (context manager) + `DB_LOCK` -> RLock. Patron "snapshot lento + persistencia
  atomica del delta" en todos los handlers largos/concurrentes (editorial, blog, imagenes,
  scheduler, mutaciones). Fin del lost-update.
- Coste: `OpenAIClient` acumula `usage`; el pipeline lo adjunta al post; `record_usage` agrega en
  `db.usageStats`; expuesto en `/api/state`.
- Edicion inline (backend): `PATCH /api/posts/:id` ahora edita copy/cta/hashtags/title
  (`apply_post_edits` sincroniza las 3 capas y normaliza hashtags).
- Verificado: py_compile + tests de transaccion, apply_post_edits, record_usage, patch_blog,
  seguridad ante 404 y camino editorial completo en fallback.

**`68ad85f` feat(ux): edicion inline, filtros/busqueda, metrica de tokens, foco accesible**
- Edicion inline en la UI (textarea + inputs, Guardar/Cancelar, marca "editado").
- Filtros por estado + buscador en Posts; lista en `#postsList` -> el buscador no pierde foco.
- Metrica de "Tokens" en la banda superior.
- `styles.css`: chips, buscador, formulario de edicion, `:focus-visible` global (accesibilidad).
- `.claude/launch.json` para previsualizar (`python server.py` en :8787).
- Verificado en navegador real: 0 errores de consola; filtro Listos -> 1; busqueda inexistente ->
  vacio; edicion abre formulario poblado; PATCH normaliza `#NexiaGrowthPartner` -> `#NexiaGP`.

**`25ff27b` feat(ux): export CSV/JSON, preview por canal, filtros en Blogs**
- Export CSV / JSON del conjunto filtrado (client-side, BOM para Excel).
- Preview por canal: mockups de feed LinkedIn / X / Facebook con contador; X marca N/280 en rojo
  si excede (hace visibles las adaptaciones X antiguas que superaban el limite).
- Filtros + busqueda en Blogs (mismo patron que Posts, lista en `#blogList`).
- Verificado en navegador real: CSV con cabecera + 5 filas; preview con 3 tarjetas y aviso
  428/280; filtro de blogs (ready -> vacio, busqueda 'logistica' -> 1).

### Pendiente tras la sesion 4
- Acciones manuales de seguridad (rotar claves, borrar `.txt`, sacar de OneDrive).
- Publicacion/programacion real (LinkedIn API o Buffer/Metricool) + calendario editorial.
- Descargar el OTLE y completar la KB.
