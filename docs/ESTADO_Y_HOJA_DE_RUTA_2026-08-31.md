# Estado y hoja de ruta — fuentes de fabricantes

**Actualizado:** 31 de agosto de 2026  
**Ámbito:** sistema editorial de Nexia GP, sus fuentes para posts/blogs y la automatización editorial.

Esta es la referencia de continuidad para la ampliación de fuentes acordada con Nexia. Complementa la [arquitectura y operación](ARQUITECTURA_Y_OPERACION.md) y la [guía de uso](GUIA_DE_USO.md); no sustituye los procedimientos de seguridad ni los controles editoriales existentes.

## Estado actual verificado

| Elemento | Estado |
| --- | --- |
| Biblioteca editorial | 67 documentos completados en la Vector Store de OpenAI; 0 fallidos o pendientes. |
| Fuentes de fabricantes | 21 webs oficiales extraídas y registradas como documentos de fabricante. |
| Uso por IA | Las fuentes se almacenan en la misma biblioteca y Vector Store que ya consulta el pipeline de posts y blogs. |
| Scheduler | Activo, una pieza cada 3 días, con rotación de todas las temáticas activas. |
| Salida del scheduler | `draft`: genera borradores; no publica por sí solo. |
| Tratamiento inicial de imagen de post | Marco Nexia + logo Nexia activados para el primer visual que se solicite. El scheduler no genera imágenes automáticamente ni consume crédito de imagen sin una acción editorial. |
| X | Ninguna cuenta activada todavía. La integración queda preparada, pero no hace llamadas ni incurre en consumo hasta configurar y habilitar una cuenta. |

El estado anterior se ha comprobado en el entorno local de trabajo. El código y el catálogo deben desplegarse y sincronizarse con el estado de Supabase de producción antes de considerar este mismo inventario disponible en la URL pública.

## Fabricantes incorporados

Airum, AR Blue Clean, STANLEY Tools, Altuna Group, ODEM, Vithal Garden, BIV, PIHER, Diadora Utility, Marefix, Catmader, DCK Power Tools, Fireside, TAGU, Sahara BBQs, Paul Voormann, Sesa Tools, Saviola, Fabricados LMG, Catral Group y Sibol Spaciani.

