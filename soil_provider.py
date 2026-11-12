"""SoilGrids WCS rasters, persistent local subsets, and native-grid point sampling.

No REST API calls, generated soil values, or interpolation across missing pixels.
Downloaded maps are static model estimates, not current field observations.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
from threading import Lock

import numpy as np
from pyproj import CRS, Transformer
import rasterio
from rasterio.io import MemoryFile
from rasterio.errors import RasterioError
import requests

from config import Config

PROPERTIES = ('phh2o', 'ocd', 'nitrogen', 'clay', 'sand', 'silt')
DEPTH = '0-5cm'
STATISTIC = 'mean'
RESOLUTION = 250
# SoilGrids' custom EPSG:152160 is Interrupted Goode Homolosine on WGS84.
# It is not in the normal EPSG registry; the PROJ definition is used locally.
NATIVE_CRS = CRS.from_proj4('+proj=igh +datum=WGS84 +units=m +no_defs')
NATIVE_CRS_URL = 'http://www.opengis.net/def/crs/EPSG/0/152160'
_project = Transformer.from_crs('EPSG:4326', NATIVE_CRS, always_xy=True)
_download_lock = Lock()
MAX_BYTES = 8 * 1024 * 1024


def project_point(lat, lon):
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError('Invalid coordinates')
    lat, lon = float(lat), float(lon)
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Invalid coordinates')
    x, y = _project.transform(lon, lat, errcheck=True)
    return x, y


def _directory(cache_dir=None):
    return Path(cache_dir if cache_dir is not None else Config.SOIL_CACHE_DIR)


def _sample(dataset, lat, lon):
    if not dataset.crs or dataset.count != 1:
        raise ValueError('Missing raster georeferencing')
    # Use the returned raster's own CRS and transform, not an assumed row/column.
    x, y = Transformer.from_crs('EPSG:4326', dataset.crs, always_xy=True).transform(lon, lat)
    row, col = dataset.index(x, y)
    if row < 0 or col < 0 or row >= dataset.height or col >= dataset.width:
        return False, None
    value = dataset.read(1, window=((row, row + 1), (col, col + 1)), masked=True)[0, 0]
    if np.ma.is_masked(value) or not np.isfinite(value) or value < 0:
        return True, None
    return True, float(value)


def _cached(property_name, lat, lon, cache_dir=None):
    directory = _directory(cache_dir)
    for metadata_path in sorted(directory.glob(f'{property_name}_{DEPTH}_{STATISTIC}_*.json')):
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            if not isinstance(metadata, dict) or metadata.get('coverage') != f'{property_name}_{DEPTH}_{STATISTIC}' or not isinstance(metadata.get('fetched_at'), str):
                continue
            with rasterio.open(metadata_path.with_suffix('.tif')) as dataset:
                covered, value = _sample(dataset, lat, lon)
            if covered:
                return True, value, metadata
        except (OSError, ValueError, TypeError, RasterioError):
            # Interrupted/corrupt downloads must never prevent a new lookup.
            continue
    return False, None, None


def _download(property_name, bounds, cache_dir=None, refresh=False):
    if property_name not in PROPERTIES:
        raise ValueError('Unknown soil property')
    directory = _directory(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    left, bottom, right, top = bounds
    identifier = '_'.join(str(int(v)) for v in bounds)
    stem = f'{property_name}_{DEPTH}_{STATISTIC}_{identifier}'
    raster_path, metadata_path = directory / f'{stem}.tif', directory / f'{stem}.json'
    if not refresh and raster_path.exists() and metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            with rasterio.open(raster_path) as dataset:
                if dataset.count == 1 and dataset.crs and isinstance(metadata, dict) and metadata.get('coverage') == f'{property_name}_{DEPTH}_{STATISTIC}' and isinstance(metadata.get('fetched_at'), str):
                    return metadata
        except (OSError, ValueError, RasterioError):
            pass
    params = [
        ('map', f'/map/{property_name}.map'), ('SERVICE', 'WCS'), ('VERSION', '2.0.1'),
        ('REQUEST', 'GetCoverage'), ('COVERAGEID', f'{property_name}_{DEPTH}_{STATISTIC}'),
        ('FORMAT', 'image/tiff'), ('SUBSETTINGCRS', NATIVE_CRS_URL), ('OUTPUTCRS', NATIVE_CRS_URL),
        ('SUBSET', f'X({left},{right})'), ('SUBSET', f'Y({bottom},{top})'),
    ]
    # Bound downloads even if an upstream server ignores the requested subset.
    with requests.get(Config.SOILGRIDS_WCS_URL, params=params, timeout=(5, 20), stream=True) as response:
        response.raise_for_status()
        chunks, length = [], 0
        for chunk in response.iter_content(65536):
            length += len(chunk)
            if length > MAX_BYTES:
                raise ValueError('WCS response too large')
            chunks.append(chunk)
    content = b''.join(chunks)
    # A WCS server can return an XML exception with HTTP 200. Only accept a valid TIFF.
    if content[:4] not in (b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+'):
        raise ValueError('WCS did not return a GeoTIFF')
    with MemoryFile(content) as memory, memory.open() as dataset:
        if not dataset.crs or dataset.count != 1 or dataset.width * dataset.height > 1_000_000:
            raise ValueError('Unexpected WCS raster')
        if any(abs(abs(size) - RESOLUTION) > 0.1 for size in dataset.res):
            raise ValueError('Unexpected WCS resolution')
        actual_bounds = list(dataset.bounds)
    metadata = {'coverage': f'{property_name}_{DEPTH}_{STATISTIC}', 'depth': DEPTH,
        'statistic': STATISTIC, 'resolution_m': RESOLUTION, 'bounds': actual_bounds,
        'fetched_at': datetime.now(timezone.utc).isoformat(), 'source': 'ISRIC SoilGrids WCS',
        'license': 'CC BY 4.0', 'source_url': Config.SOILGRIDS_WCS_URL}
    # Replace whole files atomically; readers never see a half-written TIFF or manifest.
    for destination, payload in ((raster_path, content), (metadata_path, json.dumps(metadata).encode('utf-8'))):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
                temporary = stream.name
                stream.write(payload)
            os.replace(temporary, destination)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    return metadata


def _property(property_name, lat, lon, bounds, cache_dir, offline):
    found, value, metadata = _cached(property_name, lat, lon, cache_dir)
    access = 'cache'
    if not found and not offline:
        try:
            _download(property_name, bounds, cache_dir)
            found, value, metadata = _cached(property_name, lat, lon, cache_dir)
            access = 'wcs'
        except (requests.RequestException, OSError, ValueError, RasterioError):
            return property_name, None, None, 'unavailable'
    return property_name, value, metadata, access if found else 'unavailable'


def fetch_soil_data(lat, lon, cache_dir=None, offline=None):
    """Return raw SoilGrids units in a REST-compatible envelope plus provenance."""
    x, y = project_point(lat, lon)
    lat, lon = float(lat), float(lon)
    # Reuse a 10 km map section for nearby clicks; retain native 250 m cells.
    left, bottom = math.floor(x / 10000) * 10000, math.floor(y / 10000) * 10000
    bounds = left, bottom, left + 10000, bottom + 10000
    offline = Config.SOIL_OFFLINE if offline is None else offline
    # Serialize lookup groups to avoid duplicate downloads from simultaneous users.
    with _download_lock, ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda p: _property(p, lat, lon, bounds, cache_dir, offline), PROPERTIES))
    # MapServer's TIFF output can omit nodata metadata and use a zero-filled
    # background for masked urban/water pixels. A fully zero soil profile is
    # not a measurement. Preserve legitimate individual zeros in valid profiles.
    if all(value in (None, 0) for _, value, _, _ in rows):
        rows = [(p, None, metadata, method) for p, _, metadata, method in rows]
    else:
        rows = [(p, None if p == 'phh2o' and value == 0 else value, metadata, method)
                for p, value, metadata, method in rows]
    layers, sources, access = [], {}, set()
    for property_name, value, metadata, method in rows:
        if value is not None:
            layers.append({'name': property_name, 'depths': [{'label': DEPTH, 'values': {'mean': value}}]})
        if metadata:
            sources[property_name] = metadata['fetched_at']
        if method != 'unavailable':
            access.add(method)
    return {'properties': {'layers': layers}, 'soil_access': 'wcs' if 'wcs' in access else 'cache' if access else 'unavailable',
        'soil_fetched_at': sources, 'missing_properties': [p for p, value, _, _ in rows if value is None]}


def prefetch_region(lat, lon, radius_km=10, cache_dir=None, refresh=False):
    """Download one native projected square per property, centered near a demo location."""
    if not math.isfinite(radius_km) or not 0.25 <= radius_km <= 50:
        raise ValueError('Radius must be between 0.25 and 50 km')
    x, y = project_point(lat, lon)
    radius = radius_km * 1000
    bounds = (math.floor((x - radius) / 250) * 250, math.floor((y - radius) / 250) * 250,
              math.ceil((x + radius) / 250) * 250, math.ceil((y + radius) / 250) * 250)
    results = {}
    for property_name in PROPERTIES:
        try:
            metadata = _download(property_name, bounds, cache_dir, refresh=refresh)
            results[property_name] = {'status': 'downloaded', 'fetched_at': metadata['fetched_at']}
        except (requests.RequestException, OSError, ValueError, RasterioError):
            results[property_name] = {'status': 'unavailable'}
    return {'center': {'latitude': float(lat), 'longitude': float(lon)}, 'radius_km': radius_km,
            'bounds_native_m': bounds, 'depth': DEPTH, 'resolution_m': RESOLUTION, 'properties': results}
