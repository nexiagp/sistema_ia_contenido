# Reunión con Marketing — automatización del blog a WordPress

**Fecha:** 1 de septiembre de 2026
**Objetivo:** acordar un primer flujo seguro desde Nexia GP Content AI hasta `nexiagp.com`, que reduzca trabajo manual sin quitar a Marketing el control final de marca y publicación.

> **Cierre operativo — 01/09/2026:** el flujo ya está desplegado. Los blogs aprobados crean o
> actualizan borradores de WordPress con sus imágenes, sin publicar. El piloto se comprobó con tres
> borradores reales. Rank Math permanece como revisión manual porque sus campos no están disponibles
> para escritura en la API REST actual. La guía vigente es el [Runbook de WordPress](WORDPRESS_RUNBOOK.md).

## Punto de partida

La aplicación ya genera y conserva, para cada artículo:

- artículo en HTML semántico;
- título, slug, meta título, meta descripción, Open Graph y JSON-LD;
- imágenes, captions y texto alternativo propuesto;
- enlaces internos, CTA y fuentes recuperadas;
- un control de calidad que requiere revisión humana antes de marcarlo como listo o programado.

La web de Nexia expone la API REST estándar de WordPress para artículos ([https://nexiagp.com/wp-json/wp/v2/posts](https://nexiagp.com/wp-json/wp/v2/posts)). La conexión de escritura está activa: un blog con revisión registrada puede enviarse a WordPress como **borrador** y se guarda su trazabilidad para actualizarlo sin duplicarlo.

## Propuesta recomendada: primera fase

```text
Generar en la app → revisión y aprobación en la app → enviar a WordPress como borrador
                                                        ↓
                                             Marketing revisa el resultado allí
                                                        ↓
                                              publica o programa en WordPress
```

La primera fase **no publica automáticamente en la web**. Es la forma más útil de empezar: evita copiar y pegar, sube las imágenes y deja el artículo listo en el WordPress que Marketing ya conoce. Tras validar varios artículos, se puede habilitar la programación automática como segunda fase.

## Qué hará la integración

| Salida de la app | Destino WordPress |
| --- | --- |
| Título y slug | título y URL propuesta del post |
| HTML del artículo | contenido del post |
| Imagen seleccionada | Biblioteca de medios y, si se aprueba, imagen destacada |
| Caption y alt | pie y texto alternativo de cada imagen |
| Extracto / descripción | extracto del post (decisión de Marketing) |
| Categoría, etiquetas y autor | taxonomías y autor acordados |
| Meta título, descripción, canonical, JSON-LD | plugin SEO o campos SEO de la web, según la configuración actual |
| Identificador y URL de WordPress | guardados de vuelta en la app para no duplicar artículos y permitir reintentos seguros |

El estado inicial en WordPress sería `draft`; Marketing conserva la decisión de pasar a `publish` o programar una fecha. La API de WordPress admite esos estados y permite adjuntar contenido, slug, extracto e imagen destacada.

## Decisiones que conviene cerrar en la reunión

1. **Responsable editorial.** Quién aprueba contenido en la app y quién publica/programa en WordPress.
2. **Modo inicial.** Recomendación: crear siempre un borrador de WordPress. ¿Se quiere que en una segunda fase se programe automáticamente después de una aprobación explícita?
3. **Diseño y bloques.** Validar un artículo de prueba en el tema actual: el HTML generado, tablas, CTA, enlaces e imágenes deben verse como espera Marketing. Si usan bloques Gutenberg o una plantilla específica, lo adaptamos a ese formato.
4. **SEO.** Qué plugin usa la web (Yoast, Rank Math, otro o ninguno) y qué campos deben llegar desde la app. La API estándar crea el post, pero los campos propios del plugin suelen necesitar su configuración o un endpoint adicional.
5. **Taxonomía.** Categorías, etiquetas, autor por defecto y reglas para crearlos o reutilizarlos.
6. **Imágenes.** Cuál será la imagen destacada, dimensiones/peso aceptados, si se suben las figuras interiores y si se mantiene su caption/alt propuesto.
7. **URLs y enlaces.** Confirmar la estructura de enlaces de blog y que los enlaces internos generados coinciden con las URLs definitivas de la web.
8. **Correcciones posteriores.** Si Marketing modifica un borrador en WordPress, ¿la app puede actualizarlo otra vez o el WordPress pasa a ser la fuente final? Recomendación: tras el primer envío, actualizar solo con una acción explícita de “sincronizar cambios”.
9. **Errores y trazabilidad.** Mostrar en la app el ID, URL, fecha y resultado de WordPress; no duplicar un artículo si hay un reintento tras un fallo.

## Accesos a pedir

- URL de administración de WordPress y contacto técnico que mantenga la web.
- Un usuario técnico específico de WordPress con el mínimo permiso necesario para crear/editar entradas y subir medios; no usar la cuenta personal de nadie.
- Una **contraseña de aplicación** para ese usuario, guardada solo como secreto del servidor de la app (nunca en el navegador ni en documentos compartidos).
- Confirmación de que el servidor permite peticiones autenticadas a la API REST y de que no hay un firewall o plugin de seguridad que las bloquee.
- Datos de un artículo de prueba: categoría, autor, imagen y publicación en borrador.
- Nombre y configuración del plugin SEO, si existe.

## Criterios de aceptación del piloto

Un piloto queda aprobado si, con un artículo real pero en borrador:

1. se crea un único post en WordPress desde un blog aprobado en la app;
2. título, URL, HTML, enlaces y CTA se muestran correctamente en el tema;
3. se sube y asigna la imagen destacada con su texto alternativo;
4. las categorías, autor y datos SEO quedan donde Marketing los necesita;
5. la app muestra el enlace al borrador de WordPress y permite reintentar sin duplicarlo;
6. Marketing puede editar y publicar el borrador con su proceso habitual.

## Guion breve para abrir la conversación

> La aplicación ya nos entrega un artículo revisable, con SEO, imágenes y fuentes. Lo que proponemos ahora no es publicar a ciegas: es llevar ese trabajo a un borrador de WordPress con un clic, para que Marketing conserve la revisión y publicación final. Cerramos hoy el formato del artículo, el SEO, los permisos y un piloto; con eso podemos validar la conexión con una entrada real antes de automatizar más.

## Siguiente paso tras la reunión

El piloto técnico ya está validado. Marketing debe revisar el aspecto del HTML, las imágenes y los
campos de Rank Math en los borradores antes de programar o publicar manualmente en WordPress. No se
activará publicación automática sin una decisión editorial y técnica explícita.

## Referencias técnicas

- [API REST de posts de WordPress](https://developer.wordpress.org/rest-api/reference/posts/): permite crear y actualizar entradas, incluidas contenido, slug, extracto, imagen destacada, categorías, etiquetas y estados.
- [Autenticación REST de WordPress](https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/): las contraseñas de aplicación permiten autenticar un servicio externo sin usar una contraseña personal.
