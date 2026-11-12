"""Five-day, three-hour forecast summaries and transparent field-check rules."""
from datetime import datetime, timedelta, timezone, date
from threading import Lock
import time
import requests
from config import Config
from translations import translate

_cache = {}
_lock = Lock()


def get_forecast(lat, lon):
    key = (round(lat, 4), round(lon, 4))
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 600:
            return cached[1]
    unavailable = {'status': 'unavailable', 'source': 'OpenWeatherMap', 'days': []}
    api_key = Config.OPENWEATHER_API_KEY
    if not api_key or api_key.startswith('your_'):
        return unavailable
    try:
        response = requests.get(Config.OPENWEATHER_FORECAST_URL, params={
            'lat': lat, 'lon': lon, 'appid': api_key, 'units': 'metric'
        }, timeout=12)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return unavailable
        offset = timezone(timedelta(seconds=int(payload.get('city', {}).get('timezone', 0))))
        grouped = {}
        for item in payload.get('list', []):
            local_date = datetime.fromtimestamp(item['dt'], offset).date().isoformat()
            main = item['main']
            day = grouped.setdefault(local_date, {'date': local_date, 'temp_min': 100,
                'temp_max': -100, 'rain_mm': 0, 'wind_ms': 0, 'samples': 0})
            day['temp_min'] = min(day['temp_min'], float(main['temp_min']))
            day['temp_max'] = max(day['temp_max'], float(main['temp_max']))
            day['rain_mm'] += float(item.get('rain', {}).get('3h', 0))
            day['wind_ms'] = max(day['wind_ms'], float(item.get('wind', {}).get('speed', 0)))
            day['samples'] += 1
        days = list(sorted(grouped.values(), key=lambda d: d['date']))[:5]
        if not days:
            return unavailable
        for day in days:
            for field in ('temp_min', 'temp_max', 'rain_mm', 'wind_ms'):
                day[field] = round(day[field], 1)
            day['partial'] = day['samples'] < 8
        result = {'status': 'available', 'source': 'OpenWeatherMap', 'days': days,
                  'fetched_at': datetime.now(timezone.utc).isoformat()}
        with _lock:
            # Keep memory bounded even when many different map points are selected.
            if len(_cache) >= 256:
                _cache.pop(next(iter(_cache)))
            _cache[key] = (time.monotonic(), result)
        return result
    except (requests.RequestException, ValueError, TypeError, KeyError, OverflowError):
        return unavailable


def build_action_plan(forecast, language='en', crop='', planting_date=''):
    """No invented forecast or crop-specific doses; every action exposes its trigger."""
    plan = {'status': forecast['status'], 'crop': crop, 'planting_date': planting_date,
            'note': translate('plan_note', language), 'days': []}
    if forecast['status'] != 'available':
        plan['message'] = translate('weather_unavailable', language)
        return plan
    planted = date.fromisoformat(planting_date) if planting_date else None
    for day in forecast['days']:
        rules = ['heavy_rain' if day['rain_mm'] >= 10 else
                 'some_rain' if day['rain_mm'] >= 2 else 'dry_day']
        if day['temp_max'] >= 32:
            rules.append('heat')
        if day['temp_min'] <= 2:
            rules.append('frost')
        if day['wind_ms'] >= 6:
            rules.append('wind_action')
        actions = [translate(rule, language) for rule in rules]
        if planted:
            age = (date.fromisoformat(day['date']) - planted).days
            actions.append(translate('before_planting', language) if age < 0 else
                           translate('after_planting', language, days=age))
        plan['days'].append({'date': day['date'], 'actions': actions, 'rules': rules})
    return plan
