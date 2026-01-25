#!/usr/bin/env python3
import json
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ENV_PATH = Path('/home/byrro/automation/dawarich-trips/.env')
CONTAINER_ENV_PATH = Path('/dawarich-trips/.env')
ENV_PATH = CONTAINER_ENV_PATH if CONTAINER_ENV_PATH.exists() else DEFAULT_ENV_PATH

DEFAULT_SECRETS_PATH = Path('/mnt/ByrroServer/docker-data/homeassistant/config/secrets.yaml')
CONTAINER_SECRETS_PATH = Path('/config/secrets.yaml')
SECRETS_PATH = CONTAINER_SECRETS_PATH if CONTAINER_SECRETS_PATH.exists() else DEFAULT_SECRETS_PATH

DEFAULT_STATE_PATH = Path('/home/byrro/automation/dawarich-trips/dawarich_trips.json')
CONFIG_DIR = Path('/config')
CONTAINER_STATE_PATH = CONFIG_DIR / 'dawarich_trips.json'

TIMEZONE = ZoneInfo('America/New_York')

MAP_AREA_MONTHLY = 'trips_monthly'
MAP_AREA_YEARLY = 'trips_yearly'
MAP_DISTANCE_MONTHLY = 'trips_distance_monthly'
MAP_DISTANCE_YEARLY = 'trips_distance_yearly'
MAP_DAYTYPE_MONTHLY = 'trips_daytype_monthly'
MAP_DAYTYPE_YEARLY = 'trips_daytype_yearly'


