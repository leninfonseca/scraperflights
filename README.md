# scraperflights

Buscador web de referencias de precio para **Madrid (MAD) ↔ Barcelona (BCN)** con histórico SQLite y exportación JSON/CSV. El comando de búsqueda funciona sin claves ni llamadas a APIs de vuelos.

## Uso

```bash
python -m pip install -e .
scraperflights sources --category agency
scraperflights sources --method web --status implemented
scraperflights search --date 2026-12-10 --both-directions
scraperflights search --date 2026-12-22 --return-date 2027-01-06 --providers iberia-web aireuropa-web
scraperflights history --limit 10
```

Sustituye las fechas por fechas futuras. `--flex-days` amplía la búsqueda alrededor de la salida, con la vuelta fija. `--budget` limita las peticiones principales de cada búsqueda. Los informes se guardan en `output/` y el histórico en `data/flights.sqlite`.

| Fuente | Datos disponibles |
|---|---|
| Vueling | Mínimo mensual de ida publicado en su calendario. HTML por defecto, Chromium opcional. |
| Iberia | Tarjetas de precios anunciados que coinciden con las fechas y el trayecto solicitados. |
| Air Europa | Tarifas de turista fechadas incluidas en los datos públicos de la página. |
| Kiwi.com | Precios de ida fechados en los datos estructurados de la página. Se omiten resultados con escalas contradictorias cuando se piden directos. |
| Trabber | Precio mínimo anunciado para la ruta. La fecha y el tipo de viaje de ese mínimo quedan sin confirmar. |
| Feed local | Observaciones del perfil solicitado importadas de JSON o CSV. |

Las fuentes HTML publican una selección de precios para un adulto en EUR. Si se piden más pasajeros o maletas, se indica que el perfil no está soportado. Un precio fechado puede corresponder a una captura previa del vendedor. Si falta información de escalas, el informe lo indica.

`lowest_dated_reference` muestra la referencia fechada más barata de las extraídas. `supplemental_prices` recoge también mínimos mensuales, mínimos de ruta e importaciones. Si una fuente responde sin coincidencias, el informe puede mostrar cero referencias. Eso indica qué publicó la página en esa captura. `winner` queda vacío mientras falten disponibilidad, equipaje o costes de compra confirmados.

El catálogo tiene **42 fuentes**, incluidas 26 agencias, 12 metabuscadores, 3 aerolíneas y Amadeus como distribuidor histórico. Las candidatas sirven para ampliar cobertura y consultar sus webs. Las integraciones activas y sus requisitos están en [docs/sources.md](docs/sources.md). Los adaptadores API históricos se conservan en el código fuera de la búsqueda de consola.

### Registro de vendedores

`config/sellers.json` comienza vacío porque aún no se han verificado reseñas actuales. Usa el nombre exacto del vendedor identificado en la fuente. Una aprobación requiere revisión humana y evidencia; no permite omitir otros bloqueos del precio.

```json
{
  "Nombre exacto del vendedor": {
    "status": "approved",
    "reviewed_at": "2026-11-05",
    "evidence_url": "https://plataforma-de-resenas.example/ficha-verificada",
    "rating": 4.2,
    "review_count": 1500,
    "notes": "Ejemplo de estructura: sustituir por evidencia real, no copiar como aprobación"
  }
}
```

No se incluye ninguna aprobación de ejemplo en el fichero real. Las reseñas no se scrapean automáticamente. La política numérica del diseño es una guía de revisión humana; la ejecución comprueba estado, fecha y presencia de evidencia.

### Estados y códigos de salida

- `indicative` indica una página interpretada, aunque no publique coincidencias.
- `imported` indica un archivo leído. `unsupported_profile` indica una combinación que la fuente no puede evaluar.
- `error` indica bloqueo, fallo de red, presupuesto agotado o cambio de estructura.
- Código 0 si se interpretó alguna fuente. Código 2 si ninguna respondió de forma utilizable o los argumentos son inválidos.

Las secciones siguientes conservan el diseño objetivo y las variables de precios a considerar.

## 1. Alcance y decisiones iniciales

