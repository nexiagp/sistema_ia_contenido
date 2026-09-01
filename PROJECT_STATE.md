# Nexia GP Content AI — Estado de continuidad

## Actualización vigente — 01/09/2026 — WordPress, acceso y continuidad

- **Producción:** `https://nexiagp-content.vercel.app` continúa en Vercel y está autenticada con
  Supabase (`NEXIAGP_AUTH_REQUIRED=1`). El proyecto Supabase operativo es
  `tdhbogzpnqvdcmhyrzkr`; no reemplazar su estado con una copia local.
- **Activos persistentes:** se completó la migración de las fuentes, documentos e imágenes
  históricos al Storage de Supabase. La función y el token de alcance limitado que se crearon sólo
  para esa migración fueron eliminados y revocados al finalizar.
- **WordPress:** la conexión con `nexiagp.com` está operativa mediante secretos de Vercel. Los
  artículos aprobados se suben con sus imágenes como borradores; el piloto dejó tres entradas en
  `draft`, sin ninguna publicación automática.
- **Incidencia resuelta:** el commit `f939324` evita que un recálculo de calidad elimine la
  aceptación editorial ya registrada justo antes de crear el borrador. Una edición de contenido
  sigue exigiendo una aprobación nueva, por diseño.
- **SEO:** Rank Math está instalado, pero sus campos no se exponen como metacampos REST editables.
  Cada borrador requiere revisar metatítulo, metadescripción y keyword en WordPress antes de
  publicar.
- **Documentación de relevo:** usar [Arquitectura y operación](docs/ARQUITECTURA_Y_OPERACION.md)
  para infraestructura y [Runbook de WordPress](docs/WORDPRESS_RUNBOOK.md) para el flujo diario.

La sección siguiente conserva la fotografía del 31/08/2026 como histórico; no describe el acceso
ni el flujo de WordPress actuales.

## Actualización vigente — 31/08/2026

- **Fuentes de fabricantes:** 20 webs oficiales están recuperadas, guardadas en Supabase de
  producción e indexadas en OpenAI. Altuna Group queda registrada pero pendiente de reintento por
  tiempo de espera de su web oficial; no contiene una fuente parcial.
- **Automatización:** scheduler activado, una pieza cada tres días y rotación circular de las
  temáticas activas. Mantiene el modo `draft`, sin publicación autónoma.
- **Imagen de posts:** marco y logo Nexia quedan seleccionados como acabado inicial; el editor
  puede quitarlos o combinarlos por separado en cada propuesta.
- **X:** preparado para monitorización diaria opt-in mediante `X_API_BEARER_TOKEN`; no hay cuentas
  ni llamadas activas todavía. Instagram y LinkedIn siguen con revisión manual.
- **Producción:** los commits `6081886`, `bf89d03` y `699bd72` están desplegados en Vercel. El
  scheduler remoto está activo con cadencia de tres días y modo `draft`.
- **Referencia completa:** [Estado y hoja de ruta](docs/ESTADO_Y_HOJA_DE_RUTA_2026-08-31.md),
  incluidos el estado, flujo, procedimiento y tareas pendientes.

**Fecha de referencia: 2026-08-24**

La referencia operativa vigente es [Arquitectura y operación](docs/ARQUITECTURA_Y_OPERACION.md) y
la guía del editor es [Guía de uso](docs/GUIA_DE_USO.md). Este archivo conserva el histórico de
decisiones y entregas anteriores; las secciones que describen únicamente `db.json`, Cloudinary o
una aplicación local no sustituyen la arquitectura actual desplegada.

## Estado operativo actual — 24/08/2026

- **Producción:** `https://nexiagp-content.vercel.app`, proyecto Vercel `nexiagp-content` de la
  cuenta/equipo Nexia GP. El enlace es de acceso directo (`NEXIAGP_AUTH_REQUIRED=0`).
- **Estado y ficheros persistentes:** Supabase es la fuente de verdad; usa estado transaccional,
  membresías y los buckets privados `source-library`, `editorial-images` y `brand-assets`.
- **Imágenes:** en Vercel se generan en `/tmp/nexiagp-images`, se validan/componen y se suben de
  inmediato a Supabase. No se guarda ninguna ruta efímera en el estado. Cloudinary es distribución
  opcional, no el almacenamiento canónico.
- **Código y despliegue:** `https://github.com/nexiagp/sistema_ia_contenido`, rama `main`, está
  enlazado a Vercel con despliegues automáticos. El repositorio es público y excluye secretos,
  estado editorial y documentación interna.
- **Respaldo:** se conserva la copia local previa a la migración y el backup actual; no eliminarlos
  sin una estrategia de retención aprobada.
