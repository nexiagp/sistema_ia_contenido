# Revisión de blogs, acceso y redes — 26/10/2026

Este documento recoge la revisión visual y la comprobación del despliegue del 26/10/2026.

## Estado observado

- La aplicación pública `https://nexiagp-content.vercel.app` ya pide la contraseña del equipo. Se comprobó el inicio de sesión, la carga del estado editorial y el rechazo de una consulta sin sesión (`401`).
- `https://nexiagp.com/blog/` contiene cinco entradas publicadas antiguas. Los tres artículos generados por la aplicación continúan como borradores de WordPress.
- Los tres artículos se devolvieron a «En revisión» en la aplicación tras detectar los problemas siguientes. Se retiró la aprobación previa; los tres borradores de WordPress siguen en `draft` y no se modificaron.
- La vista desplegada muestra «3 en revisión» y permite filtrarlos. Los enlaces relativos de la vista previa y de las fichas de enlaces internos se resuelven ahora hacia `nexiagp.com`; el HTML que recibe WordPress conserva rutas relativas válidas en ese dominio.
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
| X | https://x.com/NexiaGP | Aplicación de desarrollador de Nexia creada (ID `33578235`), permiso «Leer y escribir» sin mensajes directos y autorización OAuth2 del usuario con `tweet.write` | La cuenta muestra 0 créditos de API. Falta integrar y persistir de forma segura la renovación del token, probar la publicación con lectura de vuelta y financiar el uso de API si procede. |
| LinkedIn | https://www.linkedin.com/company/nexia-growth-partner/ | Aplicación `NexiaGPContent` creada (ID `266660571`) y asociación con la página de empresa `106088372` verificada el 26/10 | LinkedIn exige verificar un correo del dominio de la empresa para tramitar Community Management API. El equipo no tiene acceso ahora; la solicitud no está presentada. Después harán falta aprobación de LinkedIn, permiso de publicación y autorización del administrador. |
| Instagram | Sin cuenta identificada con certeza | Pendiente de confirmar el perfil oficial | Cuenta profesional y permisos de publicación de Instagram; comprobar el perfil antes de pedir autorización. |

Ninguna cuenta está conectada todavía al servidor para publicar. `SOCIAL_WEBHOOK_URL` sigue sin configurarse. La respuesta HTTP de un webhook genérico no verifica por sí sola qué red publicó ni el ID de la publicación; la conexión final debe guardar y comprobar el resultado por canal. Las credenciales OAuth2 de X obtenidas para preparar la conexión están sólo en `secrets/` local, excluido de Git; no se han puesto en Vercel ni se han usado para publicar. El token de acceso mostrado por X caduca en dos horas y el de renovación en seis meses. No se ha comprado crédito ni se ha enviado ningún post.

El cron actual del proyecto se ejecuta una vez al día (`05:00 UTC`) para crear borradores. El plan Hobby de Vercel limita sus cron a una ejecución diaria y admite hasta 59 minutos de variación dentro de la hora; por tanto, ese cron no sirve para publicar a la hora exacta elegida en el calendario. Hay que añadir un programador con la precisión acordada antes de activar envíos automáticos. [Límites oficiales de Vercel Cron](https://vercel.com/docs/cron-jobs/usage-and-pricing).

Referencias oficiales: [X: creación de posts](https://github.com/xdevplatform/samples/blob/main/python/posts/create_post.py), [LinkedIn: revisión de Community Management](https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-06), [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-06), [Instagram API con inicio de sesión de Instagram](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login).

## Pasos para activar con control

1. En la app desplegada, revisar de nuevo los tres artículos y después actualizar los borradores de WordPress. Sustituir las dos portadas indicadas, completar Rank Math y corregir las etiquetas genéricas de la plantilla. Mantenerlos en borrador hasta revisión final.
2. Para X, decidir el crédito de API, completar una integración con renovación persistente del token y comprobar una publicación controlada con ID remoto y lectura de vuelta. No usar el token de acceso de dos horas como secreto permanente.
3. Para LinkedIn, recuperar acceso a un correo `@nexiagp.com`, superar la verificación de empresa y presentar la solicitud de Community Management. Después de la aprobación, conectar la autorización del administrador y probar el resultado.
4. Confirmar la URL de Instagram. Registrar o seleccionar la aplicación de Meta y verificar un envío de prueba con ID remoto y lectura de vuelta. Añadir un programador de la precisión acordada antes de activar el calendario de publicación real.

No se han publicado posts, entradas ni imágenes durante esta revisión.