- Rutas independientes MAD → BCN y BCN → MAD. Solo aeropuertos exactos; Girona y Reus requieren activación explícita.
- Ida e ida/vuelta. Para ida/vuelta comparar billete conjunto y dos billetes separados, conservando sus diferencias de condiciones y responsabilidad.
- Directos por defecto; escalas en una clasificación separada y opcional.
- Perfil inicial configurable: 1 adulto, turista, mercado España, EUR, idioma es-ES, sin cuenta ni membresía. Equipaje requerido siempre explícito.
- Fechas concretas, intervalos y flexibilidad ±N días. Límites de combinaciones, presupuesto de consultas y horizonte configurable por fuente.
- Ninguna compra, reserva, pago ni contratación de membresía automática.
- Python como lenguaje previsto; adaptadores independientes para API, HTTP permitido o navegador cuando sea necesario y permitido. SQLite inicial, exportación JSON/CSV y posible PostgreSQL posterior.

## 2. Fuentes y cobertura

No se presupone que una marca opere la ruta, tenga disponibilidad en las fechas elegidas o permita automatización. Cada conector necesita validación de acceso, condiciones, cobertura, precio final y reputación antes de activarse.

| Categoría | Candidatas | Uso y limitación |
|---|---|---|
| Venta directa | Iberia, Vueling, Air Europa | Comprobar ruta y fechas en cada ejecución; diferenciar compañía comercializadora y operadora. No asumir cobertura exhaustiva. |
| Metabuscadores | Skyscanner, KAYAK, Google Flights, momondo | Descubrimiento y contraste; el vendedor final puede ser una agencia. No contar el metabuscador como vendedor. |
| Agencias | Expedia, Booking.com Flights, Trip.com, lastminute.com, eDreams, Opodo, Rumbo | Lista para evaluar, no lista de agencias ya aprobadas ni garantía de buena valoración. Registrar entidad que cobra/emite y quién atiende incidencias. |
| API de distribución | Skyscanner Travel API, Amadeus | Alternativas sujetas a aprobación, credenciales, contrato, costes y cobertura efectiva; no sustituyen automáticamente todas las fuentes. |

Evitar contar dos veces inventario compartido, marcas del mismo grupo o el mismo vendedor descubierto en varios metabuscadores. Conservar procedencia completa para poder auditarlo.

### Registro de conectores

Cada fuente tendrá: identificador, dominio oficial, tipo, entidad/grupo, mercados, capacidades, fechas de revisión, mecanismo de acceso autorizado, requisitos de credenciales, cuotas, coste, concurrencia, timeout, TTL, soporte de equipaje, revalidación, paginación, ordenación, estado y motivo de desactivación.

Estados: `candidate`, `access_pending`, `enabled`, `degraded`, `blocked`, `disabled`. El README no debe presentar candidatos como conectores implementados.

### Agencias reconocidas y bien valoradas

La popularidad no prueba la calidad del servicio. Mantener una ficha por vendedor con:

- Identidad comercial/legal, país, dominio y relación entre marca, cobrador y emisor.
- Plataforma y enlace de reseñas, puntuación, escala, número de opiniones, fecha de consulta y proporción de reseñas recientes si está disponible.
- Patrones recientes sobre reembolsos, cargos inesperados, cambios, asistencia y suscripciones.
- Condiciones públicas, canales de atención, horarios, idioma y costes de gestión.
- Evidencia y fecha de revisión humana; separar valoración de la aerolínea y de la agencia.

Política inicial propuesta, configurable: al menos 4/5 con 1.000 opiniones en una fuente identificada, revisión de reseñas recientes y contraste adicional de identidad/condiciones. Es un filtro de entrada, no una certificación. Las escalas distintas no se convierten sin documentarlo. No promediar plataformas arbitrariamente.

Si no hay evidencia suficiente: `reputation_unknown`, fuera del ranking de vendedores aprobados y visible en un apartado pendiente. Una incidencia aislada no provoca exclusión automática; los patrones materiales requieren revisión. Guardar los motivos de aprobación, advertencia o exclusión. No inventar puntuaciones.

## 3. Variables de búsqueda

