# Arquitectura y operación — Nexia GP Content AI

**Actualizado:** 1 de septiembre de 2026
**Ámbito:** aplicación de contenido de Nexia GP. No cubre el chatbot.

Para el trabajo diario en la interfaz, consultar primero la [Guía de uso](GUIA_DE_USO.md). Este documento es la referencia de arquitectura, despliegue, seguridad y recuperación.

## Resumen operativo

La aplicación está disponible en <https://nexiagp-content.vercel.app>. Es una SPA con una API
Python que genera, revisa y programa posts y artículos de blog. El código se versiona en
[`nexiagp/sistema_ia_contenido`](https://github.com/nexiagp/sistema_ia_contenido), y cada `push` a
`main` crea un despliegue de producción en Vercel.

Supabase es la fuente de verdad del contenido y de los archivos. No depender de un disco local de
Vercel: su sistema de archivos de despliegue es de solo lectura y `/tmp` sólo se usa durante una
invocación.

```text
Editor / navegador
        │ HTTPS
        ▼
Vercel · proyecto nexiagp-content
  SPA + función Python + cron diario
        │             │
        │             ├── OpenAI Responses / Images / Vector Store
        │             ├── Cloudinary (entrega opcional de imágenes)
        │             ├── WordPress · medios y borradores del blog
        ▼
Supabase
  estado editorial · biblioteca · imágenes · activos de marca

GitHub (main) ──push──► Vercel (despliegue automático)
```

## Quién aloja qué

| Servicio | Responsabilidad | Estado de uso |
| --- | --- | --- |
| **Vercel** | Aplicación pública, API Python, ejecuciones serverless y cron `/api/cron/daily`. | Producción en el equipo Nexia GP, plan Hobby. |
| **Supabase** | Fuente de verdad del estado editorial, control de miembros y almacenamiento privado de archivos. | Obligatorio en producción. |
| **OpenAI** | Generación de copy, blogs, prompts, imágenes y consulta del Vector Store. | Sólo se llama desde el servidor; consume saldo según uso. |
| **Cloudinary** | URL de entrega opcional para imágenes ya compuestas. | No es requisito para conservar ni recuperar una imagen. |
| **WordPress** | Destino de los artículos ya aprobados: medios y borradores de entradas. | `nexiagp.com`; nunca publica desde la integración. |
| **GitHub** | Código, migraciones, pruebas y documentación pública operativa. | Repositorio público; no contiene datos ni secretos. |

## Supabase: datos y almacenamiento

Supabase conserva el estado mediante operaciones con versión para evitar sobrescrituras
concurrentes. Los buckets son privados y los descarga la API de Vercel con credenciales de
servidor:

| Bucket | Contenido |
| --- | --- |
| `source-library` | Documentos incorporados a la biblioteca editorial. |
| `editorial-images` | PNG originales y versiones con marco de posts y figuras de blog. |
| `brand-assets` | Activos de marca que requiere el compositor visual. |

Las rutas públicas de la aplicación, como `/images/<archivo>.png`, son una entrega de la API que
obtiene el binario duradero desde Supabase. Una ruta local o de `/tmp` nunca forma parte del estado
editorial persistido.

El 1 de septiembre se completó la copia de los activos históricos a estos buckets antes de activar
la sincronización de WordPress. El estado editorial remoto y los objetos de Storage son el único
origen operativo; no reconstruirlos desde una copia local de `db.json`.

## WordPress: flujo de borradores

La integración de `nexiagp.com` está activa. Un blog sólo puede enviarse cuando está en estado
`ready` o `scheduled` y tiene la revisión humana registrada. El envío:

1. vuelve a ejecutar los controles deterministas de calidad sin borrar la aprobación registrada;
2. obtiene las figuras desde `editorial-images`, las convierte a JPEG optimizado (objetivo 200 KB,
   máximo 1 MB) y las sube a la Biblioteca multimedia de WordPress;
3. crea o actualiza **un borrador** de entrada con título, slug, contenido, extracto, figuras e
   imagen destacada;
4. guarda en Nexia GP el ID, URL, fecha, hash del contenido y medios subidos para evitar
   duplicados en los reintentos.

Una edición de título, slug, meta título, meta descripción o HTML editorial invalida la aprobación
anterior a propósito: hay que revisar y confirmar otra vez antes de sincronizar. Un reenvío sin
cambios conserva la aprobación y actualiza el borrador ya asociado. La integración nunca cambia
una entrada publicada y nunca ejecuta `publish` ni una programación automática.

### SEO y Rank Math

La aplicación detecta en tiempo de ejecución si Rank Math expone sus metacampos mediante la API
REST de WordPress. Cuando estén disponibles, envía metatítulo, metadescripción y keyword principal.
En la configuración actual no se exponen como campos REST editables, por lo que cada borrador queda
marcado para completar o revisar esos datos manualmente en Rank Math antes de publicarlo. Esta
limitación SEO no bloquea la creación del borrador.

### Incidencia corregida el 01/09/2026

El botón de WordPress recalculaba la puerta de calidad justo antes del envío y perdía la marca de
revisión humana; por eso un artículo ya aceptado mostraba de nuevo el error de que debía aceptarse.
El cambio `f939324` conserva esa marca al recalcular el mismo contenido y exige una aprobación
nueva sólo ante cambios editoriales. Se verificó creando tres borradores reales sin publicar.

## Flujo de generación de contenido

1. El editor crea un post o blog desde la SPA.
2. La API ejecuta el pipeline: planificación, recuperación de contexto del Vector Store, redacción,
   validación editorial y adaptaciones.
3. El resultado, fuentes, quality gate y uso se escriben de forma transaccional en Supabase.
4. El editor revisa el borrador antes de marcarlo como listo o programarlo.
5. La publicación social real no se activa sin un `SOCIAL_WEBHOOK_URL` válido; a fecha de este
   documento no hay webhook configurado.

### Fuentes de fabricantes y redes

La biblioteca incluye un catálogo de fabricantes con webs oficiales. Al actualizar una marca, la
API lee su página principal y hasta cuatro secciones relevantes del mismo dominio, crea o actualiza
un documento local y sólo lo incorpora al contexto de posts y blogs al sincronizarlo con el Vector
Store. Una actualización posterior reemplaza el adjunto anterior de ese mismo documento lógico,
para evitar duplicados.

La aplicación puede descubrir enlaces a redes desde esas webs. Sólo X admite monitorización
automática y es siempre opt-in: exige una cuenta confirmada, `X_API_BEARER_TOKEN` en servidor y el
cron diario. Instagram y LinkedIn se mantienen en revisión manual. El detalle de catálogo,
operación y tareas pendientes está en [Estado y hoja de ruta](ESTADO_Y_HOJA_DE_RUTA_2026-08-31.md).

Los trabajos largos se guardan y recuperan desde el backend persistente para que una invocación
serverless interrumpida no pierda silenciosamente el estado del encargo.

## Flujo de generación de imágenes

1. La API obtiene un prompt visual y solicita la imagen a OpenAI.
2. En Vercel, el PNG se escribe temporalmente en `/tmp/nexiagp-images`.
3. Se valida formato, tamaño y dimensiones; si se solicita, se compone localmente el marco, el
   logo Nexia o ambos.
4. El PNG original y, si existe, el PNG compuesto se suben al bucket `editorial-images` de
   Supabase antes de terminar la invocación.
5. Se guarda sólo la referencia `/images/...` y los metadatos de validación en el estado. Los
   archivos temporales se eliminan tras el éxito.

Si falla antes de la persistencia, revisar los registros de Vercel y no reintentar a ciegas: una
solicitud de imagen puede haber llegado al proveedor y tener coste aunque falle un paso posterior.

## Acceso y seguridad

- La aplicación exige autenticación de Nexia GP en producción
  (`NEXIAGP_AUTH_REQUIRED=1`). La API valida una sesión de Supabase y una membresía activa antes
  de devolver o modificar el estado editorial. No desactivar esta barrera mientras WordPress esté
  conectado.
- Las claves de OpenAI, Cloudinary, Supabase y el secreto del cron existen sólo como variables
  cifradas de producción en Vercel y, para uso local, en `.env`. Nunca copiarlas a GitHub, al
  frontend ni a documentación.
- El repositorio público ignora `.env`, archivos de claves, `data/db.json`, backups, estado de
  migración y `Documentación Nexia/`.
- Para dar acceso a una persona, crear o habilitar su membresía en Supabase y probar inicio de
  sesión, lectura de estado y una acción no destructiva. No compartir cuentas ni contraseñas de
  aplicación de WordPress.

## Variables de entorno de producción

Las variables se gestionan en Vercel para **Production**. Los nombres son públicos; sus valores no:

```text
OPENAI_API_KEY
OPENAI_MODEL
X_API_BEARER_TOKEN
CLOUDINARY_API_KEY
CLOUDINARY_API_SECRET
CLOUDINARY_CLOUD_NAME
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_STATE_BACKEND=1
NEXIAGP_AUTH_REQUIRED=1
WORDPRESS_BASE_URL
WORDPRESS_USERNAME
WORDPRESS_APPLICATION_PASSWORD
WORDPRESS_DEFAULT_CATEGORY_ID
WORDPRESS_AUTHOR_ID
CRON_SECRET
```

`SOCIAL_WEBHOOK_URL` sólo se añade cuando exista una integración social de publicación aprobada.

## Desarrollo y despliegue

### Entorno local

1. Copiar `.env.example` como `.env` y completar sólo las claves necesarias.
2. Instalar dependencias: `python -m pip install -r requirements.txt`.
3. Ejecutar: `python server.py`.
4. Abrir: `http://localhost:8787`.

Sin las variables de Supabase, el proyecto conserva un modo local de compatibilidad. Ese modo no
es la fuente de verdad de producción ni debe utilizarse para reemplazar el estado remoto.

### Entrega estándar

```powershell
python -m py_compile server.py api/index.py src/ai/services/image_service.py src/platform/supabase_store.py
python -m unittest discover -v
node --check public/app.js
git diff --check
git add -A
git commit -m "tipo: descripcion breve"
git push origin main
```

Un push a `main` inicia el despliegue automático de Vercel. Comprobar que el nuevo despliegue llega
a `READY` y probar como mínimo `/api/state`, una ruta de imagen existente y la interfaz principal.
No hacer una generación de OpenAI sólo para probar si no se desea incurrir en coste.

## Verificación y respuesta ante incidencias

| Síntoma | Comprobación inicial | Acción segura |
| --- | --- | --- |
| Pantalla vacía o verde | Abrir la URL estable y revisar el último despliegue Vercel. | Confirmar que HTML, CSS y JS pertenecen al mismo despliegue; revisar caché. |
| Imagen no generada | Logs de Vercel para `POST /api/posts/:id/generate-image`. | Confirmar Supabase y usar `/tmp`; no reintentar repetidamente. |
| Imagen 404 | Abrir `/images/<archivo>.png`. | Comprobar el objeto de `editorial-images` y la referencia persistida. |
| Estado desactualizado | Consultar `/api/state` y el despliegue activo. | No sobrescribir Supabase con `data/db.json` local. |
| WordPress pide revisión aunque ya se aceptó | Actualizar la app y confirmar que está desplegado `f939324` o posterior. | Si se cambió título, slug, metadatos o HTML, registrar la nueva revisión; si no hubo edición, abrir incidencia. |
| El borrador de WordPress falla | Revisar el error guardado en la ficha del blog y los logs de Vercel. | No repetir en cadena: comprobar primero los objetos de `editorial-images`, la conexión y el borrador existente. |
| SEO pendiente en Rank Math | Abrir el borrador en WordPress y revisar el panel de Rank Math. | Completar los campos allí; no impedir la revisión editorial ni publicar desde Nexia GP. |
| Push no despliega | Revisar el commit en `main` y la integración GitHub de Vercel. | Confirmar que la rama de producción es `main`. |

Para los logs: Vercel Dashboard → **Nexia GP / nexiagp-content** → Deployments/Logs. Para datos y
objetos: Supabase Dashboard del proyecto Nexia GP.

## Backups y recuperación

- El backup local anterior a la migración y el backup actual se mantienen fuera del repositorio.
- Supabase es el estado operativo actual; antes de cualquier restauración, exportar o verificar su
  versión remota y trabajar sobre una copia.
- GitHub protege el código y las migraciones, no los datos editoriales vivos.
- No borrar buckets ni copias locales como acción de mantenimiento ordinario.

## Límites y próximos ajustes

- Vercel Hobby es suficiente para el uso actual, con límites propios de funciones y cron. Revisar
  consumo si aumenta el volumen de generación o de imágenes.
- La integración social queda pendiente de decidir e implementar; el calendario actual es editorial,
  no prueba de publicación en LinkedIn u otras redes.
- Las mejoras de UX, prompts, calidad o flujos se realizarán a partir de pruebas reales del equipo
  y del cliente, siempre preservando el contrato existente.
