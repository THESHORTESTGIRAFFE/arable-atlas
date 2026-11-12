from datetime import date, datetime, timezone
import json
import math
import os
import secrets
import tempfile
from flask import Flask, render_template, request, jsonify, session
from geopy.geocoders import Nominatim
from config import Config
from models import db, FarmPlot, FarmProfile
from translations import CATALOGS, LANGUAGES, normalize_language, translate
from utils import extract_gps, analyse_soil_image, ask_gemini, classify_soil_texture
from weather import get_forecast, build_action_plan

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db.init_app(app)
with app.app_context():
    db.create_all()


@app.context_processor
def language_catalogs():
    return {'catalogs': CATALOGS, 'languages': LANGUAGES,
            'demo_field': {'lat': Config.DEMO_FIELD_LAT, 'lon': Config.DEMO_FIELD_LON}}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/home')
def home():
    return render_template('dashboard.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/services')
def services():
    return render_template('services.html')


@app.route('/assistant')
def assistant():
    return render_template('assistant.html')


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('request_error')
    return data


def coordinates(data):
    lat, lon = data.get('lat', data.get('latitude')), data.get('lon', data.get('longitude'))
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError('invalid_coordinates')
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError('invalid_coordinates')
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('invalid_coordinates')
    return lat, lon


def crop_details(data):
    crop, planting = data.get('crop', ''), data.get('planting_date', '')
    if not isinstance(crop, str) or len(crop) > 100 or not isinstance(planting, str):
        raise ValueError('request_error')
    if planting:
        try:
            if date.fromisoformat(planting).isoformat() != planting:
                raise ValueError()
        except ValueError:
            raise ValueError('request_error')
    return crop.strip(), planting


def error_response(key='request_error', status=400, language='en'):
    return jsonify({'error': translate(key, language), 'error_key': key}), status


def validate_manual_soil(data):
    if not isinstance(data, dict):
        raise ValueError('manual_invalid')
    result = dict.fromkeys(('ph', 'organic_carbon_density', 'nitrogen', 'clay', 'sand', 'silt'), 'N/A')
    def number(key, minimum, maximum, required=False):
        value = data.get(key)
        if value is None or value == '':
            if required:
                raise ValueError('manual_invalid')
            return None
        if isinstance(value, bool):
            raise ValueError('manual_invalid')
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValueError('manual_invalid')
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError('manual_invalid')
        return value
    result['ph'] = number('ph', 0, 14, required=True)
    for key, maximum in (('nitrogen', 100), ('organic_carbon_density', 1000), ('clay', 100), ('sand', 100), ('silt', 100)):
        value = number(key, 0, maximum)
        if value is not None:
            result[key] = value
    texture = [result[key] for key in ('clay', 'sand', 'silt')]
    present = [value for value in texture if value != 'N/A']
    if present and (len(present) != 3 or not 99 <= sum(present) <= 101):
        raise ValueError('texture_invalid')
    top = number('depth_top_cm', 0, 199, required=True)
    bottom = number('depth_bottom_cm', 0, 200, required=True)
    if top >= bottom:
        raise ValueError('manual_invalid')
    sample_date = data.get('sample_date', '')
    if sample_date is not None and not isinstance(sample_date, str):
        raise ValueError('manual_invalid')
    if sample_date:
        try:
            if not isinstance(sample_date, str) or date.fromisoformat(sample_date).isoformat() != sample_date or date.fromisoformat(sample_date) > datetime.now(timezone.utc).date():
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('manual_invalid')
    elif sample_date is None:
        sample_date = ''
    result.update({'soil_type': classify_soil_texture(*texture), 'moisture': 'N/A',
        'soil_source': 'User-entered soil test', 'soil_method': 'manual', 'soil_access': 'manual',
        'depth': f'{top:g}-{bottom:g}cm', 'resolution_m': None, 'sample_date': sample_date})
    return result