- **Pendiente no bloqueante:** `SOCIAL_WEBHOOK_URL` sigue sin configurarse, por lo que no hay
  publicación automática real en redes. La aplicación genera, revisa y programa contenido.

---

## Actualización de auditoría — 22/08/2026

- **RAG verificable:** el pipeline consulta directamente el endpoint de búsqueda del Vector Store y
  reconcilia cada fragmento con el archivo real de `db.files`. Las fuentes no catalogadas no pueden
  sostener una publicación; los fragmentos del mismo archivo se agrupan.
- **Puerta de calidad:** `review_flags`, sensibilidad factual y ausencia de evidencia bloquean
  `ready`, `scheduled` y `published` hasta registrar una revisión humana explícita. El scheduler
  mantiene el borrador si existe un bloqueo.
- **Blogs seguros:** HTML/JSON-LD saneados, enlaces falsos de lead magnet neutralizados y control de
  H1, longitud, figuras, fuentes y SEO antes de pasar a listo.
- **Seguridad local:** rutas estáticas seguras, límite JSON 1 MB, upload permitido y acotado,
  errores internos no expuestos al cliente y JPEG con MIME correcto.
- **Prueba real final:** `post_22b94f25fe79` recuperó
  `D01_AP-Tenerife-Memoria-Anual-2024.pdf` como fuente oficial y usó 12.901 tokens en 4 llamadas
  (−43 % frente a la primera prueba de 22.767 tokens / 5 llamadas). Sigue en borrador por diseño.
- **Imagen real:** `post_22b94f25fe79` conserva dos conceptos: el PNG 1536×1024 histórico y una
  nueva escena 4:5 (1088×1360) de criterio experto en operación portuaria. Ambos están validados,
  el 4:5 es el activo seleccionado y sigue pendiente de revisión editorial humana.
- **Estado actual auditado:** 10 posts (9 en `draft`, 1 en `scheduled`), 2 blogs en `draft`,
  46 archivos y 0 publicaciones. `usageStats` acumulado: 5 generaciones, 24 llamadas y
  92.989 tokens. Se preservan los borradores y las variantes como evidencia editorial; no borrar
  sin decisión explícita.

Leer primero el cierre vigente antes de continuar:
`Documentación Nexia/2026-08-cierre-pre-entrega.md`.

## Actualización visual editorial — 22/08/2026

- **Dirección de arte controlable:** cada imagen de post ahora se genera con una intención visual
  (operación, criterio experto, territorio, producto o relación de canal) y un encuadre explícito,
  en vez de depender de un selector genérico de estilos.
- **Formatos listos para contenido:** se incorpora 4:5 para LinkedIn y 16:9 para cabeceras, además
  de los formatos editorial, cuadrado y vertical ya validados. La calidad separa exploración rápida,
  trabajo recomendado y final.
- **Mejor aspecto por contrato:** los prompts de posts y blog bloquean mapas, diagramas, planos,
  documentos ficticios, texto y composiciones de collage. El modelo debe resolver la idea como una
  escena fotográfica única, coherente y creíble.
- **Comparación sin pérdida:** cada post conserva hasta cinco conceptos visuales. El editor puede
  seleccionar el activo y registrar su revisión humana sin destruir las alternativas.
- **Documentación operativa:** ver `Documentación Nexia/2026-08-estandar-visual-editorial.md`.
- **UX de revisión:** la bandeja de posts muestra una miniatura o estado visual incluso cerrada.
  Al abrir una pieza aparece una mesa de revisión: copy final a la izquierda y pieza visual a la
  derecha. La imagen se muestra completa en una miniatura contenida y se amplía en un diálogo sin
  recorte; los controles quedan en un desplegable propio, no en una columna lateral interminable.
- **Dirección visual guiada:** gestionar una imagen abre decisiones explicadas en lenguaje editorial
  (qué comunica, cómo se encuadra y formato/acabado), conservando variantes y revisión humana. Las
  miniaturas de alternativas también usan `contain`, no `cover`.
- **Revisión de blogs:** el formulario de creación queda recogido; los artículos existentes se
  seleccionan desde tarjetas con filtros y búsqueda alineados. El detalle abierto conserva vista
  previa, SEO, brief e imágenes, y la transición se expresa como “Preparar para calendario”.
- **Control de blog legible:** la vista previa del artículo es permanente y los paneles de control
  quedan debajo. SEO muestra una ficha de resultado de buscador, URLs y datos estructurados
  resumidos; el JSON-LD bruto queda bajo demanda. El enfoque convierte el brief en tesis,
  audiencia, cobertura de búsqueda y enlaces internos; las imágenes son una galería ampliable con
  sus controles de generación recogidos.
