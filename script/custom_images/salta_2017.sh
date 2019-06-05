#!/bin/bash
export OTB_MAX_RAM_HINT=8192

city=noa/salta
year=2017

dir=~/data/conae/_raw/$city
p1=$dir/SPOT6_20170121_1409016_BUNDLE_W065S25_L2A_16GT_044x068_32720

mkdir -p /tmp/$city/$year
mkdir -p ~/data/conae/_mosaicos/$city

# pansharpen
for tile in R1C1 R2C1; do
  otbcli_BundleToPerfectSensor -inp $p1/PROD_SPOT6_001/VOL_SPOT6_001_A/IMG_SPOT6_P_001_A/IMG_SPOT6_P_201701211409016_ORT_C0000000062690_$tile.TIF -inxs $p1/PROD_SPOT6_001/VOL_SPOT6_001_A/IMG_SPOT6_MS_001_A/IMG_SPOT6_MS_201701211409016_ORT_C0000000062690_$tile.TIF -interpolator bco -out /tmp/$city/$year/PMS_$tile.tif
done

# build virtual raster (merge)
gdalbuildvrt /tmp/$city/$year/mosaic.vrt /tmp/$city/$year/PMS_*.tif

# cut by extent of geojson
gdalwarp -t_srs epsg:4326 -multi -wo NUM_THREADS=ALL_CPUS -overwrite -cutline ~/ap-siu-habitat/data/areas/$city.geojson -crop_to_cutline -ot Uint16 -co TILED=YES /tmp/$city/$year/mosaic.vrt ~/data/conae/_mosaicos/$city/$year.tif
