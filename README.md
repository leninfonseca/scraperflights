# scraperflights

Buscador web y analizador de referencias de precio para Barcelona (BCN), Madrid (MAD) y Monterrey (MTY). Incluye avión y opciones terrestres BCN↔MAD.

## Iniciar en Windows

Desde CMD, en la carpeta del repositorio

```cmd
py -m pip install -e .
py -m scraperflights.viewer
```

Abre http://127.0.0.1:8765. El visor permite buscar, leer JSON/CSV de output y analizar precios históricos o archivos propios. Para actualizar, cierra el visor, ejecuta `git pull --ff-only` y vuelve a iniciarlo.

## Buscar desde CMD

```cmd
py -m scraperflights.cli search --origin BCN --destination MTY --date 2027-01-15 --return-date 2027-02-01
py -m scraperflights.cli search --origin BCN --destination MAD --date 2026-12-10 --modes train bus carpool
py -m scraperflights.cli compare --origin BCN --destination MTY --date 2027-01-15 --factor device
py -m scraperflights.cli sources --status implemented
```

Las rutas con Monterrey admiten escalas por defecto. `--direct-only` limita a directos. `--flex-days 2` amplía las fechas de salida dos días antes y después. El destino omitido conserva la búsqueda BCN↔MAD. `--both-directions` ejecuta búsquedas independientes invirtiendo origen y destino.

## Qué datos obtienes

La búsqueda utiliza 15 conectores HTML de vuelos y añade 4 terrestres para BCN↔MAD. El catálogo tiene 69 fuentes, con cobertura y estado de integración. Los resultados dependen de las páginas públicas y pueden tener mínimos orientativos, referencias fechadas, datos históricos o errores de acceso.

El visor separa medios y tramos, muestra el estado de cada fuente y conserva los datos originales. `lowest_dated_reference` es la menor referencia publicada de vuelo para las fechas solicitadas. `winner` requiere disponibilidad y costes finales verificados. Los mínimos de ruta, históricos y mensuales quedan en sus categorías. Las conexiones de billetes separados requieren planificar traslado y margen de embarque.

## Analizar históricos y Excel

En el visor, abre **Análisis histórico y variaciones porcentuales**. Puedes combinar SQLite, informes JSON y archivos XLSX, CSV, TSV o TXT propios. Revisa columnas, completa condiciones y selecciona una serie para ver mínimos, máximos, media, mediana y variaciones porcentuales.

Los CSV nuevos incorporan ruta, fechas, viajeros, equipaje y tipo de referencia para facilitar el análisis. Se conserva la lectura de informes antiguos. [Formato de importación y fórmulas](docs/analysis.md).

## Simular dispositivos y marcas

Abre **Laboratorio de dispositivos y marcas** en el mismo visor. Elige ruta y fechas arriba, perfiles de Apple, Samsung, Xiaomi o Google, un control y fuentes web. Guarda rondas, diferencias porcentuales y una repetición del control para observar ruido temporal. Los JSON se incorporan al análisis histórico por perfil. Son señales sintéticas; no cambian IP ni demuestran un efecto causal de marca. [Metodología, estudio y uso](docs/devices.md).

## Documentación

- [Fuentes e integración](docs/sources.md)
- [Arquitectura del proyecto](docs/architecture.md)
- [Análisis e importaciones](docs/analysis.md)

El visor admite `--output`, `--db` y `--port` para elegir carpetas y puerto. El navegador opcional se instala con `py -m pip install -e ".[browser]"` y `py -m playwright install chromium`.

## Validación

```cmd
py -m unittest discover -s tests -v
```

Las pruebas verifican cálculos, fechas, aislamiento de monedas y alcances, importaciones y contratos de las fuentes. La disponibilidad de las webs puede variar entre ejecuciones.
