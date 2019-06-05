#!/bin/bash
export OTB_MAX_RAM_HINT=8192

city=noa/tucuman
year=2015

dir=~/data/conae/_raw/$city
p1=$dir/SPOT7_20150630_1402042_BUNDLE_W065S27_L2A_16GT_036x030_32720

mkdir -p /tmp/$city/$year
mkdir -p ~/data/conae/_mosaicos/$city

# pansharpen
for tile in R1C1; do
  otbcli_BundleToPerfectSensor -inp $p1/PROD_SPOT7_001/VOL_SPOT7_001_A/IMG_SPOT7_P_001_A/IMG_SPOT7_P_201506301402042_ORT_C0000000063280_$tile.TIF -inxs $p1/PROD_SPOT7_001/VOL_SPOT7_001_A/IMG_SPOT7_MS_001_A/IMG_SPOT7_MS_201506301402042_ORT_C0000000063280_$tile.TIF -interpolator bco -out /tmp/$city/$year/PMS_$tile.tif
done

# build virtual raster (merge)
gdalbuildvrt /tmp/$city/$year/mosaic.vrt /tmp/$city/$year/PMS_*.tif

# cut by extent of geojson
gdalwarp -t_srs epsg:4326 -multi -wo NUM_THREADS=ALL_CPUS -overwrite -cutline ~/ap-siu-habitat/data/areas/$city.geojson -crop_to_cutline -ot Uint16 -co TILED=YES /tmp/$city/$year/mosaic.vrt ~/data/conae/_mosaicos/$city/$year.tif
