# Changelog — Nexia GP Social AI

Formato: por sesion y por fase. Cada entrada referencia el commit (`git log`).

---

## Sesión 8 — 2026-08-24 — Migración cloud, continuidad y control de versiones

- La aplicación de contenido se despliega en Vercel (`nexiagp-content`) y conserva acceso directo
  mediante su URL de producción.
- Supabase pasa a ser el sistema persistente: estado editorial transaccional, biblioteca de fuentes,
  imágenes editoriales y activos de marca. Se migró el estado y se verificó la integridad remota.
- La generación de imágenes se adapta a Vercel: usa `/tmp/nexiagp-images` sólo como paso temporal,
  valida/compone el PNG y lo persiste inmediatamente en Supabase. Se corrigió el fallo de sistema
  de archivos de solo lectura y se regeneró con éxito la imagen pendiente.
- Se creó y publicó el repositorio `nexiagp/sistema_ia_contenido`; `main` está conectado a Vercel
  con despliegue automático. El repositorio público excluye secretos, backups, estado vivo y
  documentación interna.
- Se añade `docs/ARQUITECTURA_Y_OPERACION.md` como guía vigente de operación y recuperación.

---

## Sesión 7 — 2026-08-22 — Cierre editorial, PNG y calendario de ocupación

**Estado de esta entrada:** cambios locales verificados en Chrome y por suite offline; no hay
commit ni despliegue. El handoff vigente está en
`Documentación Nexia/2026-08-cierre-pre-entrega.md`.

### Posts e imagen

- La bandeja conserva la lista plegada, pero el detalle se convierte en una mesa de revisión:
  copy a la izquierda, pieza visual a la derecha y controles de imagen recogidos. Las imágenes usan
  `contain`, no un recorte estrecho; el modal muestra la pieza completa.
- La dirección visual pasa a decisiones editoriales explícitas: intención, encuadre, formato y
  calidad. El contrato de prompt prioriza una escena fotográfica única y excluye collages, texto,
  mapas, planos, diagramas y clichés de stock.
- Cada post puede conservar y comparar hasta cinco variantes sin perder el activo anterior.
  El activo seleccionado, sus variantes y las figuras de blog incluyen **Descargar PNG**, que baja
  el binario final sin canvas ni recompresión.

### Blogs y calendario

- Blogs se seleccionan desde tarjetas; el detalle mantiene la vista previa y ordena debajo SEO,
  enfoque/brief, JSON-LD e imágenes como controles bajo demanda. SEO ahora se entiende como ficha
  de resultado y el JSON bruto solo se abre cuando hace falta.
- El calendario separa candidatos de post (con miniatura y extracto) y blog (lista editorial
  compacta), permitiendo reservar día y hora antes de añadirlos. `PATCH /api/blogs/:id` admite
  `scheduledFor` y aplica la misma puerta de revisión que los posts.
- La agenda editorial abre en vista mensual: ocupa y diferencia días con piezas, deja huecos
  explícitos, permite navegar meses y pulsar un día para ver detalle. La vista de lista permanece
  como alternativa. Se corrigió el desbordamiento del CTA de los blogs.

### Mantenimiento y verificación

- `index.html` versiona CSS/JS para evitar mezclas de caché tras las mejoras visuales.
- Se añadieron contratos offline para dirección visual, calidad/contenido, imágenes y programación
  de blogs; el conjunto actual suma 17 pruebas. La comprobación se hace en Chrome, no en la vista
  previa integrada.
- README, estado maestro y documentación se sincronizan con las cifras de datos de este cierre.

---

## Sesión 6 — 2026-08-22 — Auditoría de entrega, trazabilidad y quality gates

**Estado de esta entrada:** cambios locales verificados; no hay commit ni despliegue.

### Calidad, fuentes y coste

- Nuevo `content_quality.py`: reconciliación determinista de fuentes, compactación de contexto,
  gate editorial, sanitización HTML de blogs, validación de SEO/JSON-LD y checks de estructura.
- `RetrievalService` usa `POST /vector_stores/{id}/search` y mapea `file_id`/nombre/atributos al
  catálogo local. Se elimina la dependencia de una lista de fuentes descrita por el modelo.
- Las fuentes desconocidas se excluyen y los fragmentos de un mismo archivo se agrupan. Tipos
  factuales exigen revisión humana y, para `dato_opinion`, evidencia sectorial/oficial catalogada.
- Writer, validator y adaptador reciben payloads compactos. Prueba final: 12.901 tokens / 4
  llamadas frente a 22.767 / 5 en la primera prueba (−43 %).
- `OpenAIClient` y el endpoint heredado de Responses aplican `store:false`.

### Revisión editorial y blogs

- `qualityGate` bloquea pasar posts/blogs a listo, programado o publicado hasta que la persona
  revisora confirma explícitamente la lectura; la edición posterior revoca esa confirmación.
