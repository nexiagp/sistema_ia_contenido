# Nexia GP Social AI — Estado de continuidad

**Fecha de referencia: 2026-06-07**
**Ultima sesion documentada: Sesion 3 (07/06/2026)**

Este archivo es la fuente de verdad del proyecto. Leerlo SIEMPRE antes de retomar trabajo.

---

## PUNTO ACTUAL DEL PROYECTO

El sistema esta operativo y completo en sus tres pilares principales:

1. **Generacion de posts** para LinkedIn/X/Facebook — funcional, con imagenes, prompts editables.
2. **Generacion de articulos de blog** — funcional, con imagenes ligeras, preview fiel al sitio web.
3. **Knowledge Base externa** — 34 PDFs descargados (122 MB), pendientes de subir al Vector Store.

**Lo que falta ahora mismo:**
- Subir la KB externa al Vector Store (los archivos ya estan en disco).
- Decidir si se sube al VS actual o al VS definitivo del cliente.
- Mejorar el sistema de generacion de imagenes para posts (calidad, variedad de estilos).

---

## App actual

- Aplicacion local para generar posts de LinkedIn (con adaptaciones a X y Facebook) y articulos de blog para Nexia Growth Partner.
- Servidor canonico: `server.py` (Python `SimpleHTTPRequestHandler`).
- URL local: `http://localhost:8787`.
- Vistas principales:
  - `http://localhost:8787/#posts` — revision editorial de posts.
  - `http://localhost:8787/#blogs` — creacion y revision de articulos de blog.
  - `http://localhost:8787/#library` — biblioteca de archivos y Vector Store.
  - `http://localhost:8787/#settings` — ajustes (4 sub-tabs: General / Posts / Blog / Prompts).
- La clave API esta configurada en `.env`; no imprimirla ni moverla a archivos versionables.

---

## Estado de datos (db.json)

- 5 posts (4 draft, 1 ready) — todos con imagenes generadas.
- 2 blogs (ambos draft) — ambos con imagenes generadas.
- 12 archivos sincronizados con OpenAI Vector Store (solo web y copywriting de Nexia, sin KB externa aun).
- 15 prompts registrados (editables desde UI, con versionado append-only).
- Almacenamiento: JSON flat-file local (`data/db.json`). NO Supabase.

---

## OpenAI

- Modelo configurado: `gpt-5.4-mini`.
- Vector Store activo: `vs_69e91ba9d27c819197a522a6a07dae20`.
- Nombre: `Nexia GP Knowledge Base`.
- El cliente ignora proxies heredados invalidos via `urllib.request.ProxyHandler({})` en `server.py` y `openai_client.py`.

---

## Cloudinary

- Dos variantes por imagen:
  - `rawUrl`: sin overlay — usada en blog por defecto.
  - `brandedUrl`: con logo Nexia GP — usada en posts por defecto.
- Cuenta: `dg3peytgm`, carpetas `nexiagp/posts/` y `nexiagp/blogs/`.

---

## Knowledge Base externa (KB) — PENDIENTE DE SUBIR

### Estado
- **34 PDFs descargados y verificados** en `data/uploads/kb-externa/` (122 MB total).
- Investigacion realizada con workflow de 28 agentes: busqueda → verificacion real de URLs → curacion → relleno de gaps → sintesis.
- Script de descarga en `scripts/download_kb.py` (para re-ejecutar si hace falta).

### Estructura de la carpeta
```
data/uploads/kb-externa/
├── A-economia/   8 docs  (18.8 MB)  — CES 2024, BBVA 2025+2026, Presupuestos, CEOE-Tenerife
├── B-fiscal/     6 docs  (15.3 MB)  — Manual AEAT, Dictamen REF Parlamento, PwC/SPEGC, ZEC, BIPLAZA, RIC
├── C-turismo/    5 docs  (26.1 MB)  — IMPACTUR, Perspectivas N.95, Balance Tenerife, ULL
├── D-logistica/  3 docs  (14.4 MB)  — Memoria AP Tenerife 2024, Sostenibilidad SCT, OPPE Anuario
├── E-industria/  4 docs   (9.4 MB)  — EDIC 2022-2027, CCE Construccion, Mapa Vacantes, CCOO
├── F-demografia/ 4 docs   (9.2 MB)  — PYME Canarias 2025, PYME 2024 Talento, CCE Estructura, DGIPYME
├── G-digital/    3 docs  (26.6 MB)  — eCanarias 2024, ONTSI PYMEs, BBVA/Ivie Productividad
└── Z-garden/     1 doc   (1.4 MB)   — MAPA Flor Cortada
```

