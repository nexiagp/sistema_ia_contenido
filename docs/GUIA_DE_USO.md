# Guía de uso — Nexia GP Content AI

**Actualizada:** 1 de septiembre de 2026
**Dirigida a:** equipo editorial, dirección comercial y cliente de Nexia GP.
**Aplicación:** <https://nexiagp-content.vercel.app>

Esta guía explica el uso diario de la aplicación de contenido. Para cambios técnicos, despliegues o recuperación, consultar [Arquitectura y operación](ARQUITECTURA_Y_OPERACION.md).

## Antes de empezar

1. Abre el enlace de producción en un navegador actualizado.
2. Actualiza la página si otra persona acaba de crear o modificar contenido.
3. Define antes el objetivo, audiencia, tesis, CTA y evidencia disponible.

El acceso requiere una sesión autorizada de Nexia GP. Trátalo como un acceso de trabajo: no
compartas cuentas, claves, información sensible ni documentos sin autorización.

> Generar texto, regenerar adaptaciones, crear imágenes y sincronizar la biblioteca con OpenAI puede consumir saldo. Revisa el encargo antes de solicitar una generación.

## Mapa de la aplicación

| Sección | Para qué sirve |
| --- | --- |
| **Sistema editorial IA** | Crear posts de redes a partir de un briefing. |
| **Revisión editorial** | Revisar, editar, aprobar, exportar e ilustrar posts. |
| **Blogs web** | Crear y preparar artículos con SEO y figuras. |
| **Biblioteca y fuentes** | Añadir y gestionar los documentos que sustentan las generaciones. |
| **Prompts versionados** | Consultar el catálogo de enfoques y tipos de post. |
| **Calendario editorial** | Reservar fecha y hora para posts y artículos preparados. |
| **Automatización** | Configurar o ejecutar la cadencia editorial. |
| **Ajustes** | Configurar valores generales, blog y versiones de prompt. |

El botón superior **Nuevo post** lleva a *Sistema editorial IA*; no crea un artículo de blog. Para un blog, abre **Blogs web** y pulsa **Crear blog**.

## Flujo recomendado

```text
Fuentes actualizadas
        ↓
Crear borrador → revisar copy y fuentes → generar/elegir imagen
        ↓
Reconocer revisión de calidad → preparar para calendario → reservar fecha/hora
        ↓
Publicación manual en la red o CMS correspondiente
```

El calendario organiza la agenda editorial. No publica automáticamente en LinkedIn, X, Facebook ni en el CMS. Cuando esté configurada la conexión de WordPress, ésta sólo crea o actualiza un **borrador**: la programación y publicación final se realizan allí de forma manual.

## Crear un post para redes

1. Abre **Sistema editorial IA** o pulsa **Nuevo post**.
2. Completa el briefing:
   - **Canal** y **tipo de post**: deja *automático* cuando el sistema pueda escoger el formato; selecciónalo sólo si ya existe una decisión editorial.
   - **Audiencia**, **objetivo** y **sector**: aporta el contexto comercial básico.
   - **Marca, entidad o tema**: úsalo sólo cuando sea una fuente o asunto aprobado.
   - **Tema libre**: expresa la tesis, novedad o problema que se debe abordar.
   - **CTA**, nivel promocional y notas humanas: fijan el cierre y los matices imprescindibles.
   - Activa las adaptaciones a X/Facebook si también son necesarias.
3. Pulsa **Ejecutar pipeline**.
4. Espera a que termine el trabajo. La aplicación muestra los pasos y lleva el resultado a **Revisión editorial**.

No cierres ni recargues por impaciencia durante un trabajo. Si la página se cierra, vuelve más tarde a revisión y actualiza: el resultado se guarda de forma persistente al completarse.

### Qué revisar antes de aprobar

- La idea principal se entiende al leer las primeras líneas.
- La afirmación comercial es precisa y no atribuye datos, clientes o resultados sin sustento.
- Las fuentes asociadas son pertinentes. Si faltan documentos, corrige primero la biblioteca.
- El CTA coincide con el objetivo y el tono corresponde a Nexia GP.
- La adaptación de X respeta el límite de caracteres y Facebook no es una copia literal de LinkedIn.

## Revisar, editar y aprobar un post

En **Revisión editorial** se concentra el trabajo sobre cada pieza:

1. Usa filtros de estado y buscador para localizar el post.
2. Abre la tarjeta para ver copy, resumen de calidad, fuentes y adaptaciones por canal.
3. Usa **Editar** para ajustar copy, hashtags o CTA. Guarda antes de cambiar de sección.
4. Usa **Copiar** para llevar la versión al gestor social, o exporta el listado filtrado en CSV/JSON cuando necesites inventario.
5. Si aparece una puerta de calidad, revisa los bloqueos y confirma la revisión. Cualquier edición posterior vuelve a exigirla.
6. Pulsa **Aprobar para calendario** cuando la pieza esté preparada.