def report_for(lat, lon, language, crop='', planting='', manual_soil=None):
    forecast = get_forecast(lat, lon)
    report = analyse_soil_image(lat=lat, lon=lon, language=language, forecast=forecast, manual_soil=manual_soil)
    try:
        location = Nominatim(user_agent='arable-atlas', timeout=4).reverse((lat, lon), language=language)
        location_name = location.address if location else ''
    except Exception:
        location_name = ''
    report.update({'latitude': lat, 'longitude': lon, 'location': location_name,
        'language': language, 'crop': crop, 'planting_date': planting,
        'analyzed_at': datetime.now(timezone.utc).isoformat(), 'forecast': forecast,
        'action_plan': build_action_plan(forecast, language, crop, planting)})
    return report


@app.route('/process', methods=['POST'])
def process_location():
    data = request.get_json(silent=True) or {}
    language = normalize_language(data.get('language')) if isinstance(data, dict) else 'en'
    try:
        data = json_body()
        lat, lon = coordinates(data)
        crop, planting = crop_details(data)
        manual_soil = validate_manual_soil(data['manual_soil']) if 'manual_soil' in data else None
        return jsonify(report_for(lat, lon, language, crop, planting, manual_soil))
    except ValueError as exc:
        return error_response(str(exc), language=language)


@app.route('/upload', methods=['POST'])
def upload_file():
    language = normalize_language(request.form.get('language'))
    file = request.files.get('image')
    if not file or not file.filename or file.filename.rsplit('.', 1)[-1].lower() not in ('jpg', 'jpeg', 'png'):
        return error_response(language=language)
    path = None
    try:
        crop, planting = crop_details(request.form)
        with tempfile.NamedTemporaryFile(dir=app.config['UPLOAD_FOLDER'], suffix='.image', delete=False) as temp:
            path = temp.name
            file.save(temp)
        gps = extract_gps(path)
        if not gps:
            return error_response('no_gps', language=language)
        lat, lon = coordinates({'lat': gps[0], 'lon': gps[1]})
        return jsonify(report_for(lat, lon, language, crop, planting))
    except (ValueError, OSError, TypeError):
        return error_response('no_gps', language=language)
    finally:
        if path and os.path.exists(path):
            os.remove(path)


@app.route('/api/plan', methods=['POST'])
def field_plan():
    try:
        data = json_body()
        language = normalize_language(data.get('language'))
        lat, lon = coordinates(data)
        crop, planting = crop_details(data)
        forecast = get_forecast(lat, lon)
        return jsonify({'forecast': forecast, 'action_plan': build_action_plan(forecast, language, crop, planting),
                        'crop': crop, 'planting_date': planting})
    except ValueError as exc:
        return error_response(str(exc))


# Only bounded report fields can enter a saved snapshot or model context.
REPORT_FIELDS = ('latitude', 'longitude', 'location', 'soil_type', 'soil_status', 'soil_source',
    'ph', 'organic_carbon_density', 'nitrogen', 'clay', 'sand', 'silt', 'crops', 'actionable_advice',
    'forecast', 'action_plan', 'language', 'crop', 'planting_date', 'analyzed_at', 'depth', 'resolution_m',
    'soil_method', 'soil_access', 'soil_fetched_at', 'missing_properties', 'sample_date')


def bounded_report(value):
    if not isinstance(value, dict):
        raise ValueError('request_error')
    report = {key: value[key] for key in REPORT_FIELDS if key in value}
    encoded = json.dumps(report, allow_nan=False)
    if len(encoded) > 24000:
        raise ValueError('request_error')
    return report


