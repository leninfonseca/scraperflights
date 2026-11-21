# Ampliación híbrida inicial

La búsqueda combina páginas públicas y archivos importados.

| Sección | Ubicación | Estado |
|---|---|---|
| API | `src/scraperflights/connectors/api/` | Adaptadores históricos conservados fuera del comando de búsqueda |
| Web HTTP | `src/scraperflights/connectors/web/` | Vueling, Iberia, Air Europa, Kiwi.com, Trabber, Trip.com, Rumbo, Liligo, KAYAK, momondo, Wego, Aeroméxico, Lufthansa, SWISS y Brussels Airlines por HTTP |
| Navegador | `src/scraperflights/connectors/browser/` | Calendario público de Vueling renderizado con Chromium |
| Feeds/archivos | `src/scraperflights/connectors/feeds/` | Importador local JSON y CSV. Se aporta el archivo del proveedor |

El catálogo distribuido contiene 69 fuentes. Consulta las categorías y el estado con `scraperflights sources`. Las marcas candidatas pueden compartir inventario o grupo y requieren comprobar cobertura de la ruta, condiciones de acceso y reputación.

Iberia, Air Europa, Kiwi.com y Trabber se leen desde sus páginas públicas. Iberia y Air Europa se probaron con referencias fechadas de ida y vuelta. Kiwi.com publica una selección dinámica de fechas. Trip.com empareja las dos piernas usando el mismo enlace y toma el precio del paquete una sola vez. Rumbo lee fechas y escalas de las tarjetas públicas. Wego aporta referencias históricas fechadas en EUR. Los mínimos de Trabber, KAYAK, momondo y Liligo se mantienen fuera del mínimo fechado. KAYAK y momondo pueden compartir datos. eDreams y Opodo devolvieron HTTP 403 en la comprobación de acceso y conservan enlaces manuales.

## Ejecutar las nuevas fuentes

```bash
scraperflights search --date 2026-12-10 --both-directions --providers vueling-web
python -m pip install -e '.[browser]'
python -m playwright install chromium
scraperflights search --date 2026-12-10 --providers vueling-browser
scraperflights search --date 2026-12-10 --providers vueling-web --feed data/provider.json
```

Sustituye la fecha por una futura. La búsqueda predeterminada usa las quince fuentes HTTP. Selecciona un solo método de Vueling por búsqueda. Chromium cuenta como una navegación para el presupuesto y puede cargar recursos secundarios. Si la página bloquea el acceso o cambia su estructura, el informe registra el error. Cada modo lee el calendario público. La automatización de formularios de reserva queda pendiente.

`supplemental_prices` recoge referencias del mes (`indicative`) y capturas importadas (`imported`). Estas observaciones se guardan también en el histórico. Para ver la referencia publicada más barata con fechas coincidentes se usa `lowest_dated_reference`. El calendario Vueling solo admite ida, un adulto y sin maletas requeridas. Una búsqueda con otras condiciones registra `unsupported_profile`.

El feed local es un array JSON de filas como esta. `search` debe coincidir exactamente con el perfil de búsqueda. La fecha de observación necesita zona horaria y no puede ser futura. El ejemplo es ficticio.

```json
[
  {
    "search": {"origin":"MAD","destination":"BCN","departure":"2026-12-10","return_date":null,"adults":1,"cabin_bags":0,"checked_bags":0,"direct":true,"currency":"EUR"},
    "reference":"provider-123",
    "seller":"Agencia de ejemplo",
    "segments":[{"leg":0,"origin":"MAD","destination":"BCN","departure":"2026-12-10T10:00:00+01:00","arrival":"2026-12-10T11:15:00+01:00","flight":"IB123"}],
    "amount":"42.50",
    "currency":"EUR",
    "observed_at":"2026-11-07T09:00:00+01:00"
  }
]
```

Para CSV, usa las mismas columnas y serializa `search` y `segments` como JSON dentro de cada celda. `amount` es el importe observado para todo el grupo. La importación conserva la hora original y no revalida el precio ni descarga feeds de terceros.

## Comparar perfiles web

```bash
scraperflights compare --date 2026-12-10 --factor device --providers vueling-web trabber-web
scraperflights compare --date 2026-12-10 --factor locale --rounds 3 --providers vueling-web
scraperflights compare --date 2026-12-10 --factor session --providers vueling-web
```

Sustituye las fechas por fechas futuras. Usa `--origin BCN` para el sentido contrario y `--return-date` en fuentes con referencias de ida y vuelta. La comparación usa un adulto, turista, EUR y sin maletas adicionales.

| Factor | Perfil A | Perfil B |
|---|---|---|
| `device` | Escritorio | Móvil. En HTTP cambia el User-Agent. Con `vueling-browser` también cambian la pantalla y la emulación táctil. |
| `locale` | `es-ES` | `es-MX`. Se conserva la URL y se filtran precios en EUR. |
| `session` | Primera visita | Segunda visita al mismo URL con cookies de la primera. En navegador se reutiliza también el contexto, incluida su caché. |

Cada prueba ejecuta los dos perfiles consecutivamente por proveedor desde el mismo entorno. El orden alterna entre A→B y B→A. Por defecto se hacen dos rondas y se permiten de una a cinco. Cada par empieza sin cookies de rondas previas. La prueba de sesión puede comparar dos visitas equivalentes si la web no devuelve cookies.

