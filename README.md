# scraperflights

Diseño de un comparador de vuelos Madrid–Barcelona y Barcelona–Madrid, con histórico de observaciones y revalidación de ofertas.

**Estado: CLI implementada con adaptadores API Amadeus y Skyscanner; requiere credenciales propias. Probada con respuestas simuladas; sin validación live autenticada en este entorno.** Las fuentes citadas son candidatas salvo indicación expresa. No se garantiza el mínimo de todo el mercado: se identifica la mejor oferta comparable observada entre las fuentes que respondieron, para una búsqueda y una ventana temporal concretas.


## Organización híbrida: ampliación pequeña

Secciones creadas: **API**, **web HTTP**, **navegador** y **feeds/archivos**, con contrato común. Los dos adaptadores existentes están en `connectors/api/`; las otras secciones están preparadas y todavía no extraen precios.

Catálogo de **18 fuentes** separado del registro de reputación. Añadidas **Atrápalo, Logitravel y Viajes El Corte Inglés** como candidatas. Los métodos propuestos no implican conectores operativos ni buena valoración confirmada.

```bash
scraperflights sources
scraperflights sources --category agency
scraperflights sources --method web --status candidate
scraperflights sources --status implemented
```

Este comando consulta el catálogo local y no realiza peticiones ni consume cuota API. Detalles y siguientes pasos: [docs/sources.md](docs/sources.md).

## Uso del programa implementado

Requiere Python 3.11 o posterior. No tiene dependencias de ejecución externas.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
scraperflights doctor
```

Configura credenciales como variables de entorno (no las subas al repositorio). `.env.example` contiene sus nombres; el programa **no carga .env automáticamente**.

- Amadeus: `AMADEUS_CLIENT_ID` y `AMADEUS_CLIENT_SECRET`; `AMADEUS_ENV=production` para inventario real o `test` para sandbox. El acceso a producción debe estar autorizado por el proveedor. Cobertura limitada por su producto; no asumir todas las low cost.
- Skyscanner: `SKYSCANNER_API_KEY`, con acceso aprobado a Travel API. Busca compañías y vendedores disponibles en su inventario, no una lista fija de agencias.
- `doctor` solo informa presencia de variables; no valida permisos, saldo ni credenciales.

```bash
# Sustituye las fechas por fechas futuras.
scraperflights search --origin MAD --date 2026-12-10 --both-directions
scraperflights search --origin BCN --date 2026-12-10 --return-date 2026-12-15 --adults 2
scraperflights search --origin BCN --date 2026-12-10 --flex-days 2 --checked-bags 1 --budget 30 --top 5
scraperflights history --limit 10
```

`--both-directions` ejecuta dos búsquedas independientes; no crea un billete de ida/vuelta. `--flex-days` desplaza la ida y mantiene fija la vuelta. Valida todas las fechas antes de consultar. Hasta 30 búsquedas por invocación (±7 días y ambos sentidos); `--budget` aplica a **cada búsqueda**, contando autenticación, polling, revalidación y reintentos. Cada petición tiene timeout de 20 s y hasta 3 intentos transitorios; no existe un plazo global de ejecución. Las fuentes se ejecutan secuencialmente.

Se guardan histórico SQLite en `data/flights.sqlite` y reportes JSON/CSV en `output/`. Estas carpetas están excluidas de git. Los reportes contienen enlaces del vendedor que pueden caducar: trátalos como privados. No se persisten las claves ni las respuestas completas con tokens. CSV protege campos que podrían interpretarse como fórmulas.

### Qué hace realmente esta versión

| Función | Estado |
|---|---|
| MAD ↔ BCN, adultos, turista, EUR, directos/escalas | Implementado |
| Ida/vuelta, fechas flexibles y ambos sentidos independientes | Implementado |
| Consulta Amadeus Search y Price | Implementado; credenciales necesarias; pendiente smoke test live |
| Skyscanner create/poll y refresh create/poll | Implementado; acceso partner necesario; pendiente smoke test live |
| Vendedores de Skyscanner | Se extraen dinámicamente con precio y enlace cuando existen |
| Revalidación de finalistas y variaciones | Implementado; fallos y búsquedas parciales explícitos |
| Precio mínimo observado | `lowest_observed`, provisional, sin garantía de coste final |
| Total final y ganador verificable | Solo elegible si hay total completo, reputación aprobada y verificación reciente; los adaptadores actuales no certifican gastos finales de checkout |
| Equipaje requerido | Se captura lo informado; si se solicita equipaje, el coste necesario no confirmado bloquea el ranking final |
| Reputación | Registro manual con evidencia y caducidad de 90 días; sin puntuaciones inventadas |
| Histórico/exportación, límites y aislamiento de fallos | Implementado |
| Scraping directo de webs de aerolíneas/agencias | Pendiente; no hay parsers web activos ni evasión de bloqueos |
| Niños/bebés, descuentos, otras cabinas/monedas, filtros horarios | Variables documentadas; aún no expuestas en CLI |
| Comparar automáticamente ida/vuelta conjunta con dos billetes | Pendiente; hoy son búsquedas explícitas separadas |
| Alertas/ejecución periódica | No configuradas; CI ejecuta pruebas, no búsquedas de pago |

**No se inventa un ganador final.** Un precio API revalidado sigue sin demostrar los gastos aplicables al pago en la agencia. Las ofertas se muestran en `pending` con motivos y en `lowest_observed`; `winner` permanece null si falta evidencia. Esto es deliberado y evita prometer un ahorro con costes desconocidos. El primer paso de activación real es configurar al menos una credencial y ejecutar una búsqueda futura.

### Registro de vendedores

`config/sellers.json` comienza vacío porque aún no se han verificado reseñas actuales. Usa el nombre exacto del vendedor devuelto por la API. Una aprobación requiere revisión humana y evidencia; no permite omitir otros bloqueos del precio.

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

- `complete`: el proveedor terminó la consulta; no significa todo el mercado ni precio de checkout.
- `partial`: polling sin finalizar o límite de 100 ofertas de Amadeus.
- `credentials_missing`: falta configuración; no se ha consultado.
- `error`: red, permisos/cuota, presupuesto, respuesta inválida o cambio de esquema.
- Código 0: respondió al menos una fuente, aunque no haya ofertas o ganador; 2: ninguna respondió o argumentos inválidos.

`coverage_complete` solo describe las fuentes solicitadas. Amadeus no proporciona aquí vendedor minorista final ni enlace de compra. No llamar reserva a una confirmación de precio: el código no invoca endpoints de reserva.

El resto del README conserva el **diseño objetivo** y todas las variables a considerar; la tabla anterior es la referencia del alcance ya implementado.

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
