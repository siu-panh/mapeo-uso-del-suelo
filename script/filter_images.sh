#!/bin/bash

# Usa script/filter_image.py para aplicar un filtro de mediana a todas las imagenes que estén en el directorio 
# indicado en $2/region/ciudad/año/_merged/image.tif 
# Guarda los tifs resultado en _mean/image_mean$1.tif dentro de cada directorio de año

SIZE=$1
RESULTS_PATH=$2

for region in $RESULTS_PATH/*; do
  for city in $region/*; do
    for year in $city/*; do
      infile=$year/_merged/image.tif
      outfile=$year/_mean/image_mean$SIZE.tif

      mkdir -p $(dirname $outfile)

      if [ ! -f "$outfile" ]; then
        script/filter_image.py $infile $outfile --size $SIZE
      fi
    done
  done
done
