#!/bin/bash
export OTB_MAX_RAM_HINT=8192

city=patagonia/rawson
year=2016

dir=~/data/conae/_raw/$city
p1=$dir/SPOT7_20160202_1348442_BUNDLE_W065S43_L2A_16GT_010x007_32720

s2_img=$dir/s2_2016.tif

mkdir -p /tmp/$city/$year
mkdir -p ~/data/conae/_mosaicos/$city

# pansharpen and reproject to epsg:4326
for tile in R1C1; do
  otbcli_BundleToPerfectSensor -inp $p1/PROD_SPOT7_001/VOL_SPOT7_001_A/IMG_SPOT7_P_001_A/IMG_SPOT7_P_201602021348442_ORT_C0000000061930_$tile.TIF -inxs $p1/PROD_SPOT7_001/VOL_SPOT7_001_A/IMG_SPOT7_MS_001_A/IMG_SPOT7_MS_201602021348442_ORT_C0000000061930_$tile.TIF -interpolator bco -out /tmp/$city/$year/PMS_$tile.tif
  gdalwarp -ot Uint16 -t_srs epsg:4326 -dstnodata 0 -multi -wo NUM_THREADS=ALL_CPUS -overwrite /tmp/$city/$year/PMS_$tile.tif /tmp/$city/$year/PMS_4326_$tile.tif
  gdal_translate -b 1 -b 2 -b 3 -a_nodata 0 /tmp/$city/$year/PMS_4326_$tile.tif /tmp/$city/$year/PMS_4326_RGB_$tile.tif
done

# rescale S2 image
gdal_translate -ot Uint16 -scale 0 15.0 0 65535 $s2_img /tmp/$city/$year/S2.tif

# merge and cut by extent of geojson
gdalwarp -r cubic -t_srs epsg:4326 -dstnodata 0 -multi -wo NUM_THREADS=ALL_CPUS -overwrite -cutline ~/ap-siu-habitat/data/areas/$city.geojson -crop_to_cutline -co TILED=YES /tmp/$city/$year/S2.tif /tmp/$city/$year/PMS_4326_RGB_*.tif ~/data/conae/_mosaicos/$city/$year.tif