- **Fallo corregido de paneles:** la clase `hidden` ya se aplica realmente. Al cambiar entre SEO,
  enfoque e imágenes se muestra un único panel y se desplaza al control correspondiente, en vez de
  apilar toda la información debajo del iframe.
- **Caché de entrega:** `index.html` versiona CSS y JavaScript para impedir que un navegador mezcle
  una interfaz nueva con estilos antiguos durante una actualización local.
- **Entrega manual de PNG:** el activo seleccionado de cada post, cada concepto conservado y cada
  figura de blog ofrecen `Descargar PNG`. La acción obtiene el binario final directamente; no usa
  la miniatura visible, ni canvas, ni recompresión, por lo que preserva la calidad original.
- **Calendario editorial con selección:** posts y blogs se eligen en bandejas separadas antes de
  asignar su fecha. Los posts incluyen miniatura y extracto para identificar la pieza; los blogs
  mantienen una lista editorial compacta. Ambos guardan día y hora como `scheduledFor`, sin
  confundir planificación interna con publicación automática.
- **Agenda de ocupación:** la agenda editorial abre por defecto una vista mensual. Marca los días
  con piezas programadas o publicadas, deja explícitos los huecos libres y muestra el detalle de
  cada fecha al hacer clic; se conserva una vista de lista para recorrer la planificación lineal.
- **Validación visual real:** comprobada en Google Chrome a `1920 × 855 px` y `390 × 844 px`:
  sin desbordamiento horizontal, miniatura y modal de imagen íntegros, tarjetas de blog en una
  columna en móvil y buscador de `38 px` de alto.
- **Calendario comprobado en Chrome:** la vista mensual se abre por defecto, permite navegar entre
  meses, identifica días ocupados y libres y muestra el detalle al pulsar una fecha; la vista de
  lista sigue disponible. Los candidatos de blog mantienen el CTA dentro de su tarjeta.

---

## PUNTO ACTUAL DEL PROYECTO

### Actualización de entrega — 16/08/2026

- **Interfaz y operación editorial:** navegación móvil compacta, banda de métricas equilibrada,
  bandeja de posts cerrada por defecto (detalle bajo demanda e imagen ampliable solo al clic),
  checklist de aprobación, filtros de biblioteca, calendario de planificación manual y bloqueo
  explícito de publicación automática cuando no hay webhook.
- **Generaciones asíncronas visibles:** los flujos editorial y blog se ejecutan como trabajos
  locales en segundo plano y muestran sus pasos reales mediante sondeo. El contenido final sigue
  guardándose en las transacciones ya existentes.
- **Imagen fiable y marca determinista:** se usan presets de tamaño/calidad validados en producto;
  el PNG se valida antes de persistir y el logo aprobado se compone localmente
  antes de la entrega. Cloudinary queda como distribución, nunca como requisito para aplicar marca.
- **Coste de blog:** `costTargetCents` ya bloquea, antes de solicitarla, una figura cuyo coste
  estimado de salida de imagen haga superar el tope del artículo. No cubre texto ni entradas de
  edición, que son variables.
- **Verificación:** compilación Python y JavaScript, seis pruebas offline de imagen y ciclo de
  trabajo asíncrono simulados correctamente; interfaz comprobada en escritorio y móvil sin
  consumir OpenAI.

El sistema está operativo y completo en sus pilares principales. La sesión 4 aportó la auditoría y
las fases de calidad/integridad ya commiteadas; la sesión 5 añade entrega UX, control operativo e
imagen fiable en cambios locales aún sin commit.

1. **Generacion de posts** para LinkedIn/X/Facebook — funcional, con imagenes, prompts editables.
2. **Generacion de articulos de blog** — funcional, con imagenes ligeras, preview fiel al sitio web.
3. **Knowledge Base externa** — **SUBIDA**: 34 PDFs sectoriales de Canarias ya en el Vector Store.

**Límite consciente de esta entrega:**
- La aplicación crea, revisa y planifica contenido; no pretende incluir analítica/KPIs ni
  publicación real a redes. El webhook actual es solo un punto de extensión, no una integración
  social terminada.
- Siguen pendientes las acciones manuales de seguridad (ver sección Seguridad).

Para el handoff exhaustivo de la sesión 5, leer
`Documentación Nexia/2026-08-entrega-y-continuidad.md`.

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
  - `#calendar` — planificación interna de posts; no publica por sí solo.
  - `#automation` — scheduler por cadencia.
  - `#settings` — ajustes (General / Posts / Blog / Prompts).
- La clave API esta en `.env`; no imprimirla ni moverla a archivos versionables.

---

## Estado de datos (db.json)

