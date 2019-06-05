#!/usr/bin/env python
# coding: utf-8

################################################
import os
import argparse
import ntpath
import multiprocessing
################################################


'''
1 - Toma una imágen TIF y extrae las features usando spfeas y las guarda en un archivo VRT
2 - A partir de un archivo vectorial .shp y las features se hace un muestreo y se genera un dataset
3 - Usando el dataset se entrena un modelo Random Forest 
4 - Se aplica el modelo sobre las features generadas en (1) para evaluar cuantitativa y cualitativamente el modelo entrenado
'''



# parametros
parser = argparse.ArgumentParser(description='Siu - Train')
parser.add_argument('tif', type=str, help='Ruta completa a imagen tiff a clasificar')
parser.add_argument('train', type=str, help='Ruta completa a shp con clases')
parser.add_argument('output', type=str, help='Ruta completa a carpeta donde genera resultado')
parser.add_argument('jobs', type=str, help='Cantidad de jobs')
parser.add_argument('trees', type=str, help='RF trees')
parser.add_argument('max_depth', type=str, help='RF profundidad')
parser.add_argument('--root_path', type=str, help='Path de la raiz de la aplicacion',default='/ap-siu-habitat')
args = parser.parse_args()

os.chdir(args.root_path)

tif_origen = args.tif
train_shp = args.train
n_jobs = args.jobs
trees = args.trees
max_depth = args.max_depth

path_features = args.output+"/features_train"
path_sampling = args.output+"/sampling_train"
path_model = args.output+"/model_train_rf_t"+trees+"_d"+max_depth
path_output = args.output+"/clasificacion_train_rf_t"+trees+"_d"+max_depth

head, nombre_tiff = ntpath.split(tif_origen)
nombre_tiff_sin_ext = os.path.splitext(nombre_tiff)[0]
path_vtr = path_features+"/"+nombre_tiff_sin_ext+"__BD1-2-3-4_BK8_SC8-16_TRfourier-dmp-pantex-lbpm-gabor-hog-lac-ndvi-mean.vrt"

head, nombre_shp = ntpath.split(train_shp)
nombre_shp_sin_ext = os.path.splitext(nombre_shp)[0]
path_samples_txt = path_sampling+"/"+nombre_shp_sin_ext+"_points__"+nombre_tiff_sin_ext+"__BD1-2-3-4_BK8_SC8-16_TRfourier-dmp-pantex-lbpm-gabor-hog-lac-ndvi-mean_SAMPLES.txt"
nombre_salida = os.path.basename(os.path.normpath(args.output))+"_rf_t"+trees+"_d"+max_depth
path_model_txt = path_model+"/"+nombre_salida+".txt"

# features
# genera vrt
genera_features = True
print("=>    1. Generando features")
if os.path.exists(path_vtr):
	print("=>    Features ya generado")
	genera_features = False

if genera_features:
	comando = "spfeas -i "+tif_origen+" -o "+path_features+" -tr fourier dmp pantex lbpm gabor hog lac ndvi mean -bp 1 2 3 4 --block 8 --scales 8 16 --stack --n-jobs "+n_jobs
	os.system(comando)

# sampling
# usa shp y vrt paso features
# genera dataset (samples.txt)
genera_sampling = True
print("=>    2. Generando dataset")
if os.path.exists(path_samples_txt):
	print("=>    Vtr ya generado")
	genera_sampling = False

if genera_sampling:	
	if os.path.exists(path_vtr):
		print("=>    Archivo tiff "+nombre_tiff_sin_ext)
		comando = "sample-raster -s "+train_shp+" -i "+path_vtr+" -o "+path_sampling+" -j "+n_jobs
		os.system(comando)
	else:
		print("=>    Falta vtr")

# modelo
# usa samples.txt paso sampling
# genera model.txt y accuracy.txt
genera_modelo = True
print("=>    3. Generando modelo")
if os.path.exists(path_model_txt):
	print("=>    Modelo ya generado")
	genera_modelo = False

if genera_modelo:		
	if os.path.exists(path_samples_txt):
		print("=>    Archivo shp "+nombre_shp_sin_ext)
		comando = "classify -s "+path_samples_txt+" --output-model "+path_model_txt+" --classifier-info \"{'classifier': 'rf', 'trees': "+trees+", 'max_depth': "+max_depth+"}\" --jobs "+n_jobs+" --v-jobs "+n_jobs
		os.system(comando)
	else:
		print("=>    Falta samples")

# clasificacion
# usa vrt paso features, samples.txt paso sampling y modelo paso anterior
# genera output_map.tif
genera_clasificacion = True
print("=>    4. Generando clasificacion")
if os.path.exists(path_output+"/"+nombre_salida+".tif"):
	print("=>    Salida ya generada")
	genera_clasificacion = False

if genera_clasificacion:	
	if os.path.exists(path_model_txt):
		comando = "classify -i "+path_vtr+" -o "+path_output+"/"+nombre_salida+".tif -s "+path_samples_txt+" --input-model "+path_model_txt+" --classifier-info \"{'classifier': 'rf', 'trees': "+trees+", 'max_depth': "+max_depth+"}\" --jobs "+n_jobs+" --v-jobs "+n_jobs
		os.system(comando)
	else:
		print("=>    Falta modelo")