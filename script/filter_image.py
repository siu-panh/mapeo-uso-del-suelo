#!/usr/bin/env python3
"""
This script applies a median filter to a geotiff raster

"""

from skimage.filters import median
from skimage.morphology import disk
import rasterio


def main(args):
    with rasterio.open(args.input) as src:
        with rasterio.open(args.output, 'w', **src.meta.copy()) as dst:
            for b in range(src.count):
                img = src.read(indexes=b+1)
                new_img = median(img, disk(args.size))
                dst.write(new_img, indexes=b+1)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Apply median filter to raster',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        'input',
        help='path to input raster image')
    parser.add_argument(
        'output',
        help='path to output raster image')
    parser.add_argument(
        '--size',
        default=3,
        type=int,
        help='kernel size')

    args = parser.parse_args()

    main(args)