- 10 posts (9 `draft`, 1 `scheduled`, 0 `ready`, 0 `published`) — no borrar sin decisión editorial
  explícita. `post_22b94f25fe79` conserva dos variantes validadas y usa la nueva imagen 4:5 como
  activo seleccionado, pendiente de revisión humana.
- 2 blogs (ambos draft) — ambos con imagenes generadas.
- **46 archivos** sincronizados con el Vector Store: 12 (web + copywriting de Nexia) + **34 de la
  KB externa sectorial** (subidos en sesion 4).
- 0 overrides de prompt (los `.txt` estan activos; `prompt_overrides` y `prompt_versions` vacios).
- **`usageStats`** (nuevo): acumulado de tokens por generacion (`generations`, `calls`,
  `input_tokens`, `output_tokens`, `total_tokens`). A fecha de referencia: 5 generaciones,
  24 llamadas, 79.741 tokens de entrada, 13.248 de salida y 92.989 totales.
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
- Modelo `gpt-image-2` | 1536x1024 (default) | calidad medium.
- Formatos admitidos: `1536x1024`, `1024x1024`, `1024x1536`; PNG validado y persistido
  atómicamente tras hasta dos intentos.
- Frame: blur strip + línea chocolate + logo NGP con Pillow local (ON por defecto). Cloudinary
  solo distribuye ese activo ya compuesto.

### Blog
- 1536x1024 (default) | calidad standard. Frame/logo OFF por defecto; se puede activar como
  composición local opcional. Figuras distribuidas en el HTML y limitadas por presupuesto de imagen.

---

## Endpoints utiles

```
GET   /api/health                                — estado de clave, modelo, VS
GET   /api/state                                 — estado completo (incluye usageStats)

POST  /api/editorial/generate                    — genera post completo [CONSUME OPENAI]
POST  /api/jobs/editorial                        — inicia post en segundo plano [CONSUME OPENAI]
POST  /api/editorial/posts/:id/regenerate        — regenera post [CONSUME OPENAI]
POST  /api/editorial/posts/:id/adapt             — regenera adaptaciones X/FB [CONSUME OPENAI]
POST  /api/posts/:id/generate-image              — genera imagen de post [CONSUME OPENAI]
PATCH /api/posts/:id                             — edita status Y copy/cta/hashtags/title (inline)
DELETE/api/posts/:id                             — elimina post
POST  /api/posts/:id/publish                     — publica (webhook stub si SOCIAL_WEBHOOK_URL)

POST  /api/blogs/generate                        — genera blog completo [CONSUME OPENAI]
POST  /api/jobs/blog                             — inicia blog en segundo plano [CONSUME OPENAI]
GET   /api/jobs/:id                              — estado de un trabajo local
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

Abrir `http://localhost:8787`. Para levantar una instancia secundaria sin tocar la principal:

```powershell
$env:PORT = '8789'
python server.py
```

Si el puerto esta ocupado:
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

# Suite offline de contratos (17 pruebas actuales)
python -m unittest -v test_calendar_scheduling test_content_quality test_image_service_offline test_visual_direction
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

### 2. Cierre editorial y preparación de demostración
- Revisar los posts y blogs existentes contra copy, fuentes, SEO e imagen antes de etiquetarlos como
  listos; una fecha de calendario no equivale a publicación.
- Hacer una demostración local completa: generar borrador, revisar copy, comparar/descargar PNG,
  inspeccionar blog y reservar una fecha. No consumir OpenAI sin aprobación explícita.

### 3. Descargar el OTLE y completar la KB
Descargar el OTLE Informe Anual 2024 a `data/uploads/kb-externa/D-logistica/` y
`python scripts/upload_kb.py` (subira solo ese).

### 4. Fuera del alcance inmediato / deuda técnica
- La publicación real requerirá decidir LinkedIn API directa o Buffer/Metricool, OAuth, cola
  persistente, reintentos y comprobación humana final. No activarla como parte del cierre actual.
- Sustituir el sondeo actual por SSE/WebSocket si se migra a una arquitectura multiusuario.
- Migrar `db.json` a SQLite si crece mucho (la transaccion atomica ya mitiga lo urgente).
- Mantener y ampliar la suite offline de 17 contratos; añadir E2E HTTP/Chrome cuando se estabilice
  el siguiente bloque funcional.
- Extender los presupuestos a texto, edición de imagen y vídeo cuando se habilite esa línea.
- Historial de versiones del contenido de posts (como ya existe para prompts).

---

## Scripts utiles

```powershell
# Subir / completar la KB externa al Vector Store (resumible)
python scripts/upload_kb.py

# Re-descargar la KB externa (otra maquina)
python scripts/download_kb.py
```
