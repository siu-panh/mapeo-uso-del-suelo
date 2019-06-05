#!/usr/bin/env python3
"""
This script takes all post-processed images from results directory and bundles
them into a .zip file

"""
import os
import subprocess
from glob import glob
import shutil
import tempfile


def main(args):
    with tempfile.TemporaryDirectory() as tmpdir:
        regions = sorted(glob(os.path.join(args.results_dir, '*')))
        if args.only_regions:
            regions = [r for r in regions if os.path.basename(r) in args.only_regions]
        for region in regions:
            cities = sorted(glob(os.path.join(region, '*')))
            for city in cities:
                years = sorted(glob(os.path.join(city, '*')))
                for year in years:
                    src_path = os.path.join(year, args.result_image_path)
                    dst_path = os.path.join(tmpdir,
                            os.path.basename(region), os.path.basename(city),
                            '{}.tif'.format(os.path.basename(year)))
                    print("copy", src_path, dst_path)
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copyfile(src_path, dst_path)
        output = os.path.abspath(args.output)
        cmd = 'zip -r {output} *'.format(output=output)
        print(cmd)
        subprocess.run(cmd, cwd=tmpdir, shell=True)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Bundle prediction results into a .zip file',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--results-dir',
                        default=os.path.join('data', 'resultados', 'finales'),
                        help='path to results dir')
    parser.add_argument('--result-image-path',
                        default='_mean/image_mean5.tif',
                        help='path to raster image inside "year" directory')
    parser.add_argument('--only-regions', '-r', nargs='+',
                        help='only process specific region')
    parser.add_argument(
        '-o',
        '--output',
        default='usos_suelo_predict.zip',
        help='path to output zip file')

    args = parser.parse_args()

    main(args)
