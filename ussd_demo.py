"""USSD-style demo with a private, simulated SMS inbox. No telecom transmission.

Menu responses never wait for weather, soil, or AI. A small background worker
prepares the SMS after the session ends. Live carrier callbacks need a separate
authenticated adapter; these cookie-authenticated routes are simulator-only.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import math
import re
import secrets
from threading import Lock

from flask import Blueprint, current_app, jsonify, render_template, request, session
from models import db, UssdDemoSession, DemoSms
from translations import LANGUAGES, normalize_language, translate
from soil_provider import fetch_soil_data
from utils import ask_gemini, extract_soil_data
from weather import get_forecast

demo = Blueprint('ussd_demo', __name__)
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='demo-sms')
_menu_lock = Lock()
AREAS = {
    '1': {'name': 'Harare outskirts', 'lat': -17.9, 'lon': 31.05},
    '2': {'name': 'Bulawayo outskirts', 'lat': -20.10, 'lon': 28.60},
}
LANGUAGE_CHOICES = dict(zip(('1', '2', '3', '4', '5', '6'), LANGUAGES))
GSM_BASIC = set('@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà')
GSM_EXTENDED = set('\f^{}\\[~]|€')


def sms_metrics(text):
    if all(char in GSM_BASIC or char in GSM_EXTENDED for char in text):
        units = sum(2 if char in GSM_EXTENDED else 1 for char in text)
        return {'encoding': 'GSM-7', 'units': units, 'segments': 1 if units <= 160 else math.ceil(units / 153)}
    units = len(text.encode('utf-16-le')) // 2
    return {'encoding': 'Unicode', 'units': units, 'segments': 1 if units <= 70 else math.ceil(units / 67)}


def concise_sms(text, fallback, max_segments=2):
    # Plain punctuation avoids unintended Unicode conversion; preserve actual languages.
    text = text.translate(str.maketrans({'“': '"', '”': '"', '’': "'", '‘': "'", '—': '-', '–': '-', '\u00a0': ' '}))
    text = re.sub(r'\s+', ' ', text).strip()
    if sms_metrics(text)['segments'] <= max_segments:
        return text
    # Never cut a safety instruction or a negation halfway through a sentence.
    sentences = re.findall(r'.+?(?:[.!?。！？](?=\s|$)|[。！？]|$)', text)
    result = ''
    for sentence in sentences:
        candidate = (result + ' ' + sentence).strip()
        if sms_metrics(candidate)['segments'] > max_segments:
            break
        result = candidate
    return result or fallback


def _owner():
    if 'farm_owner' not in session:
        session['farm_owner'] = secrets.token_hex(24)
    return session['farm_owner']


def _screen(record):
    lang = record.language
    if record.stage == 'ended':
        text = translate('ussd_sent', lang)
    elif record.stage == 'cancelled':
        text = translate('ussd_cancelled', lang)
    elif record.stage == 'area':
        text = translate('ussd_area', lang) + '\n' + '\n'.join(f'{key}. {area["name"]}' for key, area in AREAS.items())
    elif record.stage == 'question':
        text = translate('ussd_question', lang)
    elif record.stage == 'language':
        text = 'Plotty\n' + '\n'.join(f'{number}. {LANGUAGES[language]}' for number, language in LANGUAGE_CHOICES.items())
    else:
        name = AREAS[record.area]['name'] if record.area else translate('ussd_no_area', lang)
        text = f'Plotty - {name}\n' + translate('ussd_menu', lang)
    return {'session_id': record.id, 'revision': record.revision, 'stage': record.stage,
            'language': lang, 'active': record.stage not in ('ended', 'cancelled'), 'text': text,
            'protocol': ('END ' if record.stage in ('ended', 'cancelled') else 'CON ') + text,
            'simulated': True}


def _prepare_sms(message):
    lang = message.language
    area = AREAS[message.area]
    fallback = translate('sms_fallback', lang)
    if message.topic == 'weather':
        forecast = get_forecast(area['lat'], area['lon'])
        if forecast['status'] != 'available':
            return translate('sms_weather_missing', lang), 'OpenWeatherMap unavailable'
        day = forecast['days'][0]
        body = translate('sms_weather', lang, area=area['name'], date=day['date'],
                         low=day['temp_min'], high=day['temp_max'], rain=day['rain_mm'])
        # First day may be partial: the text labels it a forecast period.
        return concise_sms(body, fallback), 'OpenWeatherMap forecast; ' + forecast['fetched_at']
    raw = fetch_soil_data(area['lat'], area['lon'], offline=True)
    soil = extract_soil_data(raw)
    if message.topic == 'soil':
        if soil['ph'] == 'N/A':
            return translate('sms_soil_missing', lang), 'No cached SoilGrids value'
        body = translate('sms_soil', lang, area=area['name'], ph=soil['ph'], nitrogen=soil['nitrogen'])
        return concise_sms(body, fallback), 'ISRIC SoilGrids cache; 250 m; 0-5cm modeled estimate'
    context = {'location': area['name'], 'latitude': area['lat'], 'longitude': area['lon'], **soil,
               'soil_source': 'ISRIC SoilGrids cache', 'soil_method': 'modeled', 'depth': '0-5cm',
               'soil_fetched_at': raw.get('soil_fetched_at', {})}
    answer = ask_gemini('Answer this farmer in at most two short sentences for an SMS. '
        'Use plain punctuation, no emoji, no greeting. Prioritize one useful action and its limits. '
        'Question: ' + message.question, lang, context=context)
    if not answer.strip() or answer.startswith('Error:'):
        return translate('sms_ai_missing', lang), 'Plotty unavailable'
    return concise_sms('Plotty: ' + answer, fallback), 'Plotty AI; cached soil context; no live weather provided'


def _work(app, message_id):
    with app.app_context():
        try:
            claimed = DemoSms.query.filter_by(id=message_id, status='queued').update({'status': 'processing'})
            db.session.commit()
            if not claimed:
                return
            message = db.session.get(DemoSms, message_id)
            body, source = _prepare_sms(message)
            metrics = sms_metrics(body)
            message.body, message.source = body, source
            message.encoding, message.segments = metrics['encoding'], metrics['segments']
            message.status = 'simulated'
            db.session.commit()
        except Exception:
            db.session.rollback()
            message = db.session.get(DemoSms, message_id)
            if message:
                message.status = 'failed'
                message.body = translate('sms_ai_missing', message.language)
                db.session.commit()
        finally:
            db.session.remove()


def submit_job(app, message_id):
    _pool.submit(_work, app, message_id)


@demo.route('/ussd')
def page():
    return render_template('ussd.html')


@demo.route('/api/ussd/session', methods=['POST'])
def interact():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Invalid request'), 400
    owner = _owner()
    action = data.get('action')
    if action not in ('dial', 'reply', 'cancel'):
        return jsonify(error='Invalid action'), 400
    # Demo-only single-process serialization; production adapters need distributed session handling.
    with _menu_lock:
        if action == 'dial':
            # A new call ends any previous menu for this browser, without sending an SMS.
            UssdDemoSession.query.filter_by(owner_id=owner).filter(UssdDemoSession.stage.notin_(('ended', 'cancelled'))).update({'stage': 'cancelled'})
            record = UssdDemoSession(id=secrets.token_hex(24), owner_id=owner,
                                     language=normalize_language(data.get('language')))
            db.session.add(record)
            db.session.commit()
            return jsonify(_screen(record))
        if not isinstance(data.get('session_id'), str) or not isinstance(data.get('revision'), int) or isinstance(data.get('revision'), bool):
            return jsonify(error='Invalid session'), 400
        record = UssdDemoSession.query.filter_by(id=data.get('session_id'), owner_id=owner).first()
        if not record:
            return jsonify(error='Session not found'), 404
        if record.stage in ('ended', 'cancelled'):
            return jsonify(_screen(record))
        if data.get('revision') != record.revision:
            return jsonify(**_screen(record), error_key='ussd_retry'), 409
        if record.updated_at < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=3):
            record.stage = 'cancelled'
            db.session.commit()
            return jsonify(_screen(record))
        text = data.get('text', '')
        if not isinstance(text, str) or len(text) > 500:
            return jsonify(error='Invalid input'), 400
        text = text.strip()
        if action == 'cancel' or (text == '0' and record.stage != 'question'):
            record.stage = 'cancelled'
        elif record.stage == 'language':
            if text not in LANGUAGE_CHOICES:
                return jsonify(**_screen(record), error_key='ussd_invalid'), 400
            record.language, record.stage = LANGUAGE_CHOICES[text], 'menu'
        elif record.stage == 'area':
            if text not in AREAS:
                return jsonify(**_screen(record), error_key='ussd_invalid'), 400
            record.area = text
            record.stage = 'question' if record.pending_topic == 'question' else 'ended' if record.pending_topic else 'menu'
        elif record.stage == 'question':
            if not text:
                return jsonify(**_screen(record), error_key='ussd_invalid'), 400
            record.stage = 'ended'
        elif text == '5':
            record.stage = 'language'
        elif text == '4':
            record.stage, record.pending_topic = 'area', None
        elif text in ('1', '2', '3'):
            record.pending_topic = {'1': 'weather', '2': 'soil', '3': 'question'}[text]
            record.stage = 'area' if not record.area else 'question' if text == '3' else 'ended'
        else:
            return jsonify(**_screen(record), error_key='ussd_invalid'), 400
        message = None
        if record.stage == 'ended':
            # Cap demo API usage; never generate unlimited paid AI calls from the simulator.
            if DemoSms.query.filter_by(owner_id=owner).filter(DemoSms.created_at > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)).count() >= 10 or DemoSms.query.filter(DemoSms.status.in_(('queued', 'processing'))).count() >= 10:
                db.session.rollback()
                return jsonify(error_key='ussd_limit'), 429
            message = DemoSms(owner_id=owner, session_id=record.id, language=record.language,
                              area=record.area, topic=record.pending_topic, question=text if record.pending_topic == 'question' else None)
            db.session.add(message)
        record.revision += 1
        record.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
        result = _screen(record)
        if message:
            result['message_id'] = message.id
            submit_job(current_app._get_current_object(), message.id)
        return jsonify(result)


@demo.route('/api/ussd/inbox')
def inbox():
    owner = _owner()
    messages = DemoSms.query.filter_by(owner_id=owner).order_by(DemoSms.id.desc()).limit(30).all()
    for message in messages:
        if message.status in ('queued', 'processing') and message.created_at < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=3):
            message.status = 'failed'
            message.body = translate('sms_ai_missing', message.language)
    db.session.commit()
    return jsonify([{'id': m.id, 'status': m.status, 'body': m.body, 'language': m.language,
        'encoding': m.encoding, 'segments': m.segments, 'source': m.source,
        'created_at': m.created_at.isoformat() + 'Z', 'area': AREAS[m.area]['name'],
        'simulated': True} for m in messages])
