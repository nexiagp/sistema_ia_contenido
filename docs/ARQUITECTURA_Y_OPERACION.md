# Arquitectura y operación — Nexia GP Content AI

**Actualizado:** 24 de agosto de 2026
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

## Flujo de generación de contenido

1. El editor crea un post o blog desde la SPA.
2. La API ejecuta el pipeline: planificación, recuperación de contexto del Vector Store, redacción,
   validación editorial y adaptaciones.
3. El resultado, fuentes, quality gate y uso se escriben de forma transaccional en Supabase.
4. El editor revisa el borrador antes de marcarlo como listo o programarlo.
5. La publicación social real no se activa sin un `SOCIAL_WEBHOOK_URL` válido; a fecha de este
   documento no hay webhook configurado.

Los trabajos largos se guardan y recuperan desde el backend persistente para que una invocación
serverless interrumpida no pierda silenciosamente el estado del encargo.

## Flujo de generación de imágenes

1. La API obtiene un prompt visual y solicita la imagen a OpenAI.
2. En Vercel, el PNG se escribe temporalmente en `/tmp/nexiagp-images`.
3. Se valida formato, tamaño y dimensiones; si se solicita, se compone localmente el marco de
   marca.
4. El PNG original y, si existe, el PNG compuesto se suben al bucket `editorial-images` de
   Supabase antes de terminar la invocación.
5. Se guarda sólo la referencia `/images/...` y los metadatos de validación en el estado. Los
   archivos temporales se eliminan tras el éxito.

Si falla antes de la persistencia, revisar los registros de Vercel y no reintentar a ciegas: una
solicitud de imagen puede haber llegado al proveedor y tener coste aunque falle un paso posterior.

## Acceso y seguridad

- El acceso actual es **directo por enlace**: `NEXIAGP_AUTH_REQUIRED=0` y la protección SSO de
  Vercel está desactivada por decisión operativa. Cualquier persona que conozca la URL puede abrir
  la aplicación.
- Las claves de OpenAI, Cloudinary, Supabase y el secreto del cron existen sólo como variables
  cifradas de producción en Vercel y, para uso local, en `.env`. Nunca copiarlas a GitHub, al
  frontend ni a documentación.
- El repositorio público ignora `.env`, archivos de claves, `data/db.json`, backups, estado de
  migración y `Documentación Nexia/`.
- Si en el futuro se requiere acceso restringido, activar `NEXIAGP_AUTH_REQUIRED=1`, verificar la
  membresía correspondiente en Supabase y volver a probar acceso, sesiones y API antes de abrirlo
  al equipo.

## Variables de entorno de producción

Las variables se gestionan en Vercel para **Production**. Los nombres son públicos; sus valores no:

```text
OPENAI_API_KEY
OPENAI_MODEL
CLOUDINARY_API_KEY
CLOUDINARY_API_SECRET
CLOUDINARY_CLOUD_NAME
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_STATE_BACKEND=1
NEXIAGP_AUTH_REQUIRED=0
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
