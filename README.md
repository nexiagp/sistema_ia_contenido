# Nexia GP Content AI

Sistema editorial de Nexia Growth Partner para generar y revisar **posts de LinkedIn** (con
adaptaciones a X/Facebook) y **artículos de blog** basados en conocimiento sectorial de Canarias.
Está desplegado en Vercel, usa Supabase como estado y almacenamiento persistentes, y se actualiza
automáticamente al hacer `push` a la rama `main`.

Producción: <https://nexiagp-content.vercel.app>

## Continuidad del proyecto

La documentación vigente está en:

- **[`docs/ARQUITECTURA_Y_OPERACION.md`](docs/ARQUITECTURA_Y_OPERACION.md)** — referencia
  operativa: arquitectura, responsabilidades de cada servicio, flujos, despliegue, seguridad,
  backups e incidencias.
- **`PROJECT_STATE.md`** — estado de continuidad e histórico técnico.
- **`CHANGELOG.md`** — historial de cambios por sesión y commit.

Leer primero `docs/ARQUITECTURA_Y_OPERACION.md` antes de retomar el desarrollo.

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

Para una segunda instancia local (por ejemplo, durante una revisión sin tocar la que ya está
abierta), el puerto se puede cambiar de forma explícita:

```powershell
$env:PORT = '8789'
python server.py
```

En ese caso la URL es `http://localhost:8789`. No cambiar ni detener un servidor de otro puerto
sin comprobar antes que pertenece a esta sesión.

> Seguridad: nunca versionar `.env` ni claves en `.txt`. Si el proyecto vive en OneDrive, excluye
> los secretos de la sincronizacion. Ver la seccion *Seguridad* de `PROJECT_STATE.md`.

## Despliegue

La rama `main` del repositorio de GitHub está vinculada al proyecto **Nexia GP / nexiagp-content**
de Vercel. Tras verificar los cambios localmente:

```powershell
git add -A
git commit -m "tipo: descripcion breve"
git push origin main
```

Vercel crea el despliegue de producción automáticamente. El código no contiene secretos, estado
editorial ni documentación interna: todo ello permanece en las variables seguras de Vercel y en
Supabase. La guía completa de verificación y recuperación está en
[`docs/ARQUITECTURA_Y_OPERACION.md`](docs/ARQUITECTURA_Y_OPERACION.md).

## Que incluye

- **Pipeline editorial multi-step**: planner -> retrieval vectorial trazable -> writer -> validator
  -> adaptadores, con anti-repeticion de hooks, límite de 280 caracteres en X, normalización de
  hashtags, puerta de revisión humana y voz diferenciada.
- **11 tipos de post** (7 tematicos + 4 de formato: founder-led, prueba social, encuesta,
  dato+opinion) y **3 prompts de blog**, todos editables y versionados desde la UI.
- **Generacion de blog** con HTML saneado, SEO (JSON-LD, OG, enlazado interno), quality gate y
  preview fiel a nexiagp.com.
- **Biblioteca documental** con subida a OpenAI Files y Vector Store (incluye 34 PDFs sectoriales de
  Canarias por categoria).
- **Operacion de contenido en la UI**: edicion inline, filtros y busqueda (posts y blogs), export
  CSV/JSON, preview por canal (LinkedIn/X/Facebook), metrica de tokens, calendario editorial y
  bandeja de revisión compacta con detalle e imagen ampliable bajo demanda. La agenda abre en mes,
  permite seleccionar piezas o blogs y conserva una vista de lista.
- **Generaciones visibles**: trabajos locales en segundo plano con pasos de pipeline y sondeo en
  la interfaz, sin mantener la petición HTTP abierta.
- **Imagen de producción**: presets validados, PNG validado, escritura atómica, logo compuesto
  localmente y presupuesto estimado por figuras de blog. La dirección de arte permite elegir
  intención, encuadre y formato; conserva hasta cinco variantes por post para comparar y aprobar,
  y entrega el PNG final original para descarga manual en posts, variantes y figuras de blog.
- **Integridad**: escrituras atomicas en `db.json` (`transaction()`), sin lost-update.
- **Registro de coste** de tokens (`usageStats`).
- Scheduler local por cadencia mientras el servidor este activo.
- Modo local (fallback) para posts si no hay `OPENAI_API_KEY`, útil para verificar guardas sin
  coste. Los blogs requieren OpenAI para no presentar contenido largo no sustentado como generación
  final.

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
