from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import pytest
import app as application
import ussd_demo as ussd
from models import db, DemoSms, UssdDemoSession
from translations import LANGUAGES, translate


@pytest.fixture
def client(monkeypatch):
    application.app.config['TESTING'] = True
    monkeypatch.setattr(ussd, 'submit_job', Mock())
    with application.app.app_context():
        db.create_all()
        yield application.app.test_client()
        db.session.remove()
        db.drop_all()


def reply(client, call, text, status=200):
    response = client.post('/api/ussd/session', json={'action': 'reply', 'session_id': call['session_id'],
        'revision': call['revision'], 'text': text})
    assert response.status_code == status
    return response.get_json()


def dial(client, language='en'):
    response = client.post('/api/ussd/session', json={'action': 'dial', 'language': language})
    assert response.status_code == 200
    return response.get_json()


def queue_weather(client, language='en'):
    call = dial(client, language)
    call = reply(client, call, '1')
    assert call['stage'] == 'area'
    call = reply(client, call, '1')
    assert call['protocol'].startswith('END ') and not call['active']
    return call


def test_segment_boundaries_and_encoding():
    assert ussd.sms_metrics('a' * 160)['segments'] == 1
    assert ussd.sms_metrics('a' * 161)['segments'] == 2
    assert ussd.sms_metrics('a' * 307)['segments'] == 3
    assert ussd.sms_metrics('^' * 80)['units'] == 160
    assert ussd.sms_metrics('^' * 81)['segments'] == 2
    assert ussd.sms_metrics('中' * 70)['segments'] == 1
    assert ussd.sms_metrics('中' * 71)['segments'] == 2
    assert ussd.sms_metrics('中' * 135)['segments'] == 3
    assert ussd.sms_metrics('🌱')['units'] == 2
    assert ussd.sms_metrics('Plain punctuation.')['encoding'] == 'GSM-7'


def test_concise_sms_keeps_whole_sentences():
    assert ussd.concise_sms('Check soil moisture. ' + 'x' * 400, 'Fallback.') == 'Check soil moisture.'
    assert ussd.concise_sms('x' * 500, 'Fallback.') == 'Fallback.'
    assert ussd.concise_sms('It’s dry—check soil.', 'Fallback.') == "It's dry-check soil."


@pytest.mark.parametrize('language', LANGUAGES)
def test_language_menu_and_short_sms_templates(client, language):
    call = dial(client, language)
    assert call['protocol'].startswith('CON ')
    assert translate('ussd_menu', language) in call['text']
    for key in ('sms_fallback', 'sms_weather_missing', 'sms_ai_missing', 'sms_soil_missing'):
        assert ussd.sms_metrics(translate(key, language))['segments'] <= 2
    for key in ('sms_weather', 'sms_soil'):
        body = translate(key, language, area='Harare outskirts', date='2026-11-12', low=18.2, high=32.1, rain=5.1, ph=5.9, nitrogen=1.21)
        assert ussd.sms_metrics(ussd.concise_sms(body, translate('sms_fallback', language)))['segments'] <= 2


def test_menu_returns_before_providers_and_queues_once(client, monkeypatch):
    network = Mock(side_effect=AssertionError('USSD callback must not wait for providers'))
    monkeypatch.setattr(ussd, 'get_forecast', network)
    monkeypatch.setattr(ussd, 'ask_gemini', network)
    call = queue_weather(client)
    assert DemoSms.query.count() == 1 and not network.called
    # Retrying the final callback cannot create or send another message.
    reply(client, call, '1')
    assert DemoSms.query.count() == 1
    assert ussd.submit_job.call_count == 1
    inbox = client.get('/api/ussd/inbox').get_json()
    assert inbox[0]['status'] == 'queued' and inbox[0]['simulated'] is True
    assert application.app.test_client().get('/api/ussd/inbox').get_json() == []


def test_worker_weather_no_ai_and_no_fictional_weather(client, monkeypatch):
    call = queue_weather(client)
    ai = Mock(side_effect=AssertionError('Weather summary should not call AI'))
    monkeypatch.setattr(ussd, 'ask_gemini', ai)
    monkeypatch.setattr(ussd, 'get_forecast', lambda *args: {'status': 'unavailable', 'days': []})
    ussd._work(application.app, call['message_id'])
    inbox = client.get('/api/ussd/inbox').get_json()
    assert inbox[0]['status'] == 'simulated'
    assert inbox[0]['body'] == translate('sms_weather_missing')
    assert not ai.called


def test_ai_question_uses_cached_soil_and_selected_language(client, monkeypatch):
    call = dial(client, 'es')
    call = reply(client, call, '3')
    call = reply(client, call, '1')
    assert call['stage'] == 'question'
    call = reply(client, call, '¿Cuándo regar?')
    soil = Mock(return_value={'properties': {'layers': []}})
    ai = Mock(return_value='Comprueba la humedad antes de regar.')
    monkeypatch.setattr(ussd, 'fetch_soil_data', soil)
    monkeypatch.setattr(ussd, 'ask_gemini', ai)
    ussd._work(application.app, call['message_id'])
    result = client.get('/api/ussd/inbox').get_json()[0]
    assert result['status'] == 'simulated' and result['segments'] <= 2
    assert ai.call_args.args[1] == 'es'
    assert soil.call_args.kwargs['offline'] is True


def test_invalid_choice_stale_revision_foreign_session_and_timeout(client):
    call = dial(client)
    invalid = reply(client, call, '9', status=400)
    assert invalid['revision'] == call['revision']
    next_call = reply(client, call, '5')
    assert next_call['stage'] == 'language'
    reply(client, call, '1', status=409)
    next_call = reply(client, next_call, '2')
    assert next_call['language'] == 'sn'
    stranger = application.app.test_client()
    reply(stranger, next_call, '1', status=404)
    record = db.session.get(UssdDemoSession, next_call['session_id'])
    record.updated_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=4)
    db.session.commit()
    assert reply(client, next_call, '1')['stage'] == 'cancelled'
    assert DemoSms.query.count() == 0


def test_malformed_requests(client):
    for data in ([], {}, {'action': 'invalid'}, {'action': 'reply', 'session_id': []}):
        assert client.post('/api/ussd/session', json=data).status_code == 400


def test_demo_and_contact_pages_render(client):
    response = client.get('/ussd')
    assert response.status_code == 200
    assert b'No real messages sent' in response.data
    response = client.get('/contact')
    assert response.status_code == 200
    assert b'mailto:hi@emmorphic.co.zw' in response.data
