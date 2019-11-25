# Identificación de Usos del Suelo mediante Imágenes Satelitales

## Instalación

Como pre-requisito, debe tener instalado _Docker_ en el equipo donde quiere
ejecutar este proyecto. 

Para construir la imagen de _Docker_, debe ejecutar el script `build_docker.sh`. 

Ejecute `run_docker.sh` para ejecutar
el contenedor y activar Jupyter.


## Uso

Esta metodología está basada en el uso de las librerías [SpFeas](https://github.com/jgrss/spfeas) y [MpGLue](https://github.com/jgrss/mpglue).

A través del servidor `jupyter`, puede acceder a dos _notebooks_ que contienen
ejemplos de como ejecutar los scripts y código necesario para procesar y
analizar las imágenes satelitales, con el objetivo de generar los mapas de uso
del suelo.

El notebook `TrainAndTest.ipynb` ubicado en la raíz del proyecto, explica como
usar los scripts para entrenar un modelo sobre mapas y datos etiquetados de una
ciudad y un año en específico y además como aplicar ese modelo sobre otra (o la
misma) imágen raster para clasificar las zonas de las mismas. 

El notebook `PostProcessing.ipynb` explica como usar los scripts que permiten
post-procesar las salidas del modelo para generar las estadísticas y mapas de
uso del suelo.

### Imagen Entrada

Se presenta a continuación un ejemplo para un área de la ciudad de Concordia (Entre Ríos) a partir de la anotación de un pequeño número de áreas con usos del suelo definidos.

![Concordia, Entre Ríos (2016)](https://github.com/siu-panh/mapeo-uso-del-suelo/blob/master/concordia_2016_spot.png)

### Resultados

Los resultados de aplicar la metodología son los siguientes.

![Mapa de usos del suelo estimado para Concordia, Entre Ríos (2016)](https://github.com/siu-panh/mapeo-uso-del-suelo/blob/master/concordia_2016_land_use.png)

Realizando el mismo análisis para los años 2015-2016-2017-2018, podemos calcular la variabilidad en el uso a lo largo del tiempo.

![Histograma de usos del suelo estimados para Concordia, Entre Ríos (2015-2018](https://github.com/siu-panh/mapeo-uso-del-suelo/blob/master/concordia_2016_histogram.png)



## Licencia

El código fuente de este repositorio está publicado bajo la Licencia Apache 2.0
Vea el archivo [LICENSE.md](LICENSE.md).
