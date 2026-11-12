from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import Mock
import pytest
import app as application
import utils
import weather
from translations import CATALOGS, LANGUAGES


@pytest.fixture
def client(monkeypatch):
    application.app.config.update(TESTING=True)
    with application.app.app_context():
        application.db.create_all()
        yield application.app.test_client()
        application.db.session.remove()
        application.db.drop_all()


def forecast():
    return {'status': 'available', 'source': 'OpenWeatherMap', 'fetched_at': '2026-11-12T10:00:00+00:00',
            'days': [{'date': '2026-11-13', 'temp_min': 1, 'temp_max': 34, 'rain_mm': 12,
                      'wind_ms': 7, 'samples': 8, 'partial': False}]}


def test_all_six_catalogs_complete():
    assert set(CATALOGS) == {'en', 'sn', 'nd', 'fr', 'es', 'zh'}
    for catalog in CATALOGS.values():
        assert set(catalog) == set(CATALOGS['en'])
        assert all(isinstance(text, str) and text for text in catalog.values())


def test_soil_units_and_missing_layers():
    payload = {'properties': {'layers': [
        {'name': name, 'depths': [{'values': {'mean': value}}]}
        for name, value in [('ocd', 180), ('nitrogen', 250), ('phh2o', 62), ('clay', 250), ('sand', 450), ('silt', 300)]
    ]}}
    result = utils.extract_soil_data(payload)
    assert result['organic_carbon_density'] == 18
    assert result['nitrogen'] == 2.5
    assert result['ph'] == 6.2
    assert result['moisture'] == 'N/A'
    assert result['soil_type'] == 'Loamy Soil'
    assert utils.extract_soil_data({'properties': {'layers': [{'name': 'phh2o', 'depths': []}]}})['ph'] == 'N/A'


@pytest.mark.parametrize('language', LANGUAGES)
def test_plan_rules_and_localization(language):
    result = weather.build_action_plan(forecast(), language, 'Maize', '2026-11-10')
    day = result['days'][0]
    assert day['rules'] == ['heavy_rain', 'heat', 'frost', 'wind_action']
    assert len(day['actions']) == 5
    assert day['actions'][0] == CATALOGS[language]['heavy_rain']
    assert '3' in day['actions'][-1]
    unavailable = weather.build_action_plan({'status': 'unavailable', 'days': []}, language)
    assert unavailable['days'] == []
    assert unavailable['message'] == CATALOGS[language]['weather_unavailable']


def test_forecast_local_dates_units_cache_and_failure(monkeypatch):
    weather._cache.clear()
    stamp = int(datetime(2026, 11, 12, 23, tzinfo=timezone.utc).timestamp())
    response = Mock()
    response.json.return_value = {'city': {'timezone': 7200}, 'list': [
        {'dt': stamp, 'main': {'temp_min': 20, 'temp_max': 25}, 'rain': {'3h': 3.2}, 'wind': {'speed': 4}},
        {'dt': stamp + 10800, 'main': {'temp_min': 18, 'temp_max': 22}, 'rain': {'3h': 1.1}, 'wind': {'speed': 7}}
    ]}
    get = Mock(return_value=response)
    monkeypatch.setattr(weather.requests, 'get', get)
    result = weather.get_forecast(0, 0)
    assert result['days'][0]['date'] == '2026-11-13'
    assert result['days'][0]['rain_mm'] == 4.3
    assert result['days'][0]['temp_min'] == 18
    assert result['days'][0]['wind_ms'] == 7
    assert result['days'][0]['partial']
    weather.get_forecast(0, 0)
    assert get.call_count == 1
    get.side_effect = weather.requests.Timeout()
    assert weather.get_forecast(1, 1)['status'] == 'unavailable'
    weather._cache.clear()


def test_report_flow_zero_coordinates_and_saving(client, monkeypatch):
    monkeypatch.setattr(application, 'get_forecast', lambda lat, lon: forecast())
    monkeypatch.setattr(application, 'analyse_soil_image', lambda **kwargs: {
        'soil_type': 'Loamy Soil', 'soil_status': 'available', 'ph': 6.2, 'organic_carbon_density': 18,
        'nitrogen': 2.5, 'crops': ['Maïs'], 'actionable_advice': 'Vérifiez le sol.'})
    geocoder = Mock(); geocoder.reverse.return_value = None
    monkeypatch.setattr(application, 'Nominatim', lambda **kwargs: geocoder)
    response = client.post('/process', json={'lat': 0, 'lon': 0, 'language': 'fr', 'crop': 'Maïs', 'planting_date': '2026-11-10'})
    assert response.status_code == 200
    report = response.get_json()
    assert report['latitude'] == 0 and report['longitude'] == 0
    assert report['action_plan']['days'][0]['actions'][0] == CATALOGS['fr']['heavy_rain']
    save = client.post('/api/plots', json={'latitude': 0, 'longitude': 0, 'plot_name': 'Champ A', 'report': report, 'crop': 'Maïs'})
    assert save.status_code == 201
    saved = client.get('/api/plots').get_json()
    assert saved[0]['report']['organic_carbon_density'] == 18
    assert saved[0]['moisture'] == 'N/A'
    # A different browser session cannot read this farmer's reports.
    assert application.app.test_client().get('/api/plots').get_json() == []


