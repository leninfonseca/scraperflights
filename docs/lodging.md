# Alojamiento conectado a los vuelos

En el visor abre **Alojamiento para las fechas de tus vuelos**. Con la sincronización activada, el destino del vuelo se usa como ciudad, la salida como entrada y el regreso como salida del alojamiento. Puedes desactivar la sincronización o editar cualquier fecha para ajustarla a la llegada real. La búsqueda de alojamiento tiene su propio botón; no se lanza otra búsqueda de vuelos.

Para vuelos nocturnos o con llegada al día siguiente, corrige la entrada. No se deduce la llegada de un mínimo de ruta sin itinerario. Si el vuelo es solo de ida, debes completar una salida: no se inventa una duración. La estancia admite hasta 90 noches, 1–9 adultos y 1–9 habitaciones, con al menos un adulto por habitación. No se modelan niños, edades ni reparto de adultos entre habitaciones: hay que confirmar esas condiciones en la web.

## Cobertura real

| Método | Webs | Qué se extrae |
|---|---|---|
| HTML automático | Booking.com | Tarjetas identificadas y enlaces de hoteles publicados en la página de ciudad; precios solo si están dentro de la tarjeta |
| HTML automático | Trip.com | Hoteles JSON-LD y tarjetas HTML con referencias por noche y reseñas |
| HTML automático | KAYAK | Hoteles JSON-LD, `priceRange` orientativo y reseñas con escala explícita |
| HTML automático | Expedia, Hoteles.com | Hoteles JSON-LD/tarjetas reconocidas y enlaces de alojamientos del contenido público; pueden devolver solo descubrimiento sin precio |
| Directorio manual | 32 webs y cadenas | Enlaces adicionales, sin extracción automática ni fechas preseleccionadas |

Las ciudades iniciales son Barcelona, Madrid y Monterrey. Los parámetros de fechas, adultos y habitaciones se envían a las cinco fuentes HTTP. Una web puede ignorarlos, devolver una página editorial, otra moneda o requerir JavaScript para inventario. Por eso **fechas en URL no equivalen a precio para la estancia**. No se usa ninguna API de inventario, se inicia sesión ni se eluden verificaciones.

El directorio incluye Agoda, Airbnb, Vrbo, Hostelworld, Trivago, momondo, Google Hotels, Skyscanner Hoteles, Despegar, Destinia, Central de Reservas, Atrápalo, Logitravel, Rumbo, lastminute.com, eDreams, Priceline, Orbitz, Travelocity, HotelsCombined, HRS, Traveloka y cadenas Marriott, Hilton, IHG, Accor, NH, Meliá, Barceló, Fiesta Americana, Best Western y Wyndham. Es un directorio de marcas conocidas; no se certifica su reputación ni que todas cubran cada ciudad. No promete cobertura de todo el mercado. Varias marcas pueden compartir inventario.

## Precios, reseñas y límites

Cada observación conserva nombre, proveedor, enlace, dirección cuando se publica, importe, moneda declarada, unidad, fechas explícitas de la tarifa, reseñas, método de extracción y texto del precio. El visor muestra filtros de nombre/proveedor, puntuación mínima y solo resultados con precio. Las reseñas se normalizan a diez únicamente cuando la web declara su escala. Las estrellas no se convierten en reseñas.

- `price_basis=night`: referencia por noche; no se multiplica automáticamente por las noches solicitadas.
- `price_basis=stay`: precio de estancia declarado en el objeto de la oferta. No es un total final verificado.
- `price_basis=unknown`: la página no aclara la unidad.
- `scope=undated_reference`: no se han confirmado fechas y ocupación de la oferta, aunque se hayan enviado en la petición.
- `scope=dated_stay_reference`: el objeto de la oferta declara entrada/salida y adultos/habitaciones coincidentes. Es una referencia sin disponibilidad ni impuestos finales verificados.

`lowest_comparable_reference` exige fechas y ocupación explícitas coincidentes, moneda EUR y unidad estancia. Los lectores genéricos solo aceptan los campos explícitos `checkinDate`, `checkoutDate`, `adults`, `rooms` y `priceBasis` de la oferta; no adivinan su significado a partir de precios o formularios. En las páginas comprobadas no se obtuvo ningún total comparable de estancia: se muestran referencias generales o alojamientos sin precio. No hay conversión de divisas ni un ganador de compra. Comprueba ubicación, cancelación, comidas, impuestos, tasas, limpieza, fianza y disponibilidad en la web de reserva.

## Salida e histórico

Los archivos `output/lodging-<id>.json` y `.csv` se guardan con un identificador único, sin sobrescribir búsquedas. El JSON se abre en el mismo visor e incluye los estados HTTP, fechas solicitadas, observaciones y directorio. El CSV distingue `requested_checkin`/`requested_checkout` de las fechas efectivamente publicadas; si la tarifa no especifica fechas, esas celdas quedan vacías.

El histórico de vuelos ignora expresamente los JSON de alojamiento para no mezclar noches/habitaciones con billetes. No se escribe alojamiento en SQLite de vuelos. Los JSON/CSV de alojamiento son el histórico de esta sección.

Desde CMD:

```cmd
py -m scraperflights.cli lodging --destination MTY --date 2027-01-15 --return-date 2027-01-20
py -m scraperflights.cli lodging --destination BCN --date 2027-01-15 --checkout 2027-01-18 --providers booking tripcom
py -m scraperflights.cli lodging --destination MTY --date 2027-01-15 --return-date 2027-01-20 --checkin 2027-01-16 --adults 2 --rooms 1
```

`--checkin` y `--checkout` sobrescriben las fechas por defecto. `--budget` limita consultas HTTP (1–10; cinco por defecto). Las fuentes se consultan secuencialmente con tiempo máximo por petición y guardan errores sin cancelar las restantes.

## Comprobación

El 24 de noviembre de 2026 se descargaron con HTTP 200 las páginas de Monterrey de las cinco fuentes con parámetros del 15 al 20 de enero de 2027. Se reconocieron alojamientos en todas; Trip.com y KAYAK publicaron referencias generales de precio. Booking, Expedia y Hoteles.com aportaron descubrimiento sin precio con los lectores actuales. No se confirmó disponibilidad para esas fechas. No se han comprobado todas las combinaciones de ciudad, fechas u ocupación. Las pruebas de regresión usan HTML sintético y separan moneda, unidad, fechas y ocupación.
