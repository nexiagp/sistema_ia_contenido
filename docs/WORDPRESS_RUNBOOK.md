# Operación WordPress — Nexia GP Content AI

**Actualizado:** 10 de noviembre de 2026
**Uso:** equipo editorial y mantenimiento técnico de la conexión con `nexiagp.com`.

**Revisión del 10/11/2026:** el exportador y las entradas existentes ya usan las clases
de bloque del tema y dejan el botón de contacto a la plantilla de Elementor. Se omite la imagen
`hero` del HTML: la plantilla ya coloca la destacada en cabecera y al inicio del cuerpo, como
en las entradas publicadas. El 10/11 se publicó el artículo de compraventa (WordPress `7408`),
con autor **Nexia GP**; los otros dos artículos (`7411` y `7415`) siguen como borradores. La
portada de logística sigue pendiente de sustituirse por una imagen sin mapa ni datos simulados.

## Estado actual

- La aplicación de producción exige la contraseña del equipo y usa el estado remoto como fuente de verdad.
- WordPress está conectado mediante un usuario técnico y una contraseña de aplicación almacenada
  únicamente como secreto de Production en Vercel.
- La integración crea o actualiza borradores. También permite publicar desde la aplicación
  después de las comprobaciones descritas abajo; nunca publica por una fecha del calendario.
- La entrada `7408` figura publicada en WordPress y en la aplicación. Los borradores `7411` y
  `7415` están en revisión editorial; no deben publicarse hasta resolver sus pendientes.
- Rank Math está instalado. La integración envía metatítulo, metadescripción y palabra clave
  mediante el endpoint nativo autenticado de Rank Math. La ficha distingue entre valores
  confirmados en la respuesta de WordPress y envío aceptado por Rank Math; la puntuación se
  comprueba en el editor.

## Flujo editorial acordado

```text
Generar blog en Nexia GP
        ↓
Revisar contenido, fuentes, SEO y figuras
        ↓
Registrar la revisión humana → estado Listo
        ↓
Crear/actualizar borrador WordPress
        ↓
Revisar diseño y Rank Math en WordPress
        ↓
Publicar desde WordPress o desde Nexia GP tras el control final
```

El calendario de Nexia GP organiza el plan editorial; no modifica por sí mismo el estado de una
entrada de WordPress.

## Uso diario

1. Abre **Blogs web**, elige el artículo y comprueba la vista previa, figuras y ficha SEO.
2. Pulsa **Aprobar contenido** para registrar la revisión humana.
3. Pulsa **Crear borrador en WordPress**. El primer envío sube las figuras optimizadas y crea una
   entrada en estado `draft`; los posteriores actualizan ese mismo borrador.
4. Pulsa **Abrir borrador** y revisa HTML, enlaces, CTA, imagen destacada y las imágenes interiores.
5. En Rank Math, valida metatítulo, metadescripción, keyword principal y los avisos de análisis.
   La app indica «aplicado» si WordPress devuelve los tres valores guardados; «recibió» si el
   endpoint nativo aceptó el envío sin devolver esos valores.
6. Para publicar desde la aplicación, introduce la **puntuación que ves en Rank Math** (70–100)
   y pulsa **Publicar en WordPress**. La aplicación comprueba el contenido y el borrador remoto,
   pide confirmación explícita, publica y vuelve a leer WordPress para verificar estado y autor.
7. Si publicas desde WordPress, pulsa **Comprobar publicación** en Nexia GP: la aplicación consulta
   la entrada asociada y sólo la marca como publicada cuando WordPress confirma que ya es pública.

