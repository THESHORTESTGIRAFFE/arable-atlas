from io import BytesIO
import json
from unittest.mock import MagicMock, Mock

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

import app as application
import soil_provider as soil
import utils


def tiff(value=62, nodata=-32768):
    """Small correctly georeferenced native-grid raster containing (lat=0, lon=0)."""
    x, y = soil.project_point(0, 0)
    with MemoryFile() as memory:
        with memory.open(driver='GTiff', count=1, height=2, width=2, dtype='int16',
            crs=soil.NATIVE_CRS, transform=from_origin(x - 125, y + 125, 250, 250), nodata=nodata) as dataset:
            dataset.write(np.full((2, 2), value, dtype='int16'), 1)
        return memory.read()


def response(content):
    result = MagicMock()
    result.__enter__.return_value = result
    result.iter_content.return_value = [content]
    return result


def test_wcs_request_sampling_persistent_cache_and_offline(monkeypatch, tmp_path):
    values = {'phh2o': 62, 'ocd': 180, 'nitrogen': 250, 'clay': 250, 'sand': 450, 'silt': 300}
    def get(url, params, **kwargs):
        assert url == 'https://maps.isric.org/mapserv'
        assert ('REQUEST', 'GetCoverage') in params
        assert ('SUBSETTINGCRS', soil.NATIVE_CRS_URL) in params
        coverage = dict(params)['COVERAGEID']
        assert coverage.endswith('_0-5cm_mean')
        assert len([key for key, _ in params if key == 'SUBSET']) == 2
        return response(tiff(values[coverage.split('_')[0]]))
    provider = Mock(side_effect=get)
    monkeypatch.setattr(soil.requests, 'get', provider)
    first = soil.fetch_soil_data(0, 0, cache_dir=tmp_path)
    assert first['soil_access'] == 'wcs'
    assert provider.call_count == 6
    converted = utils.extract_soil_data(first)
    assert converted['ph'] == 6.2
    assert converted['organic_carbon_density'] == 18
    assert converted['nitrogen'] == 2.5
    assert len(list(tmp_path.glob('*.tif'))) == 6
    provider.side_effect = AssertionError('Offline cache must not contact the network')
    second = soil.fetch_soil_data(0, 0, cache_dir=tmp_path, offline=True)
    assert second['properties'] == first['properties']
    assert second['soil_fetched_at'] == first['soil_fetched_at']
    assert second['soil_access'] == 'cache'
    assert provider.call_count == 6
    # A nearby but uncovered location must not borrow this pixel's values.
    outside = soil.fetch_soil_data(10, 10, cache_dir=tmp_path, offline=True)
    assert outside['properties']['layers'] == []


def test_wcs_xml_errors_and_oversized_response_not_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(soil.requests, 'get', lambda *args, **kwargs: response(b'<ExceptionReport>Unavailable</ExceptionReport>'))
    result = soil.fetch_soil_data(0, 0, tmp_path)
    assert result['properties']['layers'] == []
    assert result['soil_access'] == 'unavailable'
    assert not list(tmp_path.glob('*.tif'))
    monkeypatch.setattr(soil, 'MAX_BYTES', 10)
    monkeypatch.setattr(soil.requests, 'get', lambda *args, **kwargs: response(tiff()))
    assert soil.fetch_soil_data(0, 0, tmp_path)['properties']['layers'] == []


@pytest.mark.parametrize('value,nodata', [(-32768, -32768), (0, None)])
def test_nodata_and_unmarked_zero_background_never_become_readings(monkeypatch, tmp_path, value, nodata):
    monkeypatch.setattr(soil.requests, 'get', lambda *args, **kwargs: response(tiff(value, nodata)))
    result = soil.fetch_soil_data(0, 0, tmp_path)
    assert result['properties']['layers'] == []
    assert set(result['missing_properties']) == set(soil.PROPERTIES)


def test_a_legitimate_individual_zero_is_retained(monkeypatch, tmp_path):
    def get(*args, params, **kwargs):
        return response(tiff(62 if dict(params)['COVERAGEID'].startswith('phh2o') else 0))
    monkeypatch.setattr(soil.requests, 'get', get)
    result = utils.extract_soil_data(soil.fetch_soil_data(0, 0, tmp_path))
    assert result['ph'] == 6.2
    assert result['nitrogen'] == 0


