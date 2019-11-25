#!/usr/bin/env python3
"""
This script generates bar plots of soil use changes and renders map for all cities

"""
import os
from glob import glob

import matplotlib.cm as cm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import tempfile
from tqdm import tqdm
from matplotlib.colors import ListedColormap
from skimage import exposure

CITIES = {
    'centro/concordia': 'Concordia',
    'centro/parana': 'Paraná',
    'centro/cordoba': 'Córdoba',
    'centro/rosario': 'Rosario',
    'centro/santa_fe': 'Santa Fé',
    'cuyo/mendoza': 'Mendoza',
    'cuyo/san_juan': 'San Juan',
    'cuyo/san_luis': 'San Luis',
    'bs_as/bs_as': 'Buenos Aires',
    'bs_as/la_plata': 'La Plata',
    'bs_as/mdq': 'Mar del Plata',
    'noa/catamarca': 'San Fernando del Valle de Catamarca',
    'noa/jujuy': 'San Salvador de Jujuy',
    'noa/la_rioja': 'La Rioja',
    'noa/salta': 'Salta',
    'noa/santiago': 'Santiago del Estero',
    'noa/tucuman': 'San Miguel de Tucumán',
    'nea/corrientes': 'Corrientes',
    'nea/formosa': 'Formosa',
    'nea/posadas': 'Posadas',
    'nea/resistencia': 'Resistencia',
}

# Precalculated precentiles for each city-year
PERC_CITY_YEAR = {
    'bs_as/bs_as/2015': ((0, 820), (0, 877), (0, 894)),
    'bs_as/bs_as/2016': ((160, 1250), (234, 1361), (267, 1332)),
    'bs_as/bs_as/2017': ((190, 1023), (269, 1075), (284, 1032)),
    'bs_as/bs_as/2018': ((111, 777), (163, 825), (195, 779)),
}

CLASSES = [
    "Área Urbana Informal", "Áreas urbanas formales", "Vegetación",
    "Suelo sin cobertura vegetal", "Cuerpos de agua"
]

COLORS = ['#fefd21ff', '#8d8a86ff', '#73fcaaff', '#ba6648ff', '#0200b3ff']


def area_percs_by_cls(raster):
    with rasterio.open(raster) as src:
        img = src.read(1)
    classes, counts = np.unique(img, return_counts=True)
    total_count = np.count_nonzero(img)
    return {
        cls: count / total_count
        for cls, count in zip(classes, counts) if cls > 0
    }


def calculate_area_all_years(years, images):
    temp = {1: [], 2: [], 3: [], 4: [], 5: []}
    for year, path in zip(years, images):
        area_percs = area_percs_by_cls(path)
        for cls, area in area_percs.items():
            if cls not in temp:
                temp[cls] = []
            temp[cls].append(area * 100)
    res = []
    for cls, areas in temp.items():
        res.extend(areas)
    return res


def flatten(ls):
    return [l2 for l1 in ls for l2 in l1]


def plot_histogram(values, name=None, output=None, *, years):
    if output and os.path.exists(output):
        return

    y_pos = np.arange(len(values))
    color = flatten([[c] * len(years) for c in COLORS])
    bars = flatten([years] * len(CLASSES))

    plt.figure(figsize=(14, 7))
    if name:
        plt.title("{} - Estadísticas de Uso del Suelo".format(name))
    plt.grid(linestyle='--')
    plt.bar(y_pos, values, color=color)
    patches = [
        mpatches.Patch(color=color, label=label)
        for color, label in zip(COLORS, CLASSES)
    ]
    plt.legend(patches, CLASSES)
    plt.xticks(y_pos, bars)
    plt.tight_layout()
    if output:
        plt.savefig(output.format(name=name), dpi=200)
    else:
        plt.show()
    plt.close()


def plot_image(image, name=None, output=None):
    if output and os.path.exists(output):
        return

    with rasterio.open(image) as src:
        img = src.read(1)

    cmap = ListedColormap(COLORS, name='soil_use_cm')
    plt.figure(figsize=(14, 7))
    if name:
        plt.title("{} - Mapa de uso del suelo".format(name))
    patches = [
        mpatches.Patch(color=color, label=label)
        for color, label in zip(COLORS, CLASSES)
    ]
    plt.legend(patches, CLASSES)
    plt.tight_layout()
    plt.imshow(img, cmap=cmap, vmin=1, vmax=5)
    if output:
        plt.savefig(output.format(name=name), dpi=150)
    else:
        plt.show()
    plt.close()


