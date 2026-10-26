# Revisión de blogs, acceso y redes — 26/10/2026

Este documento recoge la revisión visual y la comprobación del despliegue del 26/10/2026.

## Estado observado

- La aplicación pública `https://nexiagp-content.vercel.app` ya pide la contraseña del equipo. Se comprobó el inicio de sesión, la carga del estado editorial y el rechazo de una consulta sin sesión (`401`).
- `https://nexiagp.com/blog/` contiene cinco entradas publicadas antiguas. Los tres artículos generados por la aplicación continúan como borradores de WordPress.
- Las vistas previas de los tres borradores repiten la imagen destacada como primera imagen del cuerpo. En los artículos 7415 y 7411, el recurso propuesto muestra «descargar» sin enlace. El 7408 muestra «Recurso en preparación». La plantilla añade etiquetas ajenas al negocio («Financial», «Advisor», «Wealth»).
- El borrador 7411 usa como portada un mapa/diagrama generado con datos visuales que no deben tratarse como hechos. Hay que sustituir esa imagen antes de publicar. La portada del 7415 representa logística portuaria aunque el artículo trata de prescripción técnica hotelera; conviene elegir una escena más específica.
- En el 7408 hay una construcción gramatical que pide corrección manual («una trabajo con fabricantes»), junto con una revisión general de los enlaces y de las tablas en móvil.
- Las puntuaciones visibles de Rank Math fueron 24/100, 23/100 y 25/100 respectivamente. Rank Math no expone estos metacampos para su actualización REST en la instalación actual; la revisión final sigue en WordPress.

### Vistas previas privadas de WordPress

| Borrador | ID | Vista previa |
| --- | ---: | --- |
| Prescripción técnica en el hotelero canario | 7415 | https://nexiagp.com/?p=7415&preview=true&_thumbnail_id=7412 |
| Logística insular para fabricantes B2B | 7411 | https://nexiagp.com/?p=7411&preview=true&_thumbnail_id=7409 |
| Compraventa y suministro industrial | 7408 | https://nexiagp.com/?p=7408&preview=true&_thumbnail_id=7405 |

Estas vistas requieren una sesión administradora de WordPress. Ninguna de las tres entradas está publicada.

## Cambios desplegados

- Acceso de equipo mediante contraseña robusta, sin correo. Se guarda su hash y una clave de sesión en secretos del servidor; el navegador recibe una cookie privada de ocho horas. La pantalla y el acceso se comprobaron en producción.
- Secretos generados una sola vez en `secrets/team-password.txt` y `secrets/team-access-env.txt`. Ambos archivos están ignorados por Git; el primero es para entregar la contraseña al equipo. Las variables privadas necesarias ya están guardadas en Vercel Production. No copiar sus valores a documentación ni al repositorio.
- La exportación futura a WordPress omite la figura que ya se usa como imagen destacada y retira los bloques de recurso sin enlace real. Los tres borradores existentes conservan su contenido hasta que se actualicen expresamente desde la aplicación o WordPress.
- Los posts sociales requieren una aprobación editorial registrada antes de aceptar una fecha futura. Una edición del texto tras programarlos retira la aprobación y la fecha. El envío, si se habilita un conector, queda bloqueado hasta la fecha programada.
- La generación añade una adaptación específica de Instagram y la muestra junto a LinkedIn, X y Facebook; es sólo un borrador de texto. Publicar en Instagram exigirá una imagen o vídeo aprobado y una cuenta profesional autorizada.
- El modo de publicación automática por mera generación está desactivado. El calendario editorial no constituye por sí solo una conexión con las redes.

## Cuentas sociales verificadas y conexión pendiente

| Canal | Cuenta correcta | Comprobación | Falta para publicar desde la aplicación |
| --- | --- | --- | --- |
| X | https://x.com/NexiaGP | Sesión abierta como `@NexiaGP`; perfil con cero posts al revisarlo | Aplicación de desarrollador con OAuth de usuario y permiso `tweet.write`; el bearer actual sólo sirve para lectura. |
| LinkedIn | https://www.linkedin.com/company/nexia-growth-partner/ | La sesión muestra «Ver como administrador» para la página de empresa ID `106088372` | Aplicación autorizada para Community Management y permiso `w_organization_social`, con consentimiento del administrador. |
| Instagram | Sin cuenta identificada con certeza | Pendiente de confirmar el perfil oficial | Cuenta profesional y permisos de publicación de Instagram; comprobar el perfil antes de pedir autorización. |

Ninguna cuenta está conectada todavía al servidor para publicar. `SOCIAL_WEBHOOK_URL` sigue sin configurarse. La respuesta HTTP de un webhook genérico no verifica por sí sola qué red publicó ni el ID de la publicación; la conexión final debe guardar y comprobar el resultado por canal. En X se comprobó que la cuenta todavía debe completar el alta del programa de desarrolladores. En LinkedIn se comprobó que no hay ninguna aplicación de desarrollador creada. Ambos formularios requieren que el titular acepte personalmente sus acuerdos legales.

El cron actual del proyecto se ejecuta una vez al día (`05:00 UTC`) para crear borradores. El plan Hobby de Vercel limita sus cron a una ejecución diaria y admite hasta 59 minutos de variación dentro de la hora; por tanto, ese cron no sirve para publicar a la hora exacta elegida en el calendario. Hay que añadir un programador con la precisión acordada antes de activar envíos automáticos. [Límites oficiales de Vercel Cron](https://vercel.com/docs/cron-jobs/usage-and-pricing).

Referencias oficiales: [X: creación de posts](https://github.com/xdevplatform/samples/blob/main/python/posts/create_post.py), [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-06), [Instagram API con inicio de sesión de Instagram](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login).

## Pasos para activar con control

1. En la app desplegada, revisar de nuevo los tres artículos y después actualizar los borradores de WordPress. Sustituir las dos portadas indicadas, completar Rank Math y corregir las etiquetas genéricas de la plantilla. Mantenerlos en borrador hasta revisión final.
2. El titular de las cuentas debe revisar y aceptar personalmente los acuerdos de desarrollador de X y LinkedIn; los formularios de alta están preparados en Chrome. Después se podrán solicitar los permisos de publicación y comprobar los resultados por canal.
3. Confirmar la URL de Instagram. Registrar o seleccionar la aplicación de Meta y verificar un envío de prueba con ID remoto y lectura de vuelta. No activar el calendario de publicación real hasta disponer de esa comprobación.

No se han publicado posts, entradas ni imágenes durante esta revisión.
