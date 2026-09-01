# Operación WordPress — Nexia GP Content AI

**Actualizado:** 1 de septiembre de 2026
**Uso:** equipo editorial y mantenimiento técnico de la conexión con `nexiagp.com`.

## Estado actual

- La aplicación de producción se autentica con Supabase y usa el estado remoto como fuente de verdad.
- WordPress está conectado mediante un usuario técnico y una contraseña de aplicación almacenada
  únicamente como secreto de Production en Vercel.
- La integración crea o actualiza **borradores**; no publica ni programa entradas de WordPress.
- El piloto inicial se verificó con tres artículos aprobados y los tres permanecen en `draft`.
- Rank Math está instalado. Sus campos no están expuestos como metacampos editables por la API REST
  actual, por lo que su revisión final se hace dentro de WordPress.

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
5. En Rank Math, completa o valida metatítulo, metadescripción y keyword principal.
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
| Primera figura | Imagen destacada |
| Caption de figura | Texto alternativo y pie de imagen |
| ID, URL, hash y fecha del borrador | Trazabilidad para actualizar sin duplicar |
| SEO de Rank Math | Sólo si el plugin expone el campo por API; si no, revisión manual |

## Diagnóstico seguro

| Síntoma | Interpretación | Acción |
| --- | --- | --- |
| «Requiere una revisión humana» | Falta la aceptación o hubo una edición editorial posterior. | Revisa y vuelve a pulsar **Aprobar contenido**. |
| Artículo aceptado vuelve a pedir revisión sin haberse editado | Posible despliegue antiguo o regresión. | Actualiza la aplicación; comprobar en Vercel `f939324` o posterior y abrir incidencia si persiste. |
| Error al crear borrador | Puede afectar a una figura, a la conexión o a la respuesta de WordPress. | Lee el mensaje en la ficha; revisa logs de Vercel y no pulses repetidamente. |
| La imagen no llega | El activo editorial no está disponible en Storage o WordPress rechazó el medio. | Verificar `editorial-images` en Supabase y el medio existente en WordPress. |
| SEO no aparece completado | Rank Math no admite esos metacampos a través de REST. | Completar los campos manualmente en el borrador. |

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