El JSON `output/comparison-*.json` registra el perfil, orden, hora, resultados y estado de cada fuente. Compara mínimos de la misma fuente, moneda y alcance (fechado, mensual o de ruta) por separado. `delta_b_minus_a` es B menos A. Si falta un lado, queda sin emparejar. El número de observaciones y el intervalo entre ellas ayudan a interpretar el resultado.

Las diferencias pueden reflejar cambios de inventario, caché o selección de ofertas. La comparación mide mínimos publicados. Las webs actuales suelen carecer de identificadores de tarifa y total de compra. El informe no atribuye causalidad ni certifica una diferencia para el mismo billete. El modo no utiliza cuentas, claves ni proxies de rotación.

## Monterrey

BCN↔MTY y MAD↔MTY están disponibles en consola y visor con escalas por defecto. `--destination` elige el destino y `--direct-only` restringe a directos. Las búsquedas anteriores sin destino conservan BCN↔MAD. El informe registra una ruta sin cobertura como `unsupported_route`. Cada página puede publicar precios de fechas distintas a las solicitadas.

## Integración de aerolíneas para México

`aeromexico-web` reutiliza la extracción de tarifas públicas fechadas y exige EUR, cabina económica y coincidencia de salida y regreso. `lufthansa-web` extrae el mínimo anunciado para la ruta de un producto estructurado y lo clasifica como orientativo de ruta. Ambos conectores admiten las cuatro rutas entre MTY y BCN/MAD. Se consultan por defecto y aparecen en `compare`.

Se probaron las cuatro rutas Aeroméxico y las salidas de BCN/MAD en Lufthansa. BCN→MTY devolvió datos en ambas aerolíneas. Las otras rutas Aeroméxico devolvieron inicialmente HTTP 403. En la consulta posterior, MAD→MTY respondió sin coincidencias. Lufthansa MAD→MTY devolvió inicialmente HTTP 403 y después una página sin precios extraíbles. Los tests comprueban fechas, monedas y la separación del mínimo de ruta.

## Transporte terrestre BCN↔MAD

Se añaden `omio-train-web`, `omio-bus-web`, `blablacar-web` y `trainline-web`. La selección `--modes` y las casillas del visor controlan los medios a consultar. MTY mantiene las consultas de avión.

Las observaciones terrestres incluyen `transport_mode` y `journey_leg`. Omio separa la ida y el regreso, y usa `indicative_leg_reference`. BlaBlaCar y Trainline usan `indicative_route_minimum`. Los importes de un tramo se mantienen fuera del mínimo fechado de vuelos de ida y vuelta. El esquema anterior conserva avión como valor por defecto para informes históricos.


## Robustez del scraping HTML

La lectura compartida vive en `connectors/web/html.py`. Tolera el orden y las comillas de los atributos HTML, JSON-LD con arrays, `@graph`, tipos múltiples y referencias locales `@id` en campos directos. Lee objetos JSON incrustados de Air Europa/Aeroméxico y Rumbo sin depender de la primera propiedad, sin ejecutar JavaScript y sin llamar endpoints de inventario.

Los importes aceptan `1.234,56`, `1,234.56` y espacios de miles. Se descartan cantidades inválidas, negativas o no finitas; los números JSON no se reinterpretan como texto localizado. Se retiran duplicados por precio, segmentos y enlace. Se mantienen los filtros de ruta, fechas, moneda, clase y alcance. Los lectores de texto omiten `script`, `style`, `template`, `noscript` y elementos marcados como ocultos; no calculan CSS externo, por lo que no equivalen a una lectura visual completa.

La descarga HTTP valida tipo HTML, decodifica el charset declarado y admite gzip con límite de 5 MB descomprimidos. Las páginas de bloqueo y errores HTTP se registran sin intentar evitarlos. Cada fuente incorpora diagnósticos `http` (estado, bytes, charset, duración y caché) y, cuando procede, `extraction` (filas e importes inválidos). Se ven en los detalles de la fuente del visor y en JSON. Un cambio de plantilla sin datos reconocibles sigue apareciendo como error de extracción; cero coincidencias reconocidas no prueba que no existan vuelos.

La caché solo dura una ejecución y admite hasta ocho páginas; evita descargar dos veces una misma URL, por ejemplo para tren y autobús de Omio. Las comparaciones con perfil desactivan esa caché para no reutilizar el HTML entre visitas experimentales. La caché cuenta navegaciones HTTP ahorradas; no agrega nuevas llamadas API.

### SWISS y Brussels Airlines

Se añadieron `swiss-web` y `brussels-web` a las búsquedas HTTP y al laboratorio de dispositivos. Utilizan las páginas públicas España–Monterrey con JSON-LD `Product/Offer`, comprobando marca, sentido de ruta y EUR. Pueden ofrecer vuelos de socios y compartir inventario con Lufthansa. Sus precios carecen de fechas y permanecen como `indicative_route_minimum`, fuera de `lowest_dated_reference` y `winner`. Si una página de salida desde México publica MXN, el precio se excluye; no se convierte ni se atribuye una tarifa en EUR.

Comprobación del 21 de noviembre de 2026: HTTP 200 y extracción de una referencia de ruta en las páginas Barcelona–Monterrey de [SWISS](https://www.swiss.com/lhg/es/es/o-d/cy-cy/barcelona-monterrey) y [Brussels Airlines](https://www.brusselsairlines.com/lhg/es/es/o-d/cy-cy/barcelona-monterrey). También se reconoció la plantilla de Iberia en esa ruta. Esto no valida inventario ni todas las rutas inversas o fechas futuras.

```cmd
py -m scraperflights.cli search --origin BCN --destination MTY --date 2027-01-15 --providers swiss-web brussels-web
```
