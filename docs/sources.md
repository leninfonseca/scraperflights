# Ampliación híbrida inicial

La búsqueda combina páginas públicas y archivos importados.

| Sección | Ubicación | Estado |
|---|---|---|
| API | `src/scraperflights/connectors/api/` | Adaptadores históricos conservados fuera del comando de búsqueda |
| Web HTTP | `src/scraperflights/connectors/web/` | Vueling, Iberia, Air Europa, Kiwi.com y Trabber por HTTP |
| Navegador | `src/scraperflights/connectors/browser/` | Calendario público de Vueling renderizado con Chromium |
| Feeds/archivos | `src/scraperflights/connectors/feeds/` | Importador local JSON y CSV. Se aporta el archivo del proveedor |
| Contrato común | `src/scraperflights/connectors/base.py` | ready, search y refresh; compatible con los adaptadores API |

El catálogo distribuido contiene 42 fuentes. Consulta las categorías y el estado con `scraperflights sources`. Las marcas candidatas pueden compartir inventario o grupo y requieren comprobar cobertura de la ruta, condiciones de acceso y reputación.

Iberia, Air Europa, Kiwi.com y Trabber se leen desde sus páginas públicas. Iberia y Air Europa se probaron con referencias fechadas de ida y vuelta. Kiwi.com publica una selección dinámica de fechas. El precio mínimo de Trabber es de ruta y se mantiene fuera del mínimo fechado.

## Ejecutar las nuevas fuentes

```bash
scraperflights search --date 2026-12-10 --both-directions --providers vueling-web
python -m pip install -e '.[browser]'
python -m playwright install chromium
scraperflights search --date 2026-12-10 --providers vueling-browser
scraperflights search --date 2026-12-10 --providers vueling-web --feed data/provider.json
```

Sustituye la fecha por una futura. La búsqueda predeterminada usa las cinco fuentes HTTP. Selecciona un solo método de Vueling por búsqueda. Chromium cuenta como una navegación para el presupuesto y puede cargar recursos secundarios. Si la página bloquea el acceso o cambia su estructura, el informe registra el error. Cada modo lee el calendario público. La automatización de formularios de reserva queda pendiente.

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