La puntuación de Rank Math se introduce tras leerla en su editor: la integración actual puede
enviar sus campos, pero **no leer ni recalcular automáticamente la puntuación**. No interpretes
el número introducido como una auditoría independiente. Rank Math dispone de una herramienta MCP
para consultar metadatos y puntuación, pero esta instalación no la tiene conectada a la aplicación;
activarla exigiría configurar y probar su autenticación. [Documentación de Rank Math](https://rankmath.com/kb/mcp-tools/).

## Reglas importantes

- Sólo un artículo en `Listo` o `Programado` con revisión registrada puede enviarse a WordPress.
- Si se edita título, slug, meta título, meta descripción o el HTML del artículo, la aprobación se
  invalida y hay que revisarlo de nuevo. Es una protección intencional.
- La sincronización recalcula la calidad pero conserva la revisión ya registrada si el contenido no
  cambió. El arreglo se publicó en el commit `f939324`.
- Un borrador ya asociado se actualiza; una entrada publicada no se sobrescribe desde Nexia GP.
- Antes de actualizar un borrador existente, la aplicación consulta su estado real en WordPress.
  Si ya está publicado, bloquea la actualización para evitar que vuelva a `draft`.
- La publicación directa exige: estado `Listo`/`Programado`, control de calidad **sin bloqueos ni
  avisos**, título SEO, descripción de 110–170 caracteres, palabra clave, los tres campos de
  Rank Math enviados, borrador vigente y comprobado, autor `2` (**Nexia GP**), imagen destacada,
  HTML sin H1/cabecera duplicados ni enlaces pendientes, párrafos de bloque y al menos un H2.
  Una revisión editorial que aceptó bloqueos para crear el borrador **no** los salta al publicar.
- Si cambia el contenido, el SEO o una figura desde el último envío, la publicación directa se
  bloquea hasta actualizar el borrador. Los borradores anteriores a esta verificación también
  necesitan una nueva sincronización.
- No borrar el borrador de WordPress desde la app para corregir contenido: edítalo y usa
  **Actualizar borrador WordPress** cuando proceda.

## Qué se envía

| Desde Nexia GP | Resultado en WordPress |
| --- | --- |
| Título, slug, HTML y extracto | Entrada en `draft` |
| Autor | Usuario de WordPress `2`, cuyo nombre público es **Nexia GP** |
| Figuras editoriales | Biblioteca de medios, con JPEG optimizado |
| Figura `hero` o primera figura | Imagen destacada; Elementor la coloca en cabecera y al inicio del cuerpo |
| Caption de figura | Texto alternativo y pie de imagen |
| ID, URL, hash y fecha del borrador | Trazabilidad para actualizar sin duplicar |
| SEO de Rank Math | Título, descripción y keyword mediante su endpoint nativo; la lectura y puntuación se revisan en el editor |

## Contrato visual y editorial de cada artículo

1. La plantilla de Elementor «Entrada individual #216» aporta el H1, imagen destacada, colores,
   tipografía, firma **Nexia GP** y CTA «CONTACTAR». No duplicarlos en el cuerpo exportado.
2. El HTML exportado usa las clases `wp-block-*` del tema en párrafos, subtítulos, listas,
   tablas y figuras. La figura `hero` pasa a imagen destacada; las demás conservan `alt` y pie.
3. Revisar que el primer párrafo explique el tema, que la palabra clave encaje de forma natural,
   que haya subtítulos útiles, fuentes comprobables, enlaces internos válidos y ningún enlace o
   recurso pendiente. La aplicación conserva enlaces externos `https://` con dominio público,
   pero hay que comprobar su destino y la afirmación que respaldan antes de publicar.
4. Verificar en WordPress la tarjeta del blog, la entrada interior, escritorio y móvil, además de
   la vista previa de Rank Math. Su puntuación orienta la revisión; no garantiza posicionamiento.
5. Antes de publicar, confirmar título, slug, metatítulo, metadescripción, palabra clave,
   imagen destacada, autor y estado del borrador. Después verificar URL pública y estado `publish`.

La plantilla pública de Elementor ya añade título, imagen destacada y botón «CONTACTAR». El
exportador evita añadirlos otra vez en el HTML y aplica las clases de bloque usadas en las entradas
publicadas. Los colores, tipografías y botón proceden del tema actual. La vista previa de la app
mantiene su propio cierre para la revisión editorial.

## Sincronización nativa de Rank Math

La aplicación intenta primero los campos `meta` del REST de entradas cuando están expuestos y
WordPress devuelve los mismos valores. En esta instalación no se exponen; por ello usa
`/wp-json/rankmath/v1/updateMeta` con la contraseña de aplicación del usuario técnico. Se
envían `rank_math_title`, `rank_math_description` y `rank_math_focus_keyword` para la entrada
que acaba de guardarse como borrador. La respuesta del endpoint confirma que recibió la
operación, pero no devuelve esos valores para cotejarlos. Revisa los campos y la puntuación en
el editor antes de publicar. La puntuación es una guía de análisis, no una garantía de
posicionamiento. No hay que instalar un complemento adicional.

## Diagnóstico seguro

| Síntoma | Interpretación | Acción |
| --- | --- | --- |
| «Requiere una revisión humana» | Falta la aceptación o hubo una edición editorial posterior. | Revisa y vuelve a pulsar **Aprobar contenido**. |
| Artículo aceptado vuelve a pedir revisión sin haberse editado | Posible despliegue antiguo o regresión. | Actualiza la aplicación; comprobar en Vercel `f939324` o posterior y abrir incidencia si persiste. |
| Error al crear borrador | Puede afectar a una figura, a la conexión o a la respuesta de WordPress. | Lee el mensaje en la ficha; revisa logs de Vercel y no pulses repetidamente. |
| La imagen no llega | El activo editorial no está disponible en Storage o WordPress rechazó el medio. | Verificar `editorial-images` en Supabase y el medio existente en WordPress. |
| SEO no aparece completado | Rank Math rechazó el envío o el editor todavía no confirmó los valores. | Revisar permisos y los campos en WordPress; completar los campos manualmente si sigue sin funcionar. |

## Configuración técnica

Las variables se configuran sólo en **Vercel / Production**. Sus valores no se escriben en
documentos, commits ni variables públicas:

```text
WORDPRESS_BASE_URL
WORDPRESS_USERNAME
WORDPRESS_APPLICATION_PASSWORD
WORDPRESS_DEFAULT_CATEGORY_ID        # opcional
NEXIAGP_AUTH_REQUIRED=1
SUPABASE_STATE_BACKEND=1
```

El servidor requiere autenticación activa para aceptar la sincronización. Si la app pasa a ser
pública, la operación se bloquea por diseño.

## Recuperación y cambios futuros

- Antes de cambiar el tema, el plugin SEO o un plugin de seguridad de WordPress, crear un borrador
  de prueba y validar contenido, figuras y Rank Math.
- Si se renueva la contraseña de aplicación, actualizar sólo el secreto de Vercel y probar la
  conexión desde **Ajustes**; nunca pegarla en la app ni en un documento.
- Para habilitar programación automática, definir primero quién la aprueba, cómo se evita publicar
  cambios no revisados y un mecanismo de reversión. No activar `publish` como consecuencia de una
  fecha del calendario.
- Los tokens y funciones temporales usados durante una migración deben borrarse y revocarse al
  finalizar. La migración de activos de 01/09/2026 se cerró de esta forma.

Ver también [Arquitectura y operación](ARQUITECTURA_Y_OPERACION.md) y la
[Guía de uso](GUIA_DE_USO.md).
