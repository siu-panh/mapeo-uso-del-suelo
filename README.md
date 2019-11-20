# Identificación de Usos del Suelo mediante Imágenes Satelitales

## Instalación

Como pre-requisito, debe tener instalado _Docker_ en el equipo donde quiere
ejecutar este proyecto. 

Para construir la imagen de _Docker_, debe ejecutar el script `build_docker.sh`. 

Ejecute `run_docker.sh` para ejecutar
el contenedor y activar Jupyter.


## Uso

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


## Licencia

El código fuente de este repositorio está publicado bajo la Licencia Apache 2.0
Vea el archivo [LICENSE.md](LICENSE.md).