def get_precalc_percentiles(region_city, year):
    return PERC_CITY_YEAR.get(os.path.join(region_city, str(year)), ())


def calculate_percentiles(image):
    print("Calculate percentiles for", image)
    res = []
    with rasterio.open(image) as src:
        for b in range(1, 4):
            img = src.read(b)
            perc = np.percentile(img, (2, 98))
            res.append(perc)
    return res


def plot_rgb_image(image, name=None, output=None, band_percentiles=None):
    if output and os.path.exists(output):
        return

    if not band_percentiles:
        band_percentiles = calculate_percentiles(image)

    tmpfile = os.path.join(tempfile.gettempdir(), 'rgb_temp.tif')
    with rasterio.open(image) as src:
        profile = src.profile.copy()
        profile.update(driver='GTiff', dtype=np.uint8)

        with rasterio.open(tmpfile, 'w', **profile) as dst:
            for b in range(1, 4):
                percentiles = band_percentiles[b-1]

                print("[{}] Process band {}".format(image, b))
                for ji, window in tqdm(list(src.block_windows(b))):
                    img = src.read(window=window, indexes=b)
                    img = exposure.rescale_intensity(img,
                            in_range=tuple(percentiles),
                            out_range=(0, 255)).astype(np.uint8)
                    dst.write(img, indexes=b, window=window)

    print("[{}] Read image".format(image))
    with rasterio.open(tmpfile) as src:
        img = np.dstack([src.read(b) for b in range(1, 4)])

    #info = np.iinfo(img.dtype)
    #img = np.interp(img, (info.min, info.max), (0, 1))

    print("[{}] Render map".format(image))
    plt.figure(figsize=(14, 7))
    if name:
        plt.title("{} - Imagen original".format(name))
    plt.tight_layout()
    plt.imshow(img)
    if output:
        plt.savefig(output.format(name=name), dpi=150)
    else:
        plt.show()

    plt.close()
    os.remove(tmpfile)


def main(args):
    for region_city, name in CITIES.items():
        print("*** {} ***".format(region_city))

        city_path = os.path.join(args.results_dir, region_city)
        year_paths = sorted(glob(os.path.join(city_path, '*')))
        years = [int(os.path.split(p)[-1]) for p in year_paths]
        print("years = {}".format(years))

        result_image_paths = [
            glob(os.path.join(city_path, str(year), args.result_image_path))[0]
            for year in years
        ]

        if not result_image_paths:
            print("ERROR: no images found for {}".format(region_city))
            continue

        values = calculate_area_all_years(years, result_image_paths)

        base_output_dir = os.path.join(args.output_dir, region_city)
        os.makedirs(base_output_dir, exist_ok=True)

        hist_output_path = os.path.join(base_output_dir, 'hist.png')
        plot_histogram(values, name=name, output=hist_output_path, years=years)
        print("{} written".format(hist_output_path))

        print(glob(os.path.join(args.images_dir, region_city, '*')))
        original_image_paths = [
            glob(os.path.join(args.images_dir, region_city, '{year}.vrt'.format(year=year)))[0]
            for year in years
        ]

        for year, image_path in zip(years, result_image_paths):
            output_path = os.path.join(base_output_dir,
                                       '{year}_map.png').format(year=year)
            plot_image(image_path, name=name, output=output_path)
            print("{} written".format(output_path))

        for year, image_path in zip(years, original_image_paths):
            output_path = os.path.join(base_output_dir,
                                       '{year}_image.png').format(year=year)
            band_percentiles = get_precalc_percentiles(region_city, year)
            plot_rgb_image(image_path, name=name, output=output_path, band_percentiles=band_percentiles)
            print("{} written".format(output_path))

        print()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Make plots for all cities',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--results-dir',
                        default=os.path.join('data', 'resultados', 'finales'),
                        help='path to results dir')
    parser.add_argument('--images-dir',
                        default=os.path.join('data', 'imagenes'),
                        help='path to original images dir')
    parser.add_argument(
        '-o',
        '--output-dir',
        required=True,
        help='path to directory containing plots for each region-city')
    parser.add_argument('--result-image-path',
                        default='_mean/image_mean5.tif',
                        help='path to raster image inside "year" directory')

    args = parser.parse_args()

    main(args)
