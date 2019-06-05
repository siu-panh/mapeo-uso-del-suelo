#!/bin/bash
export OTB_MAX_RAM_HINT=8192

city=patagonia/rio_grande
year=2017

dir=~/data/conae/_raw/$city
p1=$dir/SPOT6_20170406_1350249_BUNDLE_W068S53_L2A_16GT_062x162_32719
p2=$dir/SPOT6_20170211_1406157_PMS_W068S54_L2A_16GT_010x012_4326

mkdir -p /tmp/$city/$year
mkdir -p ~/data/conae/_mosaicos/$city

# pansharpen
for tile in R1C1 R1C2 R2C1 R2C2 R3C1 R3C2 R4C1 R4C2; do
  otbcli_BundleToPerfectSensor -inp $p1/PROD_SPOT6_001/VOL_SPOT6_001_A/IMG_SPOT6_P_001_A/IMG_SPOT6_P_201704061350249_ORT_C0000000078640_$tile.TIF -inxs $p1/PROD_SPOT6_001/VOL_SPOT6_001_A/IMG_SPOT6_MS_001_A/IMG_SPOT6_MS_201704061350249_ORT_C0000000078640_$tile.TIF -interpolator bco -out /tmp/$city/$year/PMS_$tile.tif
done

# build virtual raster (merge)
gdalbuildvrt /tmp/$city/$year/mosaic.vrt /tmp/$city/$year/PMS_*.tif

# cut by extent of geojson
gdalwarp -t_srs epsg:4326 -multi -wo NUM_THREADS=ALL_CPUS -overwrite -cutline ~/ap-siu-habitat/data/areas/$city.geojson -crop_to_cutline -ot Uint16 -co TILED=YES $p2/PROD_SPOT6_001/VOL_SPOT6_001_A/IMG_SPOT6_PMS_001_A/IMG_SPOT6_PMS_201702111406157_ORT_C0000000058870_R1C1.TIF /tmp/$city/$year/mosaic.vrt ~/data/conae/_mosaicos/$city/$year.tif