@app.route('/ask', methods=['POST'])
def ask_assistant():
    try:
        data = json_body()
        language = normalize_language(data.get('language'))
        query = data.get('query')
        if not isinstance(query, str) or not query.strip() or len(query) > 4000:
            return error_response(language=language)
        history = data.get('history', [])
        if not isinstance(history, list) or len(history) > 12:
            return error_response(language=language)
        for message in history:
            if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant') or not isinstance(message.get('content'), str) or len(message['content']) > 8000:
                return error_response(language=language)
        context = bounded_report(data['context']) if data.get('context') is not None else None
        response = ask_gemini(query.strip(), language, history=history, context=context)
        if response.startswith('Error:'):
            return error_response('chat_error', status=503, language=language)
        return jsonify({'response': response[:8000], 'language': language})
    except (ValueError, TypeError):
        return error_response()


@app.route('/api/report-language', methods=['POST'])
def report_language():
    try:
        data = json_body()
        language = normalize_language(data.get('language'))
        report = bounded_report(data.get('report'))
        if not report.get('crops'):
            return jsonify({'language': language, 'crops': [], 'actionable_advice': translate(
                'soil_unavailable' if report.get('soil_status') == 'unavailable' else 'chat_error', language)})
        prompt = ('Translate this existing agricultural report faithfully, without adding advice or facts. '
                  'Return only JSON with crops (array of names) and advice (string). Report: ' +
                  json.dumps({'crops': report.get('crops'), 'advice': report.get('actionable_advice')}))
        answer = ask_gemini(prompt, language, purpose='recommendation')
        parsed = json.loads(answer.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip())
        if not isinstance(parsed.get('crops'), list) or not isinstance(parsed.get('advice'), str):
            raise ValueError()
        return jsonify({'language': language, 'crops': [c[:100] for c in parsed['crops'][:3] if isinstance(c, str)],
                        'actionable_advice': parsed['advice'][:6000]})
    except (ValueError, TypeError, AttributeError):
        return error_response('chat_error', status=503)


def owner_id():
    if 'farm_owner' not in session:
        session['farm_owner'] = secrets.token_hex(24)
    return session['farm_owner']


@app.route('/api/plots', methods=['GET', 'POST'])
def manage_plots():
    owner = owner_id()
    if request.method == 'POST':
        try:
            data = json_body()
            lat, lon = coordinates(data)
            crop, planting = crop_details(data)
            name = data.get('plot_name', 'My Farm Plot')
            if not isinstance(name, str) or not name.strip() or len(name) > 100:
                return error_response()
            report = bounded_report(data.get('report', data))
            # Coordinates and crop metadata have a single validated source.
            report.update({'latitude': lat, 'longitude': lon, 'crop': crop, 'planting_date': planting})
            plot = FarmPlot(plot_name=name.strip(), latitude=lat, longitude=lon,
                soil_type=str(report.get('soil_type', 'Unknown'))[:50], ph=str(report.get('ph', 'N/A'))[:20],
                moisture='N/A', nitrogen=str(report.get('nitrogen', 'N/A'))[:20],
                recommendations=str(report.get('actionable_advice', data.get('recommendations', '')))[:6000])
            profile = FarmProfile(plot=plot, owner_id=owner, crop=crop, planting_date=planting, report=report)
            db.session.add(profile)
            db.session.commit()
            return jsonify({'message': 'Plot saved successfully', 'id': plot.id}), 201
        except (ValueError, TypeError):
            return error_response()
    profiles = FarmProfile.query.filter_by(owner_id=owner).join(FarmPlot).order_by(FarmPlot.timestamp.desc(), FarmPlot.id.desc()).all()
    return jsonify([{'id': p.plot.id, 'plot_name': p.plot.plot_name, 'latitude': p.plot.latitude,
        'longitude': p.plot.longitude, 'soil_type': p.plot.soil_type, 'ph': p.plot.ph, 'moisture': 'N/A',
        'nitrogen': p.plot.nitrogen, 'recommendations': p.plot.recommendations,
        'timestamp': p.plot.timestamp.isoformat(), 'crop': p.crop, 'planting_date': p.planting_date,
        'report': p.report} for p in profiles])


@app.errorhandler(413)
def upload_too_large(error):
    return error_response(status=413)


if __name__ == '__main__':
    app.run(debug=True)