### TOP 10 imprescindibles (por score del workflow)
1. Informe Economico Presupuestos Canarias 2026 (10/10) — macro oficial 2025-2028
2. Manual Practico Sociedades 2024 AEAT Cap.12 (10/10) — REF/ZEC/RIC tecnico
3. Dictamen Revision REF Parlamento Canarias dic.2025 (10/10) — futuro normativo
4. CES Informe Anual 2024 (9/10) — radiografia integral 354 pag
5. EDIC Estrategia Industrial Canarias 2022-2027 (9/10) — sectores prioritarios
6. IMPACTUR Canarias 2024 EXCELTUR (9/10) — impacto economico turismo
7. Guia Fiscal Gran Canaria 2024 PwC/SPEGC (9/10) — ZEC+RIC+DIC accesible
8. PYME Canarias 2025 FAEDPYME/ULPGC (9/10) — perfil del cliente PYME
9. BBVA Situacion Canarias 2026 (9/10) — macro independiente
10. Guia Constituir Empresas ZEC BIPLAZA/ONE (9/10) — operativo paso a paso

### Para subir al Vector Store
Desde la app: Library > Importar local > seleccionar carpeta `data/uploads/kb-externa/` > Sincronizar OpenAI.
O bien esperar al Vector Store definitivo del cliente para subirlo todo de una vez.

### Pendiente descarga manual (bloqueado por anti-bot)
- **OTLE Informe Anual 2024** (logistica): https://otle.transportes.gob.es/informes-anuales-monograficos/informes-anuales/informe-anual-otle-2024
  — Descargar manualmente desde el navegador y mover a `data/uploads/kb-externa/D-logistica/`.

---

## Arquitectura editorial — Posts

Flujo multi-step:
1. `planner` — decide tipo, audiencia, objetivo, brief.
2. `retrieval` — busca en Vector Store documentacion relevante.
3. `writer` — genera el post LinkedIn.
4. `validator` — valida calidad, riesgos, adherencia a marca.
5. Adaptadores multicanal — genera versiones X y Facebook.

---

## Arquitectura editorial — Blog

Flujo multi-step:
1. `blog_planner` — brief, keywords, estructura de secciones, figure slots.
2. `retrieval` — busca en Vector Store.
3. `blog_writer` — genera articulo completo en HTML semantico con CTA "Comenzamos? · Contactar".
4. `seo_reviewer` — valida SEO, flags de calidad.
5. Generacion de imagenes de figura — N imagenes ligeras por articulo.

Settings en `settings.blog`:
- `defaultModel`, `defaultLength`, `defaultFramework`, `defaultAudience`
- `imagesPerArticle` (default 2), `imageQuality` (default "standard")
- `costTargetCents` (default 30)

---

## Servicios principales

- `src/ai/services/openai_client.py`
- `src/ai/services/retrieval_service.py`
- `src/ai/services/planner_service.py`
- `src/ai/services/writer_service.py`
- `src/ai/services/validator_service.py`
- `src/ai/services/adaptation_service.py`
- `src/ai/services/pipeline_service.py`
- `src/ai/services/prompt_service.py` — PROMPT_REGISTRY (15 prompts), override-aware, versionado.
- `src/ai/services/blog_pipeline.py`
- `src/ai/services/blog_planner_service.py`
- `src/ai/services/blog_writer_service.py`
- `src/ai/services/blog_seo_service.py`
- `src/ai/services/image_prompt_service.py` — genera prompt de imagen para posts via LLM.
- `src/ai/services/image_service.py` — llama a gpt-image-2 y guarda localmente.
- `src/ai/services/frame_composer.py` — compone el frame de marca (blur strip + linea chocolate).
- `src/ai/services/cloudinary_service.py` — sube a Cloudinary, genera brandedUrl con logo overlay.

---

## Sistema de prompts