| Grupo | Variables |
|---|---|
| Itinerario | Origen/destino IATA, sentido, fechas, ida/vuelta, flexibilidad, estancia mínima/máxima, salida/llegada por franja, llegada al día siguiente |
| Viajeros | Adultos, niños y edades, bebés con/sin asiento, tamaño del grupo, accesibilidad y necesidades especiales si influyen en elegibilidad o coste |
| Vuelo | Directo/escalas, duración, tiempo de conexión, cambio de aeropuerto, billetes separados, conexión protegida, terminal, número de vuelo, operador y comercializador |
| Producto | Cabina por tramo, familia tarifaria, clase de reserva si disponible, equipaje, asiento, embarque, check-in, flexibilidad, reembolso y no-show |
| Contexto | Mercado/país de venta, moneda, idioma, zona horaria, canal web/app/API, sesión, login, membresía y promociones |
| Restricciones | Presupuesto total, equipaje mínimo, horarios, vendedores aprobados, máximas escalas/duración y tolerancia de antigüedad |
| Operación | Fuentes habilitadas, límites de consultas, frecuencia, paginación, tiempo máximo de ejecución, reintentos y presupuesto API |

No activar automáticamente descuentos de residente, familia numerosa, estudiante, corporativo, fidelización u otros si el viajero no ha confirmado elegibilidad.

## 4. Coste comparable

`total_comparable = precio_del_grupo_con_impuestos + extras_requeridos_no_incluidos + cargos_obligatorios_no_incluidos + costes_de_pago_aplicables`

Cada componente declara si está incluido para evitar doble contabilización. Utilizar Decimal y moneda ISO; guardar precisión y redondeo. Conservar importe original y, si hay conversión, tipo de cambio, proveedor, instante y coste de conversión.

- Precio por persona frente a total de todos los viajeros; nunca comparar uno con otro.
- Artículo personal, maleta de cabina y facturada por viajero y tramo: piezas, peso, medidas e inclusión.
- Asiento solo si se exige; no sumar selección opcional como obligatoria.
- Check-in online/aeropuerto, embarque, gestión/emisión, pago, impuestos y recargos aplicables.
- Tarifas condicionadas a tarjeta, app, cupón, membresía o suscripción en clasificación separada. Mostrar coste de alta/renovación, recurrencia y elegibilidad; no asumir que el usuario ya es miembro.
- Servicios opcionales, seguros, compensación de CO₂ y paquetes excluidos salvo petición explícita.
- Si falta un cargo necesario, el total es desconocido o parcial: no sustituir por cero ni declarar esa oferta ganadora.
- Si un extra no se puede comprar, marcar oferta incompatible con el perfil.
- Para grupos, no multiplicar automáticamente la tarifa de una plaza: consultar el grupo completo.
- Ida/vuelta conjunta puede tener precio y reglas distintos de la suma de dos idas.

Mantener dos resultados: menor precio anunciado y menor total comparable verificado. El primero nunca sustituye al segundo.

## 5. Cambios de precio y contexto

| Posible causa | Qué registrar o hacer |
|---|---|
| Inventario y clase tarifaria | Hora, plazas si se muestran y nivel de confianza; una etiqueta “últimas plazas” puede referirse solo a esa tarifa |
| Venta concurrente o vencimiento | Revalidar; guardar ambas observaciones y disponibilidad |
| Caché del metabuscador/agencia | Distinguir precio indicativo, resultado de búsqueda y oferta revalidada |
| Peticiones asíncronas | Esperar estado final o timeout; conservar indicador de búsqueda incompleta |
| Equipaje o pasajeros distintos | Comparar solo con la misma firma de búsqueda |
| Mercado, moneda o canal | Guardar contexto exacto; separar resultados con condiciones diferentes |
| Login, fidelización, membresía o cupón | Marcar condiciones y elegibilidad; perfil público reproducible como referencia |
| Cookies, sesión, IP o experimento A/B | Registrar perfil técnico sin datos sensibles; no atribuir causalidad a cookies sin experimento controlado |
| Impuestos, gastos y método de pago | Desglosar y actualizar total; separar cambio de tarifa de aparición de cargos |
| Redirección al vendedor | Verificar vuelo, fechas, tarifa, viajeros y condiciones tras el salto |
| Caducidad de oferta o enlace | Guardar expiración conocida; no inventarla; ofrecer refresco |
| Error del parser o cambio web | Aislar fuente, conservar evidencia depurada y excluir del ranking verificable |

No afirmar que buscar repetidamente encarece un vuelo ni que incógnito garantiza mejores precios. Una diferencia observada no demuestra personalización: inventario, tiempo y contexto pueden explicarla.

### Protocolo de revalidación

