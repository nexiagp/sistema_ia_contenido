# Operación WordPress — Nexia GP Content AI

**Actualizado:** 10 de noviembre de 2026
**Uso:** equipo editorial y mantenimiento técnico de la conexión con `nexiagp.com`.

**Revisión del 26/10/2026:** las tres vistas previas muestran la portada repetida dentro del
artículo. El exportador corregido la omite y retira recursos sin enlace, pero ese cambio aún no
está desplegado ni aplicado a los borradores existentes. La portada del artículo de logística
debe sustituirse por una imagen sin mapa ni datos simulados. Ver [revisión visual y enlaces](REVISION_BLOGS_Y_REDES_2026-10-26.md).

## Estado actual

- La aplicación de producción se autentica con Supabase y usa el estado remoto como fuente de verdad.
- WordPress está conectado mediante un usuario técnico y una contraseña de aplicación almacenada
  únicamente como secreto de Production en Vercel.
- La integración crea o actualiza **borradores**; no publica ni programa entradas de WordPress.
- El piloto inicial se verificó con tres artículos aprobados y los tres permanecen en `draft`.
- Rank Math está instalado. Para sincronizar sus tres campos SEO por REST, el complemento
  `wordpress/nexiagp-rankmath-rest` debe estar activo en WordPress. Si no lo está, la ficha
  muestra explícitamente que queda revisión manual.

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
Programar o publicar manualmente desde WordPress
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
   La app sólo indica «aplicado» cuando WordPress devuelve los tres valores guardados.
6. Marketing programa o publica desde WordPress. Registra la publicación en Nexia GP sólo después
   de comprobarla en la web.

## Reglas importantes

- Sólo un artículo en `Listo` o `Programado` con revisión registrada puede enviarse a WordPress.
- Si se edita título, slug, meta título, meta descripción o el HTML del artículo, la aprobación se
  invalida y hay que revisarlo de nuevo. Es una protección intencional.
- La sincronización recalcula la calidad pero conserva la revisión ya registrada si el contenido no
  cambió. El arreglo se publicó en el commit `f939324`.
- Un borrador ya asociado se actualiza; una entrada publicada no se sobrescribe desde Nexia GP.
- No borrar el borrador de WordPress desde la app para corregir contenido: edítalo y usa
  **Actualizar borrador WordPress** cuando proceda.

## Qué se envía

| Desde Nexia GP | Resultado en WordPress |
| --- | --- |
| Título, slug, HTML y extracto | Entrada en `draft` |
| Figuras editoriales | Biblioteca de medios, con JPEG optimizado |
| Figura `hero` o primera figura | Imagen destacada, sin repetirse dentro del cuerpo tras aplicar el exportador corregido |
| Caption de figura | Texto alternativo y pie de imagen |
| ID, URL, hash y fecha del borrador | Trazabilidad para actualizar sin duplicar |
| SEO de Rank Math | Título, descripción y keyword si el puente REST está activo y confirma la lectura; si no, revisión manual |

La plantilla pública de Elementor ya añade título, imagen destacada y botón «CONTACTAR». El
exportador elimina esos duplicados del HTML y aplica las clases de bloque usadas en las entradas
publicadas. Los colores, tipografías y botón proceden del tema actual. La vista previa de la app
mantiene su propio cierre para la revisión editorial.

## Puente REST de Rank Math

El código fuente está en `wordpress/nexiagp-rankmath-rest/nexiagp-rankmath-rest.php`.
Se instala como complemento ZIP desde **Plugins → Añadir plugin → Subir plugin** y se activa.
Registra únicamente `rank_math_title`, `rank_math_description` y `rank_math_focus_keyword`
para entradas, con escritura limitada a usuarios que pueden editar la entrada. No añade CSS ni
modifica contenido publicado. Para comprobarlo, consultar con autenticación el esquema REST de
`/wp-json/wp/v2/posts` y confirmar que los tres campos aparecen en `meta.properties`.

Después de activar el complemento, sincronizar un borrador revisado y comprobar en la respuesta
de WordPress que los tres valores coinciden. La puntuación de Rank Math se revisa en el editor:
es una guía de análisis, no una garantía de posicionamiento. Si el complemento no puede instalarse,
se pueden rellenar los campos manualmente en cada borrador; la app dejará esa revisión pendiente.

## Diagnóstico seguro

| Síntoma | Interpretación | Acción |
| --- | --- | --- |
| «Requiere una revisión humana» | Falta la aceptación o hubo una edición editorial posterior. | Revisa y vuelve a pulsar **Aprobar contenido**. |
| Artículo aceptado vuelve a pedir revisión sin haberse editado | Posible despliegue antiguo o regresión. | Actualiza la aplicación; comprobar en Vercel `f939324` o posterior y abrir incidencia si persiste. |
| Error al crear borrador | Puede afectar a una figura, a la conexión o a la respuesta de WordPress. | Lee el mensaje en la ficha; revisa logs de Vercel y no pulses repetidamente. |
| La imagen no llega | El activo editorial no está disponible en Storage o WordPress rechazó el medio. | Verificar `editorial-images` en Supabase y el medio existente en WordPress. |
| SEO no aparece completado | El puente REST no está activo, el esquema no expone los campos o WordPress no confirmó los valores. | Revisar el complemento y los permisos; completar los campos manualmente si sigue sin funcionar. |

## Configuración técnica

Las variables se configuran sólo en **Vercel / Production**. Sus valores no se escriben en
documentos, commits ni variables públicas:

```text
WORDPRESS_BASE_URL
WORDPRESS_USERNAME
WORDPRESS_APPLICATION_PASSWORD
WORDPRESS_DEFAULT_CATEGORY_ID        # opcional
WORDPRESS_AUTHOR_ID                  # opcional
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