### Regenerar

- **Regenerar post** solicita una nueva redacción y puede tener coste. Úsalo al cambiar el planteamiento, no para un ajuste menor.
- **Regenerar adaptaciones** rehace X/Facebook; revísalas de nuevo antes de utilizarlas.
- Para un cambio de voz, dato o CTA, normalmente es preferible editar el borrador existente.

### Estados

| Estado | Significado práctico |
| --- | --- |
| **Borrador** | Aún requiere revisión editorial. |
| **Listo** | Revisado y preparado para entrar en la agenda. |
| **Programado** | Tiene fecha y hora reservadas en el calendario editorial. |
| **Publicado** | Sólo debe usarse tras confirmar la publicación realizada fuera de la aplicación. |

No elimines un post para corregirlo: edítalo o conserva una nueva variante, salvo retirada editorial definitiva.

## Crear y gestionar imágenes de post

Desde el detalle de un post puedes **Generar imagen** o crear una nueva variante. Antes de solicitarla, define:

- Formato (horizontal, cuadrado o vertical) según el canal y la composición.
- Calidad y dirección visual; elige una intención concreta y evita pedir texto dentro de la imagen.
- Encuadre, marco de marca y notas visuales cuando sean necesarios.

Después:

1. Comprueba que la imagen representa la tesis sin inventar marcas, datos o elementos sensibles.
2. Compara las variantes guardadas y selecciona la que se utilizará.
3. Usa **Descargar PNG** para conservar el archivo final de publicación.

Las imágenes originales y sus versiones con marco se guardan de forma persistente. Si una imagen no carga, no repitas muchas veces la generación: actualiza, prueba la descarga y comunica el post concreto junto a la hora aproximada de la incidencia.

## Crear un artículo de blog

1. Entra en **Blogs web**.
2. Pulsa **Crear blog**. Si ya existen artículos, el formulario queda recogido dentro de ese botón.
3. Completa el encargo:
   - **Tema o tesis**: obligatorio; define qué debe aprender o decidir el lector.
   - **Intención de búsqueda** y **framework**: alinean el artículo con SEO y estructura editorial.
   - **Audiencia**, longitud y sector: añaden contexto comercial.
   - **CTA temático** y notas humanas: completan el encargo. El cierre final mantiene el CTA editorial fijo de Nexia GP.
   - **Imágenes por artículo**: establece de 0 a 6 antes de generar.
4. Inicia la generación y espera al trabajo asíncrono.

### Revisar un blog

Selecciona el artículo en el catálogo y revisa:

- Vista previa, estructura, tono y afirmaciones.
- Ficha SEO, metadatos, enlazado y JSON-LD.
- Brief y fuentes que lo sustentan.
- Figuras previstas y su coherencia con el contenido.

Puedes **copiar HTML** o **descargar HTML** si necesitas una entrega manual. Antes de hacerlo, confirma que el CMS no alterará el marcado y que las imágenes descargadas se subirán al alojamiento correspondiente.

Para el flujo conectado con WordPress, usa siempre esta secuencia visible en la ficha del blog:

1. **Aprobar contenido**: registra la revisión editorial y deja el artículo listo para WordPress. Si hay una puerta de calidad, revisa sus avisos antes de confirmarla.
2. **Crear borrador en WordPress**: envía o actualiza el borrador con el contenido y las imágenes optimizadas. Este paso nunca publica el artículo. Si Rank Math expone sus campos a la API, también completa metatítulo, metadescripción y keyword principal; si no, la ficha señala esos tres campos para revisión manual antes de publicar. Si editas título, slug, metadatos o HTML después de aprobar, vuelve a registrar la revisión antes de enviarlo.
3. **Reservar fecha**: se realiza desde **Calendario editorial** y sólo organiza la agenda interna. Después de revisar el borrador, programa o publica manualmente desde WordPress según el proceso acordado por el equipo.

Eliminar un artículo es irreversible desde la interfaz: confirma primero que no se necesitará como referencia o versión base.

### Figuras de blog

Cada figura admite formato, calidad, dirección visual, composición, marco y notas. La configuración de blog incorpora un límite de coste estimado para imágenes; si se alcanza, reduce el número de figuras o revisa el presupuesto en **Ajustes → Blog** antes de solicitar otra.

## Biblioteca y fuentes

La biblioteca es el fundamento del contenido verificable. Antes de tratar una afirmación como factual, asegúrate de que existe una fuente fiable y disponible.

### Añadir material

