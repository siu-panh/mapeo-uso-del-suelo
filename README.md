# Identificación de Usos del Suelo mediante Imágenes Satelitales

## Instalación

### Construcción de la imágen _Docker_

Como pre-requisito, debe tener instalado _Docker_ en el equipo donde quiere
ejecutar este proyecto. 

Los pasos para construir la imágen y correr el container _Docker_ son los
siguientes

1. Construir la imagen con el script `build_docker.bat`
2. Ejecutar el container con el script  `run_docker.bat`
3. Acceder al servidor `jupyter` haciendo click en el link

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
