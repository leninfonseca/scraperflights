# Ampliación híbrida inicial

La búsqueda combina inventario por API con referencias del calendario público y archivos importados.

| Sección | Ubicación | Estado |
|---|---|---|
| API | `src/scraperflights/connectors/api/` | Amadeus y Skyscanner trasladados, conservando imports anteriores |
| Web HTTP | `src/scraperflights/connectors/web/` | Calendario público de Vueling por HTTP |
| Navegador | `src/scraperflights/connectors/browser/` | Calendario público de Vueling renderizado con Chromium |
| Feeds/archivos | `src/scraperflights/connectors/feeds/` | Importador local JSON y CSV. Se aporta el archivo del proveedor |
| Contrato común | `src/scraperflights/connectors/base.py` | ready, search y refresh; compatible con los adaptadores API |

El catálogo distribuido con el paquete (`sources.json`) contiene 18 fuentes:

- Aerolíneas: Iberia, Vueling y Air Europa.
- Agencias: Expedia, Booking.com Flights, Trip.com, lastminute.com, eDreams, Opodo, Rumbo, Atrápalo, Logitravel y Viajes El Corte Inglés.
- Metabuscadores: Skyscanner, Google Flights, KAYAK y momondo.
- Distribución: Amadeus.

Atrápalo, Logitravel y Viajes El Corte Inglés son las tres nuevas agencias de esta ampliación. Se verificó la existencia de sus buscadores el 2026-11-05:

- https://www.atrapalo.com/vuelos/
- https://www.logitravel.com/vuelos/
- https://www.viajeselcorteingles.es/vuelos/

No se ha validado aún su extracción, reputación, disponibilidad para la ruta ni permiso de automatización. Las otras marcas proceden del diseño anterior y siguen pendientes de revisión individual. Los métodos del catálogo son opciones por evaluar; `implemented_methods` identifica exclusivamente lo programado. `implemented` tampoco significa credenciales configuradas ni prueba live aprobada.

## Ejecutar las nuevas fuentes

```bash
scraperflights search --date 2026-12-10 --both-directions --providers vueling-web
python -m pip install -e '.[browser]'
python -m playwright install chromium
scraperflights search --date 2026-12-10 --providers vueling-browser
scraperflights search --date 2026-12-10 --providers vueling-web --feed data/provider.json
```

Sustituye la fecha por una futura. La búsqueda predeterminada usa las dos APIs y Vueling por HTTP. Selecciona un solo método de Vueling por búsqueda. Chromium cuenta como una navegación para el presupuesto y puede cargar recursos secundarios. Si la página bloquea el acceso o cambia su estructura, el informe registra el error. Cada modo lee el calendario público. La automatización de formularios de reserva queda pendiente.

`supplemental_prices` recoge referencias del mes (`indicative`) y capturas importadas (`imported`). Estas observaciones se guardan también en el histórico. Para comparar vuelos con fecha exacta se usa `lowest_observed` con los resultados de API. El calendario solo admite ida, un adulto y sin maletas requeridas. Una búsqueda con otras condiciones registra `unsupported_profile`.

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
