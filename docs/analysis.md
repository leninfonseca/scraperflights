# Análisis de precios

El apartado Análisis del visor carga observaciones del histórico SQLite y JSON de output. También admite XLSX, CSV, TSV, TXT tabular y JSON propios. Los XLS antiguos deben guardarse como XLSX.

## Importar datos propios

1. Selecciona uno o varios archivos. En XLSX se presentan las hojas por separado.
2. Revisa las columnas detectadas y asigna cada campo. Las columnas con nombres canónicos se detectan automáticamente.
3. Completa valores por defecto cuando falten moneda, ruta, fechas, medio o tipo de referencia.
4. Valida la tabla. El visor indica las filas aceptadas y los motivos de exclusión.
5. Selecciona una serie para ver evolución, porcentajes y procedencia.

Campos obligatorios

| Campo | Contenido |
|---|---|
| amount | Precio numérico no negativo. Admite 1234.56 y 1.234,56 |
| observed_at | Fecha y hora de la captura. ISO o dd/mm/aaaa |
| origin y destination | Códigos IATA diferentes |
| departure | Fecha de salida del viaje |
| currency | Código ISO como EUR o MXN |
| transport_mode | flight, train, bus o carpool |
| scope | Tipo de referencia. Para una serie propia puedes declarar user_reference |

Campos adicionales recomendados son regreso, fuente, vendedor, tramo, viajeros, equipaje, perfil y comparison_group. Usa comparison_group para identificar la misma tarifa o billete cuando dispongas de esa información. Se agrupan solo valores iguales. Si las condiciones faltan, la serie representa referencias declaradas y puede contener ofertas distintas.

Las fechas sin hora se sitúan a medianoche. Las fechas sin zona usan Europe/Madrid. Cuando varios precios diferentes comparten hora, se omiten los porcentajes temporales para evitar inventar un orden. Se conservan todos los importes.

## Cálculos

- Variación respecto al primero = (último − primero) / primero × 100.
- Variación anterior = (último − anterior) / anterior × 100.
- Variación frente a mediana = (último − mediana) / mediana × 100.
- Rango porcentual = (máximo − mínimo) / mínimo × 100.
- Una base cero se muestra sin porcentaje. Una sola observación no tiene variación temporal.

El comparador separa las monedas, fechas de viaje, origen/destino, medio, tramo, alcance, proveedor, vendedor, viajeros, equipaje y perfil. Los datos de sandbox se excluyen. Los mínimos mensuales, de ruta, históricos y de tramos forman series distintas.

## Límites y almacenamiento

Archivos de hasta 8 MB y 20.000 filas por conjunto. XLSX descomprimido de hasta 32 MB y 256 columnas por hoja. El lector usa los valores guardados en Excel. Las fórmulas sin resultado guardado se tratan como celdas vacías y no se ejecutan macros ni vínculos externos. El libro debe tener cabeceras en su primera fila.

Las importaciones se procesan en el servidor local. El análisis conserva los datos en la sesión del navegador y ofrece exportar el resumen porcentual como CSV. Los archivos originales y el histórico se mantienen intactos. Si cierras o recargas la página, vuelve a cargar el histórico o los archivos.

Los duplicados con la misma serie, hora e importe se cuentan una sola vez y conservan su procedencia. El histórico combina SQLite y los JSON con ese criterio. Los CSV originales del scraper anteriores a esta ampliación carecen de algunos campos. Para ellos, completa las condiciones o carga el JSON del mismo nombre.
