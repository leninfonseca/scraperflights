# Estructura del proyecto

| Ruta | Función |
|---|---|
| cli.py | Comandos, ejecución y exportación de búsquedas |
| viewer.py | Servidor local y rutas del visor |
| core.py | Modelos, validación, clasificación e histórico SQLite |
| airports.py | Aeropuertos y opciones de ruta |
| connectors/web | Lectores HTML y datos incrustados de las fuentes |
| connectors/browser | Lectura con Chromium |
| connectors/feeds | Importación de ofertas estructuradas |
| analysis/imports.py | Lectura de tablas, XLSX y JSON históricos |
| analysis/metrics.py | Normalización, agrupación y porcentajes |
| analysis/service.py | Operaciones locales de histórico e importación |
| dashboard/app.js | Búsqueda y visualización de informes |
| dashboard/analysis.js | Importación y análisis interactivo |
| sources.json | Catálogo y cobertura |
| tests | Regresiones de cálculos, rutas y extracción |

Los adaptadores API históricos y providers.py se conservan por compatibilidad con los consumidores y pruebas existentes. La búsqueda de consola y del visor usa las fuentes web. Se retiró el protocolo base sin uso y se sustituyó el README de diseño inicial por instrucciones de ejecución y enlaces a documentación.

output y data contienen los archivos del usuario y están excluidos de git. Las tareas de limpieza se limitan a código y documentación obsoletos.
