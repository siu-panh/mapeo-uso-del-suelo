#!/bin/bash
# Script para tomar los resultados de clasificaciones para un año dado y generar la estructura de archivos necesaria para post-procesar y obtener estadísticas y plots
# Recibe 
# $1 : año a procesar , ej.: 2016
# $2 : region/ciudad , ej.: centro/concordia
# $3 : path donde van a ser copiados los resultados de la clasificación , ej.: data/resultados/finales
# $4 : carpeta donde estan los resultados de aplicar el modelo y clasificar una imágen , ej.: data/concordia2016_train_rf_t107_d1007/clasificacion_train_rf_t107_d1007
# $5 : carpeta donde están las imágenes originales , ej.: data/conae/centro/concordia/SPOT7_20160128_1334024_PMS_W058S31_L2A_16GT_010x011_4326/PROD_SPOT7_001/VOL_SPOT7_001_A/IMG_SPOT7_PMS_001_A
# $6 : carpeta donde queremos dejar el raster virtual resultado de las imágenes crudas unidas , ej.: data/imagenes_orig


# Crear el directorio
results_full_path=$3'/'$2'/'$1'/'
mkdir -p $results_full_path

# Copiar clasificación a la carpeta
cp $4/*.tif $results_full_path

# Generar raster virtual .vrt con las imágenes originales
original_images_full_path=$6'/'$2
mkdir -p $original_images_full_path
gdalbuildvrt $original_images_full_path/$1.vrt $5/*.{tif,TIF}