1. Crear `search_id` y firma del perfil; registrar inicio/fin UTC y contexto.
2. Consultar fuentes con concurrencia limitada y ventanas temporales acotadas.
3. Normalizar, validar, deduplicar y clasificar provisionalmente.
4. Revalidar las N mejores ofertas comparables (propuesta N=5) con el proveedor o vendedor, hasta el último paso no transaccional permitido.
5. Guardar precio inicial y nuevo, diferencia absoluta/porcentual, instante, condiciones y resultado: igual, subió, bajó, agotada, incompatible o no verificable.
6. Si una oferta empeora o desaparece, reordenar y revalidar candidatas siguientes dentro del presupuesto. Si se agota, declarar verificación parcial.
7. Publicar hora y alcance de verificación. Un TTL interno propuesto de 5 minutos es una política de frescura, no una garantía del vendedor.
8. Al abrir o refrescar una oferta antigua, volver a comprobarla; ninguna captura garantiza el precio hasta la emisión.

## 6. Ranking y deduplicación

Aplicar primero restricciones, reputación aprobada, disponibilidad, total completo y frescura. Orden principal por total comparable ascendente. Desempates: verificación más reciente, menor duración y preferencia configurable por venta directa. No introducir pesos ocultos.

Mostrar aparte: tarifas condicionales, costes incompletos, reputación pendiente, ofertas caducadas y resultados sin revalidar. Un precio alto válido no es error; un precio anormalmente bajo requiere comprobación, no eliminación automática.

Clave de itinerario: secuencia de segmentos con aeropuertos, salida UTC y número/operador normalizados. Conservar códigos compartidos. Clave de oferta: itinerario + vendedor + producto/condiciones + viajeros + perfil de extras + moneda/mercado. No fusionar tarifas con distinto equipaje o flexibilidad.

## 7. Modelo de datos previsto

| Entidad | Campos principales |
|---|---|
| search_runs | search_id, firma, parámetros, inicio/fin, fuentes solicitadas/completadas, estado, versión de configuración y software |
| source_runs | fuente, inicio/fin, latencia, páginas/resultados, estado, HTTP/error, reintentos, completitud |
| itineraries/segments | origen, destino, salida/llegada UTC y local con zona, vuelos, operador/comercializador, terminal, duración, escalas, protección |
| offer_observations | observation_id, search_id, fuente/vendedor, itinerario, tarifa, viajeros, importes/desglose, extras, moneda, contexto, observado_en, expiración conocida |
| revalidations | oferta/observación inicial, nuevo importe, checked_at, diferencias, estado, evidencia y paso alcanzado |
| sellers/reputation_reviews | entidad, dominios, grupo, política, evidencia fechada, revisión y estado |
| parser_evidence | hash, versión del parser, referencia de evidencia depurada, fecha y retención |

Los precios son observaciones inmutables: añadir una nueva fila, nunca sobrescribir la anterior. Identificadores de búsqueda y oferta sirven para idempotencia; una reejecución no debe duplicar la misma captura. Guardar UTC y presentar Europe/Madrid; no fijar manualmente UTC+1 porque existe horario de verano. Valores desconocidos son null con motivo, no cero.

No persistir cookies, tokens, datos de pago ni información personal innecesaria. Redactar URLs con identificadores sensibles y respuestas antes de guardarlas; secretos fuera del repositorio.

## 8. Arquitectura prevista

Flujo: configuración → planificador de búsquedas → adaptadores → captura → normalización → validación → deduplicación → revalidación → ranking → histórico/exportación.

Estructura propuesta:

- `src/scraperflights/config.py`: perfiles y límites.
- `src/scraperflights/providers/`: un adaptador por fuente.
- `src/scraperflights/models.py`: contratos de búsquedas/ofertas.
- `src/scraperflights/pricing.py`: costes y elegibilidad.
- `src/scraperflights/revalidation.py`: actualización de ofertas.
- `src/scraperflights/ranking.py`: filtros y orden.
- `src/scraperflights/storage.py`: histórico.
- `src/scraperflights/cli.py`: ejecución/exportación.
- `config/`: fuentes y perfiles sin secretos.
- `tests/fixtures/`: respuestas sintéticas o depuradas, nunca presentadas como precios actuales.