1. Entra en **Biblioteca y fuentes**.
2. Selecciona la categoría: Nexia Core, Web, Blog, Fabricante, Mercado temporal o Copywriting.
3. Sube el documento y espera a que termine la incorporación.
4. Sincroniza con OpenAI/Vector Store sólo si el documento debe entrar en las recuperaciones de IA.

Se admiten `.txt`, `.md`, `.pdf`, `.docx`, `.csv` y `.xlsx`, con un máximo de 50 MB por archivo. Comprueba derechos, vigencia y confidencialidad antes de subir material.

### Gestionar material existente

- Usa filtros para distinguir archivos sincronizados, pendientes o locales.
- Conserva nombres y categorías que permitan localizar la fuente después.
- No borres una fuente que sostiene contenido publicado sin conservar copia y sin actualizar sus dependencias.

## Calendario editorial

1. Abre **Calendario editorial**.
2. Elige si quieres planificar un post o un blog preparado y sin fecha.
3. Selecciona pieza, fecha y hora.
4. Pulsa **Añadir** o **Reprogramar** y verifica el resultado en la vista mensual o de lista.

El calendario es la agenda interna. Al llegar la fecha, publica manualmente en la plataforma correspondiente. Para un blog, revisa primero su borrador en WordPress y programa o publica allí según el proceso del equipo; reservar la fecha en Nexia GP no cambia el estado del artículo en la web.

## Automatización, ajustes y prompts

Estas secciones alteran el comportamiento general. Úsalas sólo con una decisión editorial clara.

### Automatización

- Activa o desactiva el scheduler, define la cadencia, el tipo por defecto y el modo de salida.
- **Ejecutar ahora** puede iniciar generación y tener coste.
- Revisa el historial después de cada ejecución.

Aunque se active la automatización, no hay publicación social real sin una integración aprobada. El resultado sigue el flujo de borrador, revisión y calendario.

### Ajustes generales y de blog

- No cambies modelo, Vector Store, claves ni backend de estado sin coordinación técnica.
- Revisa con atención número de imágenes, calidad y límite estimado de coste del blog.
- Los valores por defecto afectan a futuras generaciones; no reescriben contenido ya creado.

### Prompts versionados

Los prompts se consultan en **Prompts versionados** y se editan en **Ajustes → Prompts**.

1. Identifica el prompt y redacta el objetivo del cambio.
2. Edita sólo lo necesario y guarda: el sistema crea una versión.
3. Prueba el cambio en un borrador representativo y revisa el resultado humano.
4. Si empeora el resultado, usa el historial para restaurar una versión anterior.

Los prompts nuevos sólo se aplican a generaciones posteriores. No deben contener secretos, datos no autorizados ni instrucciones que contradigan las puertas de calidad.

## Buenas prácticas editoriales

- Parte de una tesis concreta y una evidencia identificable; no de un tema genérico.
- Revisa cada dato, nombre de cliente, cifra y promesa antes de aprobar.
- Usa la IA para acelerar borradores, no para sustituir la validación profesional.
- Mantén el mensaje comercial útil: problema, perspectiva, consecuencia y CTA coherentes.
- Guarda la versión final que se publicó fuera de la aplicación cuando haya cambios manuales en la red o CMS.
- Si otra persona puede editar al mismo tiempo, actualiza antes de modificar y antes de programar para no trabajar sobre una versión antigua.

## Incidencias frecuentes

| Situación | Acción segura |
| --- | --- |
| No veo el formulario de blog | En **Blogs web**, abre **Crear blog**; queda plegado cuando ya hay artículos. |
| Pantalla vacía o desactualizada | Recarga la URL estable. Si continúa, anota hora y captura; no generes contenido para probar. |
| Un trabajo tarda | Espera a que finalice y actualiza *Revisión editorial* o *Blogs web*. No lances encargos duplicados. |
| No puedo preparar una pieza | Lee los bloqueos de calidad y confirma la revisión después de corregirlos. |
| No puedo crear el borrador de WordPress | Comprueba que el artículo está en **Listo** y con la revisión registrada. Si se editó título, slug, metadatos o HTML, apruébalo otra vez. Si aparece otro error, consulta el mensaje en la ficha y no reintentes en cadena. |
| Imagen no aparece | Actualiza, prueba descargar el PNG y comunica ID/título; no reintentes en cadena. |
| No se publica al programar | Es el comportamiento actual: el calendario no tiene publicación automática integrada. |
| Quiero borrar contenido o una fuente | Detente y confirma decisión editorial y copia cuando sea necesaria. |

Para la operación y las incidencias específicas de WordPress, consulta el [Runbook de
WordPress](WORDPRESS_RUNBOOK.md). Para incidencias técnicas recurrentes, consulta
[Arquitectura y operación](ARQUITECTURA_Y_OPERACION.md), donde se indica cómo revisar Vercel y Supabase.