El listado procede del catálogo de distribuidores de [Nexia GP](https://nexiagp.com/distribuidores/). Cada registro conserva únicamente una web oficial verificada y su estado de actualización; las URLs sociales que aparezcan en ella se descubren pero no se usan como fuente automática salvo X, con la configuración descrita más abajo.

## Cómo fluye una fuente hasta un post o blog

```text
Web oficial del fabricante
        │ actualización manual, limitada al dominio y a un máximo de 5 páginas
        ▼
Documento Markdown local de fabricante
        │ "Sincronizar OpenAI" explícito
        ▼
Vector Store de OpenAI
        │ recuperación verificable del pipeline
        ├── Post editorial
        └── Blog SEO
```

La aplicación no publica ni reescribe automáticamente una novedad de fabricante. La fuente aporta contexto recuperable; la validación y la revisión humana siguen bloqueando el paso a `ready`, `scheduled` o `published` cuando corresponde.

Al actualizar una fuente ya sincronizada se conserva un único documento lógico. En la siguiente sincronización, la aplicación reemplaza de forma controlada su adjunto anterior del Vector Store para no duplicar contexto.

## Automatización editorial

El scheduler está activado con `cadenceDays = 3` y selecciona una sola temática activa mediante rotación circular. Así evita generar siempre las primeras temáticas configuradas. La ejecución manual también usa esa rotación.

- Si no hay una ejecución previa, el siguiente cron puede crear el primer borrador.
- El modo de salida actual es `draft`; por tanto, el scheduler no publica en redes ni en la web.
- El marco y el logo son dos controles independientes, pero los posts nuevos y los creados por scheduler parten de ambos activados.
- Los blogs conservan su tratamiento visual limpio por defecto; marco y logo pueden activarse de forma independiente al crear cada figura.

## Monitorización de redes sociales

### X, única red automatizable por ahora

Para cada fabricante, un editor debe confirmar el identificador de la cuenta y activar “Monitorizar X”. También hace falta configurar en el servidor la variable privada `X_API_BEARER_TOKEN`; jamás se guarda ni se entrega al navegador.

Cuando se cumplen ambas condiciones, el cron diario consulta los posts recientes mediante la API oficial de X, ignora respuestas y reposts, evita duplicados y guarda las novedades como fuente local antes de su sincronización al Vector Store. El cron procesa hasta diez cuentas habilitadas por ejecución para mantener un tiempo de ejecución controlado.

La implementación usa sondeo de timeline, no una conexión de stream persistente, porque el entorno serverless ejecuta tareas breves. X también ofrece Filtered Stream para conexiones persistentes y entrega por webhook, una alternativa a valorar si el volumen o la inmediatez futura lo justifican. [Documentación oficial de X](https://docs.x.com/x-api/posts/filtered-stream/introduction)

### Instagram y LinkedIn

Los enlaces que aparezcan en la web de cada marca se muestran en la aplicación para revisión manual. No se recogen ni se publican contenidos automáticamente en estas redes en esta fase.

## Operación diaria recomendada

1. En **Biblioteca y fuentes**, actualizar la web de una marca cuando exista una novedad que interese tratar.
2. Revisar el documento local creado y, si procede, pulsar **Sincronizar OpenAI**.
3. Crear o revisar el post/blog. Confirmar las fuentes recuperadas y superar la puerta de calidad antes de prepararlo para calendario.
4. Para X, confirmar el usuario oficial antes de activar el interruptor; no aceptar automáticamente una cuenta solo porque se haya detectado un enlace.
5. Mantener el scheduler activo si se desea el borrador de cada tres días. Pausarlo solo en periodos editoriales de cierre.

## Tareas pendientes

### Requieren una decisión o acceso del equipo

- Desplegar este cambio y sembrar el catálogo/estado de fuentes en Supabase de producción. La sincronización OpenAI ya realizada corresponde al entorno local actual; la URL pública necesita el despliegue y su estado persistente para catalogar las fuentes también allí.
- Configurar `X_API_BEARER_TOKEN` en el entorno de producción y confirmar, una a una, las cuentas oficiales de X que Nexia tenga autorización para monitorizar.
- Definir con Begoña/marketing el mecanismo de publicación automática de blogs en la web: CMS de destino, credenciales, estados de aprobación, imágenes, URL final y gestión de errores.
- Decidir si se añade un webhook social aprobado (`SOCIAL_WEBHOOK_URL`). Mientras no exista, la aplicación conserva los posts en revisión/listos y no los publica.

### Pendientes funcionales del acta de reunión

- Implementar SEO local sencillo para reforzar presencia de Nexia en Canarias.
- Evaluar la automatización del LinkedIn de Ángel, con autorización y reglas de revisión.
- Crear y preparar el Instagram corporativo de Nexia; seguirá siendo una carga/revisión manual hasta que se apruebe una integración.
- Definir una política editorial para novedades de fabricante: qué fuentes se pueden citar, qué requiere validación comercial/técnica y cuándo caduca una información.

### Mejora recomendada posterior

- Añadir una vista de “novedades detectadas” que compare la última extracción de cada fabricante con la anterior antes de convertirla en fuente editorial.
- Medir el consumo de X y OpenAI por fabricante para mantener previsibilidad de coste.

## Verificación realizada en esta actualización

- 21 documentos de fabricante sincronizados correctamente; la operación también completó un adjunto anterior que estaba en seguimiento: 22 sincronizaciones correctas y 0 errores.
- Estado final comprobado: 67 documentos completados, 21 de fabricantes, 0 pendientes y 0 fallidos.
- Scheduler comprobado activo, cadencia de tres días y modo de salida en borrador.
- Pruebas offline, análisis sintáctico de Python/JavaScript y comprobación de espacios de Git ejecutados antes del cierre.

