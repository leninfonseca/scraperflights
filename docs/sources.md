# Ampliación híbrida inicial

Esta entrega organiza los métodos y el catálogo. No añade búsquedas web activas.

| Sección | Ubicación | Estado |
|---|---|---|
| API | `src/scraperflights/connectors/api/` | Amadeus y Skyscanner trasladados, conservando imports anteriores |
| Web HTTP | `src/scraperflights/connectors/web/` | Espacio para HTML y JSON incrustado; sin parser activo |
| Navegador | `src/scraperflights/connectors/browser/` | Espacio para formularios, JavaScript y respuestas de red; sin automatización activa |
| Feeds/archivos | `src/scraperflights/connectors/feeds/` | Reservado; ninguna fuente identificada todavía |
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

## Próxima ampliación pequeña

1. Inspeccionar Iberia y Vueling: HTML, datos incrustados y necesidad de navegador.
2. Inspeccionar Atrápalo y Logitravel como primeras agencias candidatas.
3. Implementar y probar cada parser con una búsqueda fechada antes de activarlo.

Los adaptadores devolverán `Offer` y el comparador conservará procedencia, precio y limitaciones. La misma fuente obtenida por web y API no cuenta como dos fuentes independientes. Ninguna agencia se añade automáticamente a vendedores aprobados: `config/sellers.json` conserva su función separada de evaluación de reputación.