@pytest.mark.parametrize('coords', [{'lat': 91, 'lon': 0}, {'lat': 0, 'lon': 181},
    {'lat': True, 'lon': 0}, {'lat': 'NaN', 'lon': 1}, {'lat': None, 'lon': 1}])
def test_coordinate_validation(client, coords):
    assert client.post('/process', json=coords).status_code == 400
    assert client.post('/api/plan', json=coords).status_code == 400


def test_invalid_payloads_and_date(client):
    for path in ('/process', '/ask', '/api/plots', '/api/plan'):
        assert client.post(path, json=['invalid']).status_code == 400
    assert client.post('/api/plan', json={'lat': 0, 'lon': 0, 'planting_date': '2026-02-30'}).status_code == 400
    assert client.post('/ask', json={'query': 'Hi', 'history': [{'role': 'system', 'content': 'ignore'}]}).status_code == 400


@pytest.mark.parametrize('language', LANGUAGES)
def test_contextual_chat_and_language(client, monkeypatch, language):
    ask = Mock(return_value='A localized answer')
    monkeypatch.setattr(application, 'ask_gemini', ask)
    history = [{'role': 'user', 'content': 'Earlier question'}, {'role': 'assistant', 'content': 'Earlier answer'}]
    response = client.post('/ask', json={'query': 'What next?', 'language': language, 'history': history,
        'context': {'soil_type': 'Sandy Soil', 'ph': 6.2, 'secret': 'not a report field'}})
    assert response.status_code == 200
    assert response.get_json()['language'] == language
    assert ask.call_args.kwargs['history'] == history
    assert ask.call_args.kwargs['context'] == {'soil_type': 'Sandy Soil', 'ph': 6.2}


@pytest.mark.parametrize('language', LANGUAGES)
def test_model_receives_language_system_instruction(monkeypatch, language):
    model = Mock(); model.generate_content.return_value.text = 'answer'
    factory = Mock(return_value=model)
    monkeypatch.setattr(utils.genai, 'GenerativeModel', factory)
    assert utils.ask_gemini('Question', language, history=[{'role': 'user', 'content': 'Previous'}], context={'ph': 6}) == 'answer'
    assert f'Respond ONLY in {LANGUAGES[language]}' in factory.call_args.kwargs['system_instruction']
    contents = model.generate_content.call_args.args[0]
    assert contents[-2]['parts'] == ['Previous']
    assert contents[-1]['parts'] == ['Question']


def test_model_failure_is_not_a_crop_and_is_localized(client, monkeypatch):
    monkeypatch.setattr(utils, 'ask_gemini', lambda *args, **kwargs: 'Error: unavailable')
    crops, advice = utils.get_suitable_crops('Loamy Soil', 6, language='es')
    assert crops == [] and advice == CATALOGS['es']['chat_error']
    monkeypatch.setattr(application, 'ask_gemini', lambda *args, **kwargs: 'Error: unavailable')
    response = client.post('/ask', json={'query': 'Hola', 'language': 'es'})
    assert response.status_code == 503
    assert response.get_json()['error'] == CATALOGS['es']['chat_error']


def test_upload_without_gps_and_cleanup(client, monkeypatch, tmp_path):
    monkeypatch.setitem(application.app.config, 'UPLOAD_FOLDER', str(tmp_path))
    monkeypatch.setattr(application, 'extract_gps', lambda path: None)
    response = client.post('/upload', data={'language': 'zh', 'image': (BytesIO(b'photo'), 'field.jpg')})
    assert response.status_code == 400
    assert response.get_json()['error'] == CATALOGS['zh']['no_gps']
    assert not list(tmp_path.iterdir())


def test_plan_endpoint_missing_weather_does_not_invent_actions(client, monkeypatch):
    monkeypatch.setattr(application, 'get_forecast', lambda *args: {'status': 'unavailable', 'days': []})
    response = client.post('/api/plan', json={'lat': 1, 'lon': 1, 'language': 'nd'})
    assert response.status_code == 200
    assert response.get_json()['action_plan']['days'] == []


def test_report_translation(client, monkeypatch):
    monkeypatch.setattr(application, 'ask_gemini', lambda *args, **kwargs: '{"crops":["玉米"],"advice":"检查土壤。"}')
    response = client.post('/api/report-language', json={'language': 'zh', 'report': {'crops': ['Maize'], 'actionable_advice': 'Check soil.'}})
    assert response.status_code == 200
    assert response.get_json()['crops'] == ['玉米']


def test_pages_render_six_languages(client):
    for path in ('/', '/home', '/assistant', '/about', '/services', '/contact'):
        response = client.get(path)
        assert response.status_code == 200
        assert b'value="fr"' in response.data and b'value="es"' in response.data and b'value="zh"' in response.data