15 prompts en PROMPT_REGISTRY:
- Base: `base_global_v1`, `planner_v1`, `validator_v1`
- Posts (7 tipos): `marca_propuesta_valor`, `educativo_autoridad`, `sector_solucion`, `fabricante_colaborador`, `proyecto_prescripcion`, `servicio_proceso_operativa`, `actualidad_lectura_mercado`
- Adaptadores: `adaptacion_x`, `adaptacion_facebook`
- Blog: `blog_planner_v1`, `blog_writer_v1`, `blog_seo_reviewer_v1`

Sistema de overrides: `db.json > prompt_overrides[name].text` tiene prioridad sobre `.txt`.
Versionado append-only en `db.json > prompt_versions`. UI en Settings > Prompts.

---

## Imagenes

### Posts
- Modelo: `gpt-image-2` | Tamano: 1344x768 (default) | Calidad: medium (default)
- Estilo: "Fotografia documental editorial" (default, configurable)
- Frame: blur strip + linea chocolate (Pillow local) + logo NGP via Cloudinary (ON por defecto)
- `ImagePromptService`: LLM genera el prompt de imagen en ingles a partir del post, angulo y brief visual.

### Blog
- Tamano: 1024x576 | Calidad: standard (default, desde settings.blog.imageQuality)
- Estilo: "Ilustracion editorial sobria"
- Frame/overlay: OFF por defecto (usa rawUrl directo)
- Imagenes distribuidas como figure slots en el HTML del articulo.

---

## UI

- `public/index.html` — estructura de la SPA
- `public/app.js` — toda la logica
- `public/styles.css` — estilos generales
- `public/blog-preview.css` — estilos del iframe de blog (fiel a nexiagp.com)

### Preview del blog — valores exactos verificados en nexiagp.com
- Paleta: primary `#261E1E`, secondary `#EEEDEC`, text `#5B5B5B`, accent `#DBD4CC`, teal `#00ADB6`
- Tipografia: Questrial para TODO (headings + body + botones), 15px, line-height 1.8
- H2: 45px | H3: 24px | Boton CTA: bg #261E1E, color #EEEDEC, padding 15px 30px, radius 0, uppercase
- Referencia: `post-7.css` del kit Elementor de nexiagp.com

---

## Endpoints utiles

```
GET  /api/health                                  — estado de clave, modelo, VS
GET  /api/state                                   — estado completo de la app

POST /api/editorial/generate                      — genera post completo [CONSUME OPENAI]
POST /api/editorial/posts/:id/regenerate          — regenera post existente [CONSUME OPENAI]
POST /api/editorial/posts/:id/adapt               — regenera adaptaciones X/FB [CONSUME OPENAI]
POST /api/posts/:id/generate-image               — genera imagen para post [CONSUME OPENAI]

POST /api/blogs/generate                          — genera articulo de blog completo [CONSUME OPENAI]
POST /api/blogs/:id/generate-figure-image         — genera imagen de figura [CONSUME OPENAI]
PATCH /api/blogs/:id                              — actualiza estado/campos del blog

GET  /api/settings                                — lee configuracion
PATCH /api/settings                               — actualiza config (incluye settings.blog)

GET  /api/prompts                                 — lista los 15 prompts con metadatos
GET  /api/prompts/:id                             — detalle completo de un prompt
PUT  /api/prompts/:id                             — guarda override de un prompt
POST /api/prompts/:id/revert                      — revierte a version anterior

POST /api/files/sync-openai                       — sincroniza archivos con OpenAI Vector Store
```

---

## Arranque

```powershell
python server.py
```

Abrir: `http://localhost:8787`

Si el puerto esta ocupado:
```powershell
netstat -ano | findstr :8787
Get-Process python -ErrorAction SilentlyContinue
```

---

## Verificacion sin consumir tokens

