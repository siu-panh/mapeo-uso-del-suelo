# Identificación de Usos del Suelo mediante Imágenes Satelitales

## Instalación

### Instalación manual (Windows)

La forma más sencilla de instalar lo necesario para ejecutar el código de este
repositorio es utilizando [Anaconda](https://www.anaconda.com/) y
[OSGeo4W](https://trac.osgeo.org/osgeo4w/).

Primero descargue el instalador de Anaconda para Python 3.7 version 64-bit, y
siga los pasos para instalarlo en su sistema.  Los notebooks fueron testeados
con la versión **2019-10**. 

Ejecute *Anaconda Prompt* para abrir una consola de linea de comandos con
Anaconda configurado. 

Ahora ejecute los siguientes comandos para crear un entorno virtual para el
proyecto y activarlo:

```
conda create -n mapeo python=3
conda activate mapeo
```

Luego, el siguiente comando para instalar y configurar GDAL, y otras
dependencias de Python:

```
conda install gdal==3.0.2
set GDAL_VERSION=3.0.2
pip install -r requirements.txt
```


### Instalación con Docker (Windows, Linux, OSX)

Como pre-requisito, debe tener instalado _Docker_ en el equipo donde quiere
ejecutar este proyecto. 

Para construir la imagen de _Docker_, debe ejecutar el script
`build_docker.bat` (Windows) o `build_docker.sh` (Linux, OSX). 


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

### Anaconda (Windows)

Ejecute Anaconda Prompt para abrir una consola, y active el entorno virtual:

```
conda activate mapeo
```

Luego, ejecute `jupyter notebook` para levantar el servidor de notebooks.
Entre a la URL que se imprime en pantalla con su navegador web.

### Docker

Ejecute `run_docker.bat` (Windows) o `run_docker.sh` (Linux, OSX) para ejecutar
el contenedor y activar Jupyter.

## Licencia

El código fuente de este repositorio está publicado bajo la Licencia Apache 2.0
Vea el archivo [LICENSE.md](LICENSE.md).
