#!/bin/bash
# Hace un merge de todos los *.tif que hay en el directorio pasado como paraemtro
# Asume una estructura de directorios region/ciudad/año/*.tif 
# Guarda los tifs resultado en _merged/image.tif dentro de cada directorio de año

RESULTS_PATH=$1

for region in $RESULTS_PATH/*; do
  for city in $region/*; do
    for year in $city/*; do
      infiles=$year/*.tif
      outfile=$year/_merged/image.tif

      mkdir -p $(dirname $outfile)

      if [ ! -f "$outfile" ]; then
        gdal_merge.py -q -o $outfile -co COMPRESS=DEFLATE $infiles
      fi
    done
  done
done