El contrato de adaptador devolverá ofertas, estado de completitud, advertencias, tiempos y procedencia. Debe distinguir cero ofertas de error, bloqueo, timeout, búsqueda parcial o ausencia de permisos.

## 9. Resiliencia y calidad

- Respetar condiciones de uso, robots cuando aplique, cuotas y restricciones de la fuente. Preferir interfaces autorizadas. Sin evasión de CAPTCHA, acceso o límites.
- Timeout por fuente, reintentos limitados con backoff/jitter para fallos transitorios y respeto de Retry-After. No reintentar sin límite ni repetir errores de autenticación.
- Aislar fallos por fuente; una caída no impide publicar las demás, pero el resultado declara cobertura incompleta.
- Validar esquema, moneda, decimales/localización, signo del precio, total/grupo, orden temporal, equipaje, ruta y duración.
- Cambios de HTML, selectores, JavaScript, banners, localización, paginación, API o esquema deben detectarse con contratos y fixtures; evitar fallos silenciosos.
- Métricas: éxito por fuente, latencia, resultados, ofertas incompletas, revalidaciones, variaciones, antigüedad, duplicados, costes y bloqueos.
- Evidencia mínima depurada y retención configurable; no publicar sesiones o datos personales en logs.
- Límites de consultas por fecha/fuente y caché por firma; una caché interna no se presenta como consulta recién ejecutada.
- Pruebas relevantes: grupo de viajeros, extras por tramo, monedas/redondeo, fechas/DST, códigos compartidos, membresías, costes desconocidos, subida/agotamiento al revalidar, fallos parciales y parser roto.
- Pruebas en vivo opcionales, con credenciales y presupuesto; datos sandbox y simulados identificados y excluidos del ranking real.

## 10. Salida esperada

Por oferta: ruta y fechas, salida/llegada, duración, aerolínea operadora, vendedor, tarifa, viajeros, equipaje incluido/requerido, precio anunciado, total comparable, extras/cargos, condiciones, reputación fechada, observado_en, verificado_en, caducidad conocida y enlace.

Por ejecución: fuentes consultadas, completadas y fallidas, intervalo de captura, perfil exacto, resultados parciales, candidatos descartados y motivo. Texto correcto: “menor total verificado entre X fuentes que respondieron, observado entre A y B”. Si no hay ninguna oferta verificable, decirlo sin elegir una ganadora artificial.

El histórico permite comparar la misma oferta y perfil a lo largo del tiempo, pero no garantiza tendencias futuras, disponibilidad ni “mejor día para comprar”.

## 11. Fases de implementación

1. Contratos, configuración, almacenamiento y ranking con datos sintéticos.
2. Validar acceso real de fuentes; integrar una fuente directa y una de comparación cuando sea posible. No prometer conectores hasta probarlos.
3. Revalidación, coste de equipaje y evaluación documentada de vendedores.
4. Ampliar agencias y fuentes según cobertura útil, permisos, calidad y coste.
5. CLI/exportaciones e histórico; automatización solo después de medir cuotas y estabilidad.

Criterio de aceptación: ambos sentidos, perfil reproducible, total completo o desconocido explícito, ranking auditable, histórico sin sobrescrituras, revalidación de finalistas, fallos parciales visibles y ausencia de afirmaciones de cobertura total.

## 12. Fuentes de referencia

Consulta de diseño: 2026-11-05. Capacidades y condiciones deben revisarse al implementar.

- Iberia, Puente Aéreo: https://www.iberia.com/es/puente-aereo/
- Vueling, ruta Barcelona–Madrid: https://www.vueling.com/es/vuelos-baratos-de-barcelona-a-madrid
- Skyscanner, precios live: https://developers.skyscanner.net/docs/flights-live-prices/overview
- Skyscanner, referencia y refresh: https://developers.skyscanner.net/api/flights-live-pricing
- Skyscanner, solicitud de acceso: https://www.partners.skyscanner.net/product/travel-api
- Amadeus, guía oficial de vuelos (Search/Price): https://github.com/amadeus4dev/developer-guides/blob/master/docs/resources/flights.md

Skyscanner documenta búsqueda live y refresco; el acceso y atributos como equipaje dependen del producto habilitado. Amadeus distingue búsqueda y confirmación de precio. Ninguna de estas referencias demuestra por sí sola que un conector tenga acceso aprobado, cubra todas las compañías o exponga todos los cargos del vendedor.
