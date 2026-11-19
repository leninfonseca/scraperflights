# Laboratorio de dispositivos

En el visor local abre **Laboratorio de dispositivos y marcas**. Utiliza la ruta, salida y regreso de **Nueva búsqueda**, elige el perfil de control, varios dispositivos y entre una y cuatro fuentes. Ejecuta entre una y tres rondas. Cada ronda hace una consulta por dispositivo y una segunda consulta del control. Se invierte el orden entre rondas. El contador muestra el coste previsto; los errores y fuentes sin datos también quedan registrados.

Los ocho perfiles son Linux, Windows, Mac, Pixel 7, Redmi Note 13, Samsung Galaxy A14 (SM-A145F), Samsung Galaxy S24 (SM-S921B) e iPhone/iOS 17. Los identificadores estables usan navegadores de referencia, no pretenden ser versiones actuales. Gama económica/alta son etiquetas orientativas de muestreo, no precios actuales del aparato ni predicciones sobre el vuelo. En iPhone el User-Agent no identifica el modelo ni su precio, por lo que no podemos distinguir un iPhone barato de uno caro con esta señal.

## Qué se simula

- En HTML se envían User-Agent y Accept-Language; cada consulta usa una sesión nueva. No se transmite una etiqueta de «gama» al vendedor.
- En el conector opcional vueling-browser se añaden viewport, escala y señales táctiles en Chromium. Safari/iOS sigue siendo una simulación parcial: no cambia el motor ni toda la huella. La marca de un portátil Windows no es observable mediante su User-Agent genérico.
- Declarar un modelo Android permite probar esa señal, pero Chrome real puede reducir el User-Agent y ocultar el modelo. No se emulan Client Hints específicos de cada marca ni hardware físico.
- No se cambia IP, país de salida, cuenta, moneda ni ubicación GPS. Un perfil de dispositivo agrupa varias señales: una diferencia no permite aislar la marca de sistema operativo, navegador o tamaño de pantalla.

## Base científica y límites

Hannak, Soeller, Lazer, Mislove y Wilson, **Measuring Price Discrimination and Steering on E-commerce Web Sites**, IMC 2014: [proyecto original](https://personalization.ccs.neu.edu/Projects/PriceDiscrimination/) y [artículo](https://www.ccs.neu.edu/~amislove/publications/Ecommerce-IMC.pdf).

El estudio midió personalización por navegador/sistema y otros factores en comercios y webs de hoteles/alquiler de coches. Distingue discriminación de precio para un mismo producto de cambios en la selección/orden de productos. No demuestra que una marca de teléfono cara encarezca un billete de avión actual. Tampoco permite asignar un porcentaje esperado a Apple, Samsung o Xiaomi. Estos perfiles son hipótesis experimentales para tus propias observaciones.

Comparamos mínimos publicados con el mismo alcance y moneda. Pueden corresponder a vuelos/tarifas diferentes. Inventario, caché, tiempo y pruebas A/B pueden producir diferencias. La repetición de control ayuda a detectar ruido, pero no elimina esos factores ni constituye una prueba estadística causal. No se anuncia un «dispositivo ganador» para comprar.

## Resultados y análisis posterior

El JSON `output/comparison-<id>.json` conserva perfiles, ruta, rondas, orden, tiempos, errores, mínimos y diferencias absolutas y porcentuales. La fórmula es `(B − A) / A × 100`, siendo A el control. Sin pareja comparable o con A cero el porcentaje queda vacío; una diferencia cero sí es un resultado válido. La repetición del control tiene su propio detalle en cada ronda.

El informe se abre en el mismo HTML y aparece en la lista de informes. Para seguir la evolución por dispositivo, en **Análisis histórico y variaciones porcentuales** pulsa **Cargar histórico local**, o importa ese JSON. Se mantienen separadas las series de perfiles distintos. Los porcentajes entre dispositivos se muestran en el informe del experimento; los porcentajes históricos comparan observaciones dentro de cada perfil. Las consultas de control repetidas se conservan en el JSON original como `control_run` y sus métricas en `control_comparisons`.

Desde CMD:

```cmd
py -m scraperflights.cli compare --origin BCN --destination MTY --date 2027-01-15 --devices redmi galaxy-a galaxy-s iphone mac --baseline desktop --providers iberia-web aeromexico-web --rounds 2
```

Sin `--devices` se conserva la comparación anterior de dos perfiles con `--factor device`, `locale` o `session`. Con perfiles múltiples, se usan dos fuentes por defecto; puedes elegir hasta cuatro. Para Chromium instala los extras de navegador y selecciona explícitamente `vueling-browser` (limitado a su ruta/calendario compatible).
