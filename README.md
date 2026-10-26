# Nexia GP Content AI

Aplicación editorial de Nexia Growth Partner para crear, revisar, ilustrar y planificar contenido B2B: publicaciones de LinkedIn con adaptaciones a X, Facebook e Instagram y artículos de blog orientados a SEO.

**Producción:** <https://nexiagp-content.vercel.app>
**Código:** <https://github.com/nexiagp/sistema_ia_contenido>

## Empieza aquí

- **Para utilizar la aplicación:** [Guía completa de uso](docs/GUIA_DE_USO.md).
- **Para operar, mantener o desplegar:** [Arquitectura y operación](docs/ARQUITECTURA_Y_OPERACION.md).
- **Para crear y revisar borradores web:** [Runbook de WordPress](docs/WORDPRESS_RUNBOOK.md).
- **Para el estado comprobado de blogs, acceso y redes (26/10/2026):** [Revisión y pasos pendientes](docs/REVISION_BLOGS_Y_REDES_2026-10-26.md).
- **Para las fuentes de fabricantes y el plan de continuidad:** [Estado y hoja de ruta (31/08/2026)](docs/ESTADO_Y_HOJA_DE_RUTA_2026-08-31.md).
- **Para retomar el desarrollo:** [Estado del proyecto](PROJECT_STATE.md) y [changelog](CHANGELOG.md).

El acceso de equipo por contraseña está activo en producción. La aplicación conserva el estado
editorial en Supabase; la contraseña privada está guardada fuera del repositorio.

## Qué permite hacer

- Crear borradores de posts para LinkedIn y sus adaptaciones para X, Facebook e Instagram, a partir de una pauta editorial, fuentes y prompts versionados.
- Revisar, editar, copiar, exportar y aprobar las piezas antes de llevarlas al calendario editorial.
- Generar y comparar imágenes de post; aplicar marco y logo Nexia por separado y descargar el PNG final elegido.
- Crear artículos de blog con HTML, SEO, JSON-LD, fuentes, figuras y vista previa editorial.
- Cargar y sincronizar documentos en la biblioteca de fuentes para alimentar el contexto de generación.
- Gestionar calendario, cadencia, automatización de borradores, tipos de contenido, prompts y límites operativos.

La agenda es editorial: **programar una pieza no la publica en redes**. Las cuentas de X,
LinkedIn e Instagram no tienen todavía una conexión de publicación verificada.

## Arquitectura de producción

```text
Navegador
   │ HTTPS
   ▼
Vercel · SPA + API Python + cron diario
   ├── OpenAI · texto, imágenes y Vector Store
   ├── Supabase · estado editorial y ficheros persistentes
   └── Cloudinary · entrega opcional de imágenes

GitHub (main) ── push ──► Vercel · despliegue automático
```

| Servicio | Qué aloja o realiza |
| --- | --- |
| **Vercel** | La aplicación pública, la API Python, funciones serverless y el cron. |
| **Supabase** | Fuente de verdad del estado editorial, biblioteca, imágenes y activos de marca. |
| **OpenAI** | Generación de texto e imágenes y consulta del Vector Store. Sólo se invoca desde el servidor. |
| **Cloudinary** | Entrega opcional de imágenes ya persistidas; no es necesario para conservarlas. |
| **GitHub** | Código, migraciones, pruebas y documentación pública del sistema. |

Los detalles de buckets, recuperación, variables y límites están en la [documentación de arquitectura](docs/ARQUITECTURA_Y_OPERACION.md).

## Uso diario, en cuatro pasos

1. En **Sistema editorial IA**, rellena el briefing y ejecuta el pipeline para crear un borrador.
2. En **Revisión editorial**, valida el copy y las fuentes, edita lo necesario y reconoce la revisión cuando la puerta de calidad lo solicite.
3. Genera o elige la imagen, aprueba la pieza y llévala al **Calendario editorial**.
4. Reserva fecha y hora en el calendario. Para un blog, crea antes el borrador en WordPress y
revisa Rank Math; la publicación final sigue siendo manual desde el CMS.

Para artículos, entra en **Blogs web** y pulsa **Crear blog**. Si ya hay artículos, el formulario aparece recogido dentro de ese botón.

## Desarrollo local

Requisitos: Python y las dependencias de `requirements.txt`.

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python server.py
```

Abrir <http://localhost:8787>. Completa `.env` únicamente con las variables que necesites para el entorno local. No copies ni subas valores de producción.

Para una segunda instancia local:

```powershell
$env:PORT = '8789'
python server.py
```

En producción, Supabase es la fuente de verdad. El modo local sin Supabase existe para compatibilidad y pruebas, pero no sustituye el estado remoto.

## Entrega de cambios

La rama `main` está conectada al proyecto de Vercel **Nexia GP / nexiagp-content**. Un push validado inicia automáticamente un despliegue de producción.

```powershell
python -m py_compile server.py api/index.py src/ai/services/image_service.py src/platform/supabase_store.py
python -m unittest discover -v
node --check public/app.js
git diff --check
git add -A
git commit -m "tipo: descripcion breve"
git push origin main
```

Tras el despliegue, comprobar al menos la interfaz, `GET /api/state` y una imagen existente. No generar contenido ni imágenes sólo para comprobar el despliegue: esas acciones pueden consumir saldo de OpenAI.

## Estructura del repositorio

```text
api/                 Entrada serverless para Vercel
public/              Interfaz web (SPA, estilos y recursos públicos)
src/ai/              Pipelines, prompts, validación y servicios de IA
src/domain/          Modelos y reglas de contenido
src/platform/        Persistencia y adaptadores de Supabase
supabase/migrations/ Esquema y cambios de base de datos
scripts/             Migración, verificación y utilidades de mantenimiento
test_*.py            Pruebas offline de reglas editoriales, imágenes y calendario
docs/                Guías de uso, arquitectura y operación
```

## Seguridad y límites

- Los secretos operativos viven en las variables de Production de Vercel. Las credenciales de preparación local permanecen en `.env` o `secrets/`, ambos excluidos de Git; no equivalen a una conexión activa en producción.
- El repositorio no debe contener `.env`, claves, contenido editorial vivo, backups ni documentación interna.
- Crear contenido, regenerar adaptaciones, sincronizar OpenAI o generar imágenes puede tener coste.
- No borrar posts, blogs, archivos de biblioteca ni objetos de Supabase sin una decisión editorial explícita.
- Si se requiere restringir el acceso por enlace, debe planificarse y probarse el cambio de autenticación antes de activarlo.

## Incidencias y continuidad

Consulta la tabla de diagnóstico, los backups y la recuperación en [Arquitectura y operación](docs/ARQUITECTURA_Y_OPERACION.md). Para cambios funcionales o de UX, preserva los flujos existentes y actualiza la guía de uso cuando cambie el comportamiento del editor.