def test_corrupt_cache_is_ignored(monkeypatch, tmp_path):
    (tmp_path / 'phh2o_0-5cm_mean_bad.json').write_text('[]')
    monkeypatch.setattr(soil.requests, 'get', lambda *args, **kwargs: response(tiff()))
    result = soil.fetch_soil_data(0, 0, tmp_path)
    assert len(result['properties']['layers']) == 6


def test_prefetch_partial_failure_and_radius_limits(monkeypatch, tmp_path):
    def get(*args, params, **kwargs):
        return response(b'<Exception/>' if dict(params)['COVERAGEID'].startswith('ocd') else tiff())
    monkeypatch.setattr(soil.requests, 'get', get)
    result = soil.prefetch_region(0, 0, 1, tmp_path)
    assert result['properties']['phh2o']['status'] == 'downloaded'
    assert result['properties']['ocd']['status'] == 'unavailable'
    assert result['depth'] == '0-5cm' and result['resolution_m'] == 250
    assert all(value % 250 == 0 for value in result['bounds_native_m'])
    for radius in (0, 51, float('nan')):
        with pytest.raises(ValueError):
            soil.prefetch_region(0, 0, radius, tmp_path)


@pytest.mark.parametrize('lat,lon', [(91, 0), (0, 181), (True, 0), (float('nan'), 0)])
def test_provider_rejects_invalid_coordinates(lat, lon, tmp_path):
    with pytest.raises(ValueError):
        soil.fetch_soil_data(lat, lon, tmp_path)


@pytest.fixture
def client(monkeypatch):
    application.app.config.update(TESTING=True)
    with application.app.app_context():
        application.db.create_all()
        yield application.app.test_client()
        application.db.session.remove()
        application.db.drop_all()


def test_manual_soil_bypasses_wcs_and_preserves_depth_in_saved_report(client, monkeypatch):
    provider = Mock(side_effect=AssertionError('Manual soil must bypass WCS'))
    monkeypatch.setattr(utils, 'fetch_soil_data', provider)
    recommendations = Mock(return_value=(['Maize'], 'Check local planting guidance.'))
    monkeypatch.setattr(utils, 'get_suitable_crops', recommendations)
    monkeypatch.setattr(application, 'get_forecast', lambda *args: {'status': 'unavailable', 'days': []})
    geocoder = Mock(); geocoder.reverse.return_value = None
    monkeypatch.setattr(application, 'Nominatim', lambda **kwargs: geocoder)
    test = {'ph': 6.2, 'nitrogen': 2.5, 'clay': 25, 'sand': 45, 'silt': 30,
            'depth_top_cm': 10, 'depth_bottom_cm': 30, 'sample_date': '2026-01-01'}
    result = client.post('/process', json={'lat': 0, 'lon': 0, 'manual_soil': test, 'language': 'fr'})
    assert result.status_code == 200
    report = result.get_json()
    assert report['soil_method'] == 'manual' and report['soil_status'] == 'available'
    assert report['depth'] == '10-30cm' and report['resolution_m'] is None
    assert report['organic_carbon_density'] == 'N/A'
    assert report['nitrogen'] == 2.5  # Already conventional units, never scale twice.
    assert report['soil_type'] == 'Loamy Soil'
    assert not provider.called
    assert recommendations.call_args.kwargs['soil_context']['soil_method'] == 'manual'
    assert client.post('/api/plots', json={'lat': 0, 'lon': 0, 'plot_name': 'Test field', 'report': report}).status_code == 201
    restored = client.get('/api/plots').get_json()[0]['report']
    assert restored['depth'] == '10-30cm' and restored['sample_date'] == '2026-01-01'
    assert restored['soil_source'] == 'User-entered soil test'


@pytest.mark.parametrize('changes', [
    {'ph': ''}, {'ph': 15}, {'ph': 'NaN'}, {'ph': True}, {'depth_top_cm': 20, 'depth_bottom_cm': 10},
    {'clay': 20}, {'clay': 20, 'sand': 20, 'silt': 20}, {'nitrogen': -1},
    {'sample_date': '2099-01-01'}, {'sample_date': []}, {'sample_date': '2026-02-30'},
])
def test_invalid_manual_values_are_rejected_before_network_calls(client, monkeypatch, changes):
    network = Mock(side_effect=AssertionError('Validation must happen before network calls'))
    monkeypatch.setattr(application, 'get_forecast', network)
    data = {'ph': 6.2, 'depth_top_cm': 0, 'depth_bottom_cm': 20, **changes}
    assert client.post('/process', json={'lat': 0, 'lon': 0, 'manual_soil': data}).status_code == 400
    assert not network.called