```powershell
# Salud del servidor
Invoke-RestMethod -Uri 'http://localhost:8787/api/health' | ConvertTo-Json -Depth 5

# Compilacion de todos los modulos Python
python -m py_compile server.py `
  src\ai\services\openai_client.py `
  src\ai\services\retrieval_service.py `
  src\ai\services\planner_service.py `
  src\ai\services\writer_service.py `
  src\ai\services\validator_service.py `
  src\ai\services\adaptation_service.py `
  src\ai\services\pipeline_service.py `
  src\ai\services\prompt_service.py `
  src\ai\services\blog_pipeline.py `
  src\ai\services\blog_planner_service.py `
  src\ai\services\blog_writer_service.py `
  src\ai\services\blog_seo_service.py `
  src\ai\services\image_prompt_service.py `
  src\ai\services\image_service.py `
  src\ai\services\frame_composer.py `
  src\ai\services\cloudinary_service.py `
  src\domain\editorial.py
```

---

## Reglas de continuidad

- **NO lanzar** `POST /api/editorial/generate`, `POST /api/blogs/generate` ni ningun endpoint de imagenes salvo peticion EXPLICITA del usuario. Todos consumen OpenAI.
- No borrar posts/blogs de muestra. Sirven para revisar la UI sin gastar tokens.
- No imprimir ni exponer la API key.
- Mantener prompts separados y versionados; nunca mezclar en una sola llamada.
- Mantener trazabilidad en UI: brief, fuentes, flags, notas de validacion y adaptaciones.
- Al tocar la UI, no perder acciones existentes (copiar, adaptar, regenerar, publicar, marcar listo, eliminar).

---

## PROXIMOS PASOS — Por orden de prioridad

### 1. INMEDIATO: Subir KB externa al Vector Store (0 tokens de generacion)
- Decidir si se sube al VS actual (`vs_69e91ba9d27c819197a522a6a07dae20`) o esperar al VS definitivo del cliente.
- Si se decide subir: Library > Importar local > `data/uploads/kb-externa/` > Sincronizar OpenAI.
- Descargar manualmente el OTLE y moverlo a `D-logistica/` antes de sincronizar.
- **Impacto esperado**: el retrieval de posts y blogs pasara de recuperar solo web de Nexia a recuperar datos sectoriales, fiscales, macroeconomicos y turisticos de Canarias reales.

### 2. ALTA PRIORIDAD: Mejorar sistema de imagenes para posts
- El `ImagePromptService` ya genera prompts en ingles via LLM — base solida.
- Mejoras pendientes:
  a. Añadir estilos predefinidos adicionales (no solo "Fotografia documental editorial"): opciones como "Minimalista de estudio", "Aerea / drone shot", "Macro detalle industrial".
  b. Opcion de regenerar solo el prompt (sin generar imagen) para que el usuario lo ajuste antes.
  c. Mejorar el prompt del `ImagePromptService`: añadir contexto de sector del post, isla especifica si la hay, tipo de post.
  d. Revisar la composicion del frame (blur strip + chocolate line): evaluar si el resultado visual es el deseado o hay que ajustar padding_ratio, blur_radius, line_width.
  e. Añadir opcion de "sin frame, sin overlay" para posts (ahora solo existe en blog).

### 3. MEDIA PRIORIDAD: Funcionalidades de UI pendientes
- Filtros y busqueda en la vista de posts (cuando haya volumen de contenido).
- Historial de regeneraciones por post (ver versiones anteriores del post).
- Exportacion de piezas aprobadas a CSV/JSON para entrega al cliente.
- Boton "Generar lote" para crear varios posts de una sola vez.

### 4. BAJA PRIORIDAD: Mejoras de sistema
- Pulir detalles responsive para movil.
- Preparar despliegue o instalador local si la app pasa a uso frecuente del cliente.
- Añadir logs de uso (cuantos tokens se consumen por generacion) visible en UI.
- Considerar export de articulos de blog a WordPress (WP REST API).

### 5. FUTURO: Vector Store definitivo del cliente
- Cuando Nexia GP tenga su VS de produccion, migrar los 12 archivos web + 34 PDFs KB externa.
- La app ya soporta cambiar el vectorStoreId desde Settings sin tocar codigo.

---

## Scripts utiles

```powershell
# Re-descargar KB externa (por si se necesita en otra maquina)
python scripts/download_kb.py

# Ver cuantos archivos y peso tiene la KB descargada
python -X utf8 -c "
import pathlib
base = pathlib.Path('data/uploads/kb-externa')
files = list(base.rglob('*.pdf'))
size = sum(f.stat().st_size for f in files)
print(f'{len(files)} archivos, {size/1e6:.0f} MB')
"
```