- El scheduler conserva borradores bloqueados aunque se active un modo de salida futuro.
- HTML de blogs restringido a una lista permitida; se eliminan scripts, eventos, iframes, URLs
  JavaScript y falsas descargas de lead magnet. JSON-LD se normaliza antes de exportar.
- Rango de longitudes de blog alineado con dominio (800–1200 / 1500–2200 / 2500–3500), frameworks
  de UI corregidos y texto de 11 tipos de post corregido.

### Seguridad, UX y pruebas

- Rutas estáticas con comprobación de pertenencia real, límite JSON de 1 MB, uploads acotados a
  50 MB y tipos documentales permitidos, MIME JPEG correcto y errores internos sin detalle al
  navegador.
- Métrica de tokens corregida (no vuelve a mostrar `NaN`).
- Se amplía `Pillow` a `>=10,<13`, compatible con la versión 12.3 validada.
- Nueva suite `test_content_quality.py`; total de 12 pruebas offline correctas, compilación Python,
  sintaxis JS, traversal 404 y JSON inválido/sobredimensionado 400/413 comprobados.
- Pruebas reales, siempre en borrador: cuatro posts y una imagen PNG 1536×1024 con marco NGP y
  distribución Cloudinary. El post histórico que seguía en `ready` se baja a `draft` por revisión
  pendiente; no se borra contenido ni se publica nada.

Informe de evidencia y pendientes: `Documentación Nexia/2026-08-auditoria-de-entrega.md`.

---

## Sesión 5 — 2026-08-16 — Entrega, control operativo e imagen fiable

**Estado de esta entrada:** cambios locales verificados, todavía sin commit ni despliegue.

### Imagen, logo y coste

- `image_service.py` refactorizado como frontera estricta de generación: tres tamaños admitidos
  por `gpt-image-2`, calidades permitidas, prompt de producción sin texto/marcas, dos intentos
  recuperables, inspección de PNG con Pillow y persistencia atómica.
- `frame_composer.py` aplica el logo aprobado localmente, verifica el PNG final y no deja un
  compuesto parcial. Cloudinary pasa a ser solo distribución del activo ya marcado.
- Posts y figuras de blog guardan `displayUrl`, validación y configuración coherentes incluso sin
  Cloudinary; ya no dependen de una transformación CDN para mostrar marca correcta.
- Coste real preventivo en figuras de blog: `costTargetCents` bloquea antes de pedir una imagen si
  el total estimado superaría el presupuesto. Las estimaciones se conservan por figura y se
  reconstruyen desde configuraciones antiguas cuando es posible.
- Añadido `test_image_service_offline.py`: contrato de formatos/calidades, prompt seguro, PNG
  válido, fallo sin residuo, marco/logo y publicación bloqueada sin webhook (6/6 correcto).

### Producto y operación

- Nuevos trabajos locales en segundo plano para posts y blogs (`/api/jobs/editorial`,
  `/api/jobs/blog`, `/api/jobs/:id`) con progreso por etapas reales, sondeo desde la SPA y prueba
  aislada de ciclo de vida sin OpenAI.
- `BlogPipeline` ahora devuelve uso de tokens, por lo que blog también actualiza `usageStats`.
- Añadida vista de **Calendario**: programación interna mediante `scheduledFor` UTC y estado
  `scheduled`, sin representar falsamente que se ha publicado en redes.
- Publicación manual rechazada sin `SOCIAL_WEBHOOK_URL` y modo `auto` degradado a revisión cuando
  no existe una integración social. Biblioteca ampliada con filtros, búsqueda y estados legibles.

### Interfaz de entrega

- Corrección global de SVG de controles, métricas de seis tarjetas equilibradas, blog menos
  comprimido y menú móvil colapsable.
- Vista Posts rehecha como bandeja de revisión compacta: cada tarjeta inicia cerrada; la pieza
  completa, fuentes y acciones se muestran solo al abrirla.
- Eliminado el encabezado teal/verde grande de las tarjetas. Titulares reducidos, fondo blanco,
  resumen truncado y acento usado únicamente con valor funcional.
- Imagen de post reducida a miniatura dentro del detalle y ampliación explícita por diálogo modal.
  No se muestran imágenes de tamaño completo antes de solicitarlas.

### Investigación y documentación

- Catálogo de fuentes oficiales de Canarias en
  `Documentación Nexia/Fuentes Oficiales/2026-08-fuentes-oficiales-canarias.md`.
- Propuesta de vídeo API de 8 s, todavía sin endpoint ni coste activado, en
  `Documentación Nexia/2026-08-plan-video-api.md`.
- Handoff técnico completo de la sesión en
  `Documentación Nexia/2026-08-entrega-y-continuidad.md`.

### Verificación realizada

- `node --check public/app.js` sin errores.
- `python -m py_compile` para servidor y pipelines sin errores.
- `python test_image_service_offline.py`: 6 pruebas correctas.
- App local comprobada con `GET /api/health`, en escritorio y móvil, sin errores/avisos de consola.
- No se ejecutó ninguna llamada que consumiera OpenAI, sincronización ni publicación.

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