def read_env(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        data[key.strip()] = val.strip()
    return data


def read_secrets(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        key, val = line.split(':', 1)
        data[key.strip()] = val.strip()
    return data


def slugify(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    return text or 'unknown'


def now_iso() -> str:
    return datetime.now(TIMEZONE).isoformat(timespec='seconds')


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_miles * c


def ha_request(method: str, path: str, payload: dict | None = None):
    headers = {'Authorization': f'Bearer {HA_TOKEN}'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(f"{HA_BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode('utf-8')
        return resp.status, body


def ha_get_state(entity_id: str) -> dict:
    status, body = ha_request('GET', f'/api/states/{entity_id}')
    if status != 200:
        raise RuntimeError(f"HA state fetch failed: {entity_id} status={status}")
    return json.loads(body)


def ha_service(domain: str, service: str, payload: dict) -> None:
    status, body = ha_request('POST', f'/api/services/{domain}/{service}', payload)
    if status != 200:
        raise RuntimeError(f"HA service failed: {domain}.{service} status={status} body={body[:200]}")


def set_input_text(entity_id: str, value: str) -> None:
    ha_service('input_text', 'set_value', {
        'entity_id': entity_id,
        'value': value,
    })


def dawarich_request(method: str, path: str, payload: dict | None = None):
    headers = {'Authorization': f'Bearer {DAWARICH_API_KEY}'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(f"{DAWARICH_BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode('utf-8')
        return resp.status, body


def rate_limited_error_notify(message: str) -> None:
    now = datetime.now(TIMEZONE)
    should_notify = True
    try:
        state = ha_get_state('input_datetime.dawarich_last_error')
        raw = state.get('state')
        if raw and raw not in ('unknown', 'unavailable'):
            last = datetime.fromisoformat(raw)
            if (now - last) < timedelta(hours=1):
                should_notify = False
    except Exception:
        pass

    try:
        set_input_text('input_text.dawarich_last_error', message[:255])
        ha_service('input_datetime', 'set_datetime', {
            'entity_id': 'input_datetime.dawarich_last_error',
            'datetime': now.isoformat(timespec='seconds'),
        })
    except Exception:
        pass

    if should_notify:
        ha_service('persistent_notification', 'create', {
            'title': 'Dawarich Trip Error',
            'message': message,
            'notification_id': 'dawarich_trip_error',
        })


def load_state() -> dict:
    state = {
        MAP_AREA_MONTHLY: {},
        MAP_AREA_YEARLY: {},
        MAP_DISTANCE_MONTHLY: {},
        MAP_DISTANCE_YEARLY: {},
        MAP_DAYTYPE_MONTHLY: {},
        MAP_DAYTYPE_YEARLY: {},
        'geo_cache': {},
    }
    if not STATE_PATH.exists():
        return state
    try:
        data = json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return state
    if not isinstance(data, dict):
        return state

    legacy = data.get('trips')
    if isinstance(legacy, dict):
        state[MAP_AREA_MONTHLY] = legacy

    for key in [
        MAP_AREA_MONTHLY,
        MAP_AREA_YEARLY,
        MAP_DISTANCE_MONTHLY,
        MAP_DISTANCE_YEARLY,
        MAP_DAYTYPE_MONTHLY,
        MAP_DAYTYPE_YEARLY,
    ]:
        value = data.get(key)
        if isinstance(value, dict):
            state[key] = value

    cache = data.get('geo_cache')
    if isinstance(cache, dict):
        state['geo_cache'] = cache
    return state


def save_state(state: dict) -> None:
    payload = {
        MAP_AREA_MONTHLY: state.get(MAP_AREA_MONTHLY, {}),
        MAP_AREA_YEARLY: state.get(MAP_AREA_YEARLY, {}),
        MAP_DISTANCE_MONTHLY: state.get(MAP_DISTANCE_MONTHLY, {}),
        MAP_DISTANCE_YEARLY: state.get(MAP_DISTANCE_YEARLY, {}),
        MAP_DAYTYPE_MONTHLY: state.get(MAP_DAYTYPE_MONTHLY, {}),
        MAP_DAYTYPE_YEARLY: state.get(MAP_DAYTYPE_YEARLY, {}),
        'geo_cache': state.get('geo_cache', {}),
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_suffix('.tmp')
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
    tmp_path.replace(STATE_PATH)


def get_state_value(entity_id: str) -> str:
    return (ha_get_state(entity_id).get('state') or '').strip()


def get_trip_id() -> str:
    return get_state_value('input_text.dawarich_current_trip_id')


def get_trip_key() -> str:
    return get_state_value('input_text.dawarich_current_trip_key')


def get_yearly_trip_id() -> str:
    return get_state_value('input_text.dawarich_current_trip_id_yearly')


def get_yearly_trip_key() -> str:
    return get_state_value('input_text.dawarich_current_trip_key_yearly')


def get_distance_trip_id() -> str:
    return get_state_value('input_text.dawarich_current_trip_id_distance')


def get_distance_trip_key() -> str:
    return get_state_value('input_text.dawarich_current_trip_key_distance')


def get_distance_yearly_trip_id() -> str:
    return get_state_value('input_text.dawarich_current_trip_id_distance_yearly')


def get_distance_yearly_trip_key() -> str:
    return get_state_value('input_text.dawarich_current_trip_key_distance_yearly')


def get_daytype_trip_id() -> str:
    return get_state_value('input_text.dawarich_current_trip_id_daytype')


def get_daytype_trip_key() -> str:
    return get_state_value('input_text.dawarich_current_trip_key_daytype')


def get_daytype_yearly_trip_id() -> str:
    return get_state_value('input_text.dawarich_current_trip_id_daytype_yearly')


def get_daytype_yearly_trip_key() -> str:
    return get_state_value('input_text.dawarich_current_trip_key_daytype_yearly')


def get_on_trip() -> bool:
    return get_state_value('input_boolean.dawarich_on_trip') == 'on'


def get_last_update() -> datetime | None:
    raw = get_state_value('input_datetime.dawarich_trip_last_update')
    if raw in ('unknown', 'unavailable', ''):
        return None
    try:
        value = datetime.fromisoformat(raw)
        if value.tzinfo is None:
            value = value.replace(tzinfo=TIMEZONE)
        return value
    except Exception:
        return None


def get_extend_minutes() -> int:
    raw = get_state_value('input_number.dawarich_extend_minutes')
    try:
        return max(1, int(float(raw)))
    except Exception:
        return 10


def get_person_location() -> tuple[float, float]:
    person = ha_get_state(PERSON_ENTITY)
    lat = person.get('attributes', {}).get('latitude')
    lon = person.get('attributes', {}).get('longitude')
    if lat is None or lon is None:
        zone = ha_get_state(HOME_ZONE)
        lat = zone.get('attributes', {}).get('latitude')
        lon = zone.get('attributes', {}).get('longitude')
    if lat is None or lon is None:
        raise RuntimeError(f"Missing latitude/longitude for {PERSON_ENTITY} and {HOME_ZONE}")
    return float(lat), float(lon)


def get_home_location() -> tuple[float, float]:
    zone = ha_get_state(HOME_ZONE)
    lat = zone.get('attributes', {}).get('latitude')
    lon = zone.get('attributes', {}).get('longitude')
    if lat is None or lon is None:
        raise RuntimeError(f"Missing latitude/longitude for {HOME_ZONE}")
    return float(lat), float(lon)


def get_area_name_from_ha() -> str | None:
    try:
        state = ha_get_state(GEOCODE_ENTITY)
    except Exception:
        return None

    value = (state.get('state') or '').strip()
    if value in ('unknown', 'unavailable'):
        value = ''

    attrs = state.get('attributes') or {}
    city = attrs.get('city') or attrs.get('town') or attrs.get('village') or attrs.get('county')
    region = attrs.get('state') or attrs.get('region')

    if city and region:
        return f"{city}, {region}"
    if city:
        return city
    if region:
        return region
    if value:
        return value
    return None


def reverse_geocode_nominatim(lat: float, lon: float) -> str | None:
    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?format=jsonv2&lat={lat}&lon={lon}&zoom=10&addressdetails=1"
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'DawarichTrips/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

    address = data.get('address') or {}
    city = address.get('city') or address.get('town') or address.get('village') or address.get('county')
    region = address.get('state')

    if city and region:
        return f"{city}, {region}"
    if city:
        return city
    if region:
        return region
    return data.get('name') or data.get('display_name')


def resolve_area(lat: float, lon: float, state: dict) -> tuple[str, str, bool]:
    dirty = False
    area_name = get_area_name_from_ha()
    geo_key = f"{round(lat, 2)}|{round(lon, 2)}"
    if not area_name:
        area_name = state['geo_cache'].get(geo_key)
    if not area_name:
        area_name = reverse_geocode_nominatim(lat, lon)
        if area_name:
            state['geo_cache'][geo_key] = area_name
            dirty = True
    if not area_name:
        area_name = f"{lat:.2f}, {lon:.2f}"
    area_key = slugify(area_name)
    return area_name, area_key, dirty


def resolve_distance_band(distance_miles: float) -> tuple[str, str]:
    for name, limit in DISTANCE_BANDS:
        if limit is None or distance_miles <= limit:
            return name, slugify(name)
    return 'Travel', 'travel'


def resolve_daytype(now: datetime) -> tuple[str, str]:
    if now.weekday() >= 5:
        return 'Weekend', 'weekend'
    return 'Weekday', 'weekday'


def set_area_trip(trip_id: str, trip_key: str, started_at: str, last_update: str) -> None:
    set_input_text('input_text.dawarich_current_trip_id', trip_id)
    set_input_text('input_text.dawarich_current_trip_key', trip_key)
    ha_service('input_boolean', 'turn_on', {
        'entity_id': 'input_boolean.dawarich_on_trip',
    })
    ha_service('input_datetime', 'set_datetime', {
        'entity_id': 'input_datetime.dawarich_trip_start',
        'datetime': started_at,
    })
    ha_service('input_datetime', 'set_datetime', {
        'entity_id': 'input_datetime.dawarich_trip_last_update',
        'datetime': last_update,
    })


def set_area_yearly_trip(trip_id: str, trip_key: str) -> None:
    set_input_text('input_text.dawarich_current_trip_id_yearly', trip_id)
    set_input_text('input_text.dawarich_current_trip_key_yearly', trip_key)


def set_distance_trip(monthly_id: str, monthly_key: str, yearly_id: str, yearly_key: str) -> None:
    set_input_text('input_text.dawarich_current_trip_id_distance', monthly_id)
    set_input_text('input_text.dawarich_current_trip_key_distance', monthly_key)
    set_input_text('input_text.dawarich_current_trip_id_distance_yearly', yearly_id)
    set_input_text('input_text.dawarich_current_trip_key_distance_yearly', yearly_key)


def set_daytype_trip(monthly_id: str, monthly_key: str, yearly_id: str, yearly_key: str) -> None:
    set_input_text('input_text.dawarich_current_trip_id_daytype', monthly_id)
    set_input_text('input_text.dawarich_current_trip_key_daytype', monthly_key)
    set_input_text('input_text.dawarich_current_trip_id_daytype_yearly', yearly_id)
    set_input_text('input_text.dawarich_current_trip_key_daytype_yearly', yearly_key)


def clear_current_trips() -> None:
    ha_service('input_boolean', 'turn_off', {
        'entity_id': 'input_boolean.dawarich_on_trip',
    })
    for entity_id in [
        'input_text.dawarich_current_trip_id',
        'input_text.dawarich_current_trip_key',
        'input_text.dawarich_current_trip_id_yearly',
        'input_text.dawarich_current_trip_key_yearly',
        'input_text.dawarich_current_trip_id_distance',
        'input_text.dawarich_current_trip_key_distance',
        'input_text.dawarich_current_trip_id_distance_yearly',
        'input_text.dawarich_current_trip_key_distance_yearly',
        'input_text.dawarich_current_trip_id_daytype',
        'input_text.dawarich_current_trip_key_daytype',
        'input_text.dawarich_current_trip_id_daytype_yearly',
        'input_text.dawarich_current_trip_key_daytype_yearly',
    ]:
        set_input_text(entity_id, '')


def update_trip(trip_id: str, ended_at: str) -> bool:
    payload = {'trip': {'ended_at': ended_at}}
    try:
        status, body = dawarich_request('PATCH', f'/api/v1/trips/{trip_id}', payload)
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode('utf-8', errors='replace')
        rate_limited_error_notify(f'Update trip failed: status={exc.code} body={msg[:200]}')
        return False
    except Exception as exc:
        rate_limited_error_notify(f'Update trip failed: {exc}')
        return False

    if status not in (200, 204):
        rate_limited_error_notify(f'Update trip failed: status={status} body={body[:200]}')
        return False

    try:
        ha_service('input_datetime', 'set_datetime', {
            'entity_id': 'input_datetime.dawarich_trip_last_update',
            'datetime': ended_at,
        })
    except Exception as exc:
        rate_limited_error_notify(f'Update trip succeeded but HA state update failed: {exc}')
        return False

    return True


def create_trip(name_prefix: str, area_name: str, lat: float, lon: float, started_at: str) -> str | None:
    ended_at = (datetime.fromisoformat(started_at) + timedelta(minutes=1)).isoformat(timespec='seconds')
    name = f"{name_prefix} {area_name}".strip()
    payload = {
        'trip': {
            'name': name,
            'latitude': lat,
            'longitude': lon,
            'started_at': started_at,
            'ended_at': ended_at,
        }
    }
    try:
        status, body = dawarich_request('POST', '/api/v1/trips', payload)
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode('utf-8', errors='replace')
        rate_limited_error_notify(f'Create trip failed: status={exc.code} body={msg[:200]}')
        return None
    except Exception as exc:
        rate_limited_error_notify(f'Create trip failed: {exc}')
        return None

    if status not in (200, 201):
        rate_limited_error_notify(f'Create trip failed: status={status} body={body[:200]}')
        return None

    try:
        data = json.loads(body)
        trip_id = str(data.get('id', '')).strip()
    except Exception:
        trip_id = ''

    if not trip_id:
        rate_limited_error_notify('Create trip failed: missing trip id in response')
        return None

    return trip_id


def ensure_trip(state: dict, map_name: str, trip_key: str, name_prefix: str, area_name: str,
                lat: float, lon: float, now_str: str) -> str | None:
    trip_map = state.get(map_name, {})
    entry = trip_map.get(trip_key) or {}
    trip_id = str(entry.get('trip_id', '')).strip()

    if trip_id:
        entry['last_seen'] = now_str
        entry.setdefault('area_name', area_name)
        entry.setdefault('first_seen', now_str)
        trip_map[trip_key] = entry
        state[map_name] = trip_map
        return trip_id

    trip_id = create_trip(name_prefix, area_name, lat, lon, now_str)
    if not trip_id:
        return None

    trip_map[trip_key] = {
        'trip_id': trip_id,
        'area_name': area_name,
        'first_seen': now_str,
        'last_seen': now_str,
    }
    state[map_name] = trip_map
    return trip_id


def touch_trip_map(state: dict, map_name: str, trip_key: str, trip_id: str,
                   area_name: str, now_str: str) -> None:
    trip_map = state.get(map_name, {})
    entry = trip_map.get(trip_key) or {}
    entry.setdefault('trip_id', trip_id)
    entry.setdefault('area_name', area_name)
    entry.setdefault('first_seen', now_str)
    entry['last_seen'] = now_str
    trip_map[trip_key] = entry
    state[map_name] = trip_map


def should_update(now: datetime) -> bool:
    last = get_last_update()
    if not last:
        return True
    extend_minutes = get_extend_minutes()
    return (now - last) >= timedelta(minutes=max(1, extend_minutes))


def action_create() -> int:
    lat, lon = get_person_location()
    now = datetime.now(TIMEZONE)
    now_str = now.isoformat(timespec='seconds')
    state = load_state()

    month_key = now.strftime('%Y-%m')
    year_key = now.strftime('%Y')
    month_name = f"{year_key} - {now.strftime('%m')}"
    year_name = year_key

    monthly_id = get_trip_id()
    monthly_current_key = get_trip_key()
    yearly_id = get_yearly_trip_id()
    yearly_current_key = get_yearly_trip_key()

    if monthly_current_key and monthly_current_key != month_key and monthly_id:
        update_trip(monthly_id, now_str)
    if yearly_current_key and yearly_current_key != year_key and yearly_id:
        update_trip(yearly_id, now_str)

    monthly_id = ensure_trip(state, MAP_AREA_MONTHLY, month_key, month_name, '', lat, lon, now_str)
    yearly_id = ensure_trip(state, MAP_AREA_YEARLY, year_key, year_name, '', lat, lon, now_str)

    if not monthly_id:
        save_state(state)
        return 1

    try:
        set_area_trip(monthly_id, month_key, now_str, now_str)
        set_area_yearly_trip(yearly_id or '', year_key if yearly_id else '')
        set_distance_trip('', '', '', '')
        set_daytype_trip('', '', '', '')
    except Exception as exc:
        rate_limited_error_notify(f'HA state update failed: {exc}')
        return 1

    save_state(state)

    if not yearly_id:
        rate_limited_error_notify('Yearly trip failed to create; monthly trip active')
        return 1

    print(f'Created/resumed monthly={monthly_id} yearly={yearly_id}')
    return 0


def action_extend() -> int:
    lat, lon = get_person_location()
    now = datetime.now(TIMEZONE)
    now_str = now.isoformat(timespec='seconds')
    state = load_state()

    month_key = now.strftime('%Y-%m')
    year_key = now.strftime('%Y')
    month_name = f"{year_key} - {now.strftime('%m')}"
    year_name = year_key

    monthly_id = get_trip_id()
    monthly_current_key = get_trip_key()
    yearly_id = get_yearly_trip_id()
    yearly_current_key = get_yearly_trip_key()

    monthly_switched = False
    if monthly_current_key and monthly_current_key != month_key and monthly_id:
        update_trip(monthly_id, now_str)
        monthly_switched = True
    if monthly_switched:
        monthly_id = ''

    yearly_switched = False
    if yearly_current_key and yearly_current_key != year_key and yearly_id:
        update_trip(yearly_id, now_str)
        yearly_switched = True
    if yearly_switched:
        yearly_id = ''

    need_ensure = monthly_switched or yearly_switched or not monthly_id or not yearly_id

    if need_ensure:
        monthly_id = ensure_trip(state, MAP_AREA_MONTHLY, month_key, month_name, '', lat, lon, now_str)
        yearly_id = ensure_trip(state, MAP_AREA_YEARLY, year_key, year_name, '', lat, lon, now_str)

        if not monthly_id:
            save_state(state)
            return 1

        try:
            set_area_trip(monthly_id, month_key, now_str, now_str)
            set_area_yearly_trip(yearly_id or '', year_key if yearly_id else '')
            set_distance_trip('', '', '', '')
            set_daytype_trip('', '', '', '')
        except Exception as exc:
            rate_limited_error_notify(f'HA state update failed: {exc}')
            return 1

        save_state(state)

        if not yearly_id:
            rate_limited_error_notify('Yearly trip failed to create; monthly trip active')
            return 1

        print(f'Switched/resumed monthly={monthly_id} yearly={yearly_id}')
        return 0

    if not should_update(now):
        print('Skip update; last update within extend window')
        return 0

    ok = True
    if monthly_id:
        ok = update_trip(monthly_id, now_str) and ok
    if yearly_id:
        ok = update_trip(yearly_id, now_str) and ok

    if not ok:
        return 1

    touch_trip_map(state, MAP_AREA_MONTHLY, month_key, monthly_id, '', now_str)
    touch_trip_map(state, MAP_AREA_YEARLY, year_key, yearly_id, '', now_str)
    save_state(state)

    print(f'Updated monthly={monthly_id} yearly={yearly_id}')
    return 0


def action_finalize() -> int:
    monthly_id = get_trip_id()
    yearly_id = get_yearly_trip_id()

    if not any([monthly_id, yearly_id]):
        return 0

    ended_at = now_iso()
    ok = True
    if monthly_id:
        ok = update_trip(monthly_id, ended_at) and ok
    if yearly_id:
        ok = update_trip(yearly_id, ended_at) and ok

    if not ok:
        return 1

    try:
        clear_current_trips()
    except Exception as exc:
        rate_limited_error_notify(f'Finalize trip succeeded but HA state update failed: {exc}')
        return 1

    print('Finalized monthly/yearly trips')
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: dawarich_trip.py create|extend|finalize')
        return 2

    if not DAWARICH_BASE_URL or not DAWARICH_API_KEY:
        print('Missing Dawarich configuration in .env')
        return 2
    if not HA_TOKEN:
        print('Missing ha_long_lived_token in secrets.yaml')
        return 2

    action = sys.argv[1].strip().lower()
    if action == 'create':
        return action_create()
    if action == 'extend':
        return action_extend()
    if action == 'finalize':
        return action_finalize()

    print('Unknown action')
    return 2


ENV = read_env(ENV_PATH)
SECRETS = read_secrets(SECRETS_PATH)
DAWARICH_BASE_URL = ENV.get('DAWARICH_BASE_URL', '').rstrip('/')
DAWARICH_API_KEY = ENV.get('DAWARICH_API_KEY', '')
HA_TOKEN = SECRETS.get('ha_long_lived_token', '')
HA_BASE = (ENV.get('HA_BASE_URL', '') or '').rstrip('/')
if not HA_BASE:
    HA_BASE = 'http://127.0.0.1:8123' if CONFIG_DIR.exists() else 'https://home.byrroserver.com'

PERSON_ENTITY = ENV.get('HA_PERSON_ENTITY', 'person.andre_byrro')
HOME_ZONE = ENV.get('HA_HOME_ZONE', 'zone.home')
GEOCODE_ENTITY = ENV.get('HA_GEOCODE_ENTITY', 'sensor.andre_iphone_geocoded_location')
STATE_PATH = Path(
    ENV.get('DAWARICH_STATE_PATH')
    or (str(CONTAINER_STATE_PATH) if CONFIG_DIR.exists() else str(DEFAULT_STATE_PATH))
)

DIST_LOCAL_MI = float(ENV.get('DAWARICH_DISTANCE_LOCAL_MI', '5'))
DIST_REGIONAL_MI = float(ENV.get('DAWARICH_DISTANCE_REGIONAL_MI', '25'))
DIST_DAYTRIP_MI = float(ENV.get('DAWARICH_DISTANCE_DAYTRIP_MI', '100'))

DISTANCE_BANDS = [
    ('Local', DIST_LOCAL_MI),
    ('Regional', DIST_REGIONAL_MI),
    ('Day Trip', DIST_DAYTRIP_MI),
    ('Travel', None),
]


if __name__ == '__main__':
    sys.exit(main())
