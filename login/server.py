"""Python Flask WebApp Auth0 integration
"""
from collections import defaultdict, deque
from functools import wraps
import json, sys
import secrets
import dateparser ,datetime
import subprocess, os
from os import environ as env
from pathlib import Path
from threading import Lock
import time
from werkzeug.exceptions import HTTPException

from dotenv import load_dotenv, find_dotenv
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for
from flask import request
from flask import send_from_directory
from authlib.integrations.flask_client import OAuth
from six.moves.urllib.parse import urlencode
from lib.mongo import mongoHelper
from lib.selector_memory import get_selector_memory_summary
from lib.studio_copilot import suggest_studio_copilot_plan
from lib.studio_inspector import build_inspector_response
from lib.studio import build_studio_state, get_studio_method_catalog, is_studio_enabled, validate_studio_payload

import constants

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)


def utc_now():
    return datetime.datetime.now(datetime.UTC)


def get_app_env():
    return env.get('APP_ENV', 'local')


def is_local_mode():
    return get_app_env() == 'local'


def get_local_profile():
    return {
        'user_id': 'local_admin',
        'name': 'Local Admin',
        'email': 'admin@localhost',
        'picture': ''
    }


def is_auth0_configured():
    required_settings = (
        AUTH0_CLIENT_ID,
        AUTH0_CLIENT_SECRET,
        AUTH0_DOMAIN,
        AUTH0_CALLBACK_URL,
        AUTH0_LOGOUT_REDIRECT_URL,
    )
    return all(required_settings)


def get_secret_key():
    configured_secret = env.get(constants.SECRET_KEY)
    if configured_secret:
        return configured_secret
    if get_app_env() == 'production':
        raise RuntimeError('SECRET_KEY must be set when APP_ENV=production')
    return os.urandom(24)

AUTH0_CALLBACK_URL = env.get(constants.AUTH0_CALLBACK_URL)
AUTH0_LOGOUT_REDIRECT_URL = env.get(constants.AUTH0_LOGOUT_REDIRECT_URL)
AUTH0_CLIENT_ID = env.get(constants.AUTH0_CLIENT_ID)
AUTH0_CLIENT_SECRET = env.get(constants.AUTH0_CLIENT_SECRET)
AUTH0_DOMAIN = env.get(constants.AUTH0_DOMAIN)
AUTH0_BASE_URL = f'https://{AUTH0_DOMAIN}' if AUTH0_DOMAIN else None
AUTH0_AUDIENCE = env.get(constants.AUTH0_AUDIENCE)

app = Flask(__name__, static_url_path='/public', static_folder='./public')
app.secret_key = get_secret_key()
app.debug = get_app_env() != 'production'
app.TRAP_HTTP_EXCEPTIONS = True
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=get_app_env() == 'production',
)

errors = 0

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCKER_ROOT = Path('/work')


# Connection to mongodb
db = mongoHelper.mongo_conn()


def get_runtime_root():
    if (DOCKER_ROOT / 'main.py').exists():
        return DOCKER_ROOT
    return PROJECT_ROOT


def get_python_command():
    if get_runtime_root() == DOCKER_ROOT:
        return 'python'
    return sys.executable


def get_script_path(script_name):
    return get_runtime_root() / script_name


def get_downloads_dir():
    return get_runtime_root() / 'login' / 'downloads'


def generate_task_token(prefix=''):
    token = secrets.token_urlsafe(24)
    return prefix + token if prefix else token


def normalize_boolean(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def is_valid_form_token(token):
    return bool(token) and token == session.get('form_token')


def is_valid_preview_token(preview_id):
    if not preview_id:
        return False
    valid_tokens = {
        session.get('form_token'),
        session.get('studio_token'),
    }
    return preview_id in {token for token in valid_tokens if token}


def get_current_user_id():
    profile = session.get(constants.PROFILE_KEY) or {}
    return str(profile.get('user_id', '')).strip() or None


def build_preview_cache_query(preview_id, user_id=None):
    query = {'preview_id': preview_id}
    if user_id:
        query['user_id'] = user_id
    return query


def build_preview_cache_payload(preview_id, url, method, user_id):
    return json.dumps(
        {
            'preview_id': preview_id,
            'url': url,
            'c_method': method,
            'user_id': user_id,
        },
        ensure_ascii=True,
        separators=(',', ':'),
    )


def build_preview_run_payload(preview_id, steps, args, method, url, user_id):
    return json.dumps(
        {
            'preview_id': preview_id,
            'steps': steps,
            'args': args,
            'c_method': method,
            'url': url,
            'user_id': user_id,
        },
        ensure_ascii=True,
        separators=(',', ':'),
    )


def build_content_security_policy():
    directives = {
        'default-src': ["'self'", 'https:'],
        'script-src': ["'self'", 'https://cdn.jsdelivr.net', "'unsafe-inline'"],
        'style-src': ["'self'", 'https://cdn.jsdelivr.net', "'unsafe-inline'"],
        'img-src': ["'self'", 'data:', 'https:'],
        'font-src': ["'self'", 'data:', 'https:'],
        'connect-src': ["'self'", 'https:'],
        'frame-ancestors': ["'self'"],
        'base-uri': ["'self'"],
        'form-action': ["'self'"],
    }
    return '; '.join(
        f"{directive} {' '.join(values)}"
        for directive, values in directives.items()
    )


class RequestRateLimiter:
    def __init__(self):
        self._requests = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key, limit, window_seconds):
        now = time.time()
        with self._lock:
            window = self._requests[key]
            cutoff = now - window_seconds
            while window and window[0] <= cutoff:
                window.popleft()

            if len(window) >= limit:
                retry_after = max(1, int(window_seconds - (now - window[0])))
                return False, retry_after

            window.append(now)
            return True, 0

    def reset(self):
        with self._lock:
            self._requests.clear()


request_rate_limiter = RequestRateLimiter()


def get_rate_limit_settings(scope, default_limit, default_window_seconds):
    overrides = app.config.get('RATE_LIMITS', {})
    route_config = overrides.get(scope, {}) if isinstance(overrides, dict) else {}
    limit = int(route_config.get('limit', default_limit))
    window_seconds = int(route_config.get('window_seconds', default_window_seconds))
    return max(limit, 1), max(window_seconds, 1)


def get_request_client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip() or 'unknown'
    return request.headers.get('X-Real-IP') or request.remote_addr or 'unknown'


def build_rate_limit_key(scope):
    return ':'.join(
        [
            scope,
            get_request_client_ip(),
            get_current_user_id() or 'anon',
        ]
    )


def build_rate_limit_response(retry_after):
    message = 'Too many requests. Please retry later.'
    if request.is_json or request.path.startswith('/studio/api/'):
        response = jsonify(message=message)
    else:
        response = app.response_class(message, status=429, mimetype='text/plain')
    response.status_code = 429
    response.headers['Retry-After'] = str(retry_after)
    return response


def rate_limit(scope, default_limit, default_window_seconds=60):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            limit, window_seconds = get_rate_limit_settings(scope, default_limit, default_window_seconds)
            allowed, retry_after = request_rate_limiter.allow(
                build_rate_limit_key(scope),
                limit,
                window_seconds,
            )
            if not allowed:
                return build_rate_limit_response(retry_after)
            return func(*args, **kwargs)

        return wrapped

    return decorator


@app.after_request
def apply_security_headers(response):
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Content-Security-Policy', build_content_security_policy())
    if get_app_env() == 'production':
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response


def normalize_step_args(steps, args):
    clean_steps = [str(step).strip() for step in (steps or []) if str(step).strip()]
    clean_args = [str(arg).strip() for arg in (args or []) if str(arg).strip()]
    if len(clean_steps) != len(clean_args):
        raise ValueError('Steps_and_Arguments_are_not_match.')
    if not clean_steps:
        raise ValueError('At least one step is required.')
    return clean_steps, clean_args


def build_task_record(task_name, url, crawl_method, noti_email, steps, args, user_id, task_id, schedule_enabled=True):
    res = {
        'task_name': str(task_name or '').strip(),
        'url': str(url or '').strip(),
        'c_method': str(crawl_method or '').strip(),
        'noti_email': str(noti_email or '').strip(),
        'schedule_enabled': normalize_boolean(schedule_enabled, default=True),
        'steps': steps,
        'args': args,
        'user_id': user_id,
        'task_id': task_id,
        'created_at': str(dateparser.parse('today').date()),
    }
    if user_id and user_id == 'auth0|60f28997680b890068f4bea7':
        res['demo'] = utc_now()
    return res


def enqueue_task(task_id):
    return subprocess.check_output(
        [get_python_command(), str(get_script_path('celery_task1.py')), '--task', task_id],
        universal_newlines=True,
    )


def enqueue_preview(payload):
    return subprocess.check_output(
        [get_python_command(), str(get_script_path('celery_task1.py')), '--preview', payload],
        universal_newlines=True,
    )


def cache_preview(preview_payload):
    return subprocess.run(
        [get_python_command(), str(get_script_path('main.py')), '--temphtml', preview_payload],
        check=True,
    )


def fetch_cached_preview_html(preview_id, user_id=None):
    cached = list(db.preview_contents.find(build_preview_cache_query(preview_id, user_id)).limit(1))
    if not cached:
        return None
    return cached[0].get('contents')

@app.errorhandler(Exception)
def handle_auth_error(ex):
    response = jsonify(message=str(ex))
    response.status_code = (ex.code if isinstance(ex, HTTPException) else 500)
    return response


oauth = OAuth(app)

auth0 = None
if is_auth0_configured():
    auth0 = oauth.register(
        'auth0',
        client_id=AUTH0_CLIENT_ID,
        client_secret=AUTH0_CLIENT_SECRET,
        api_base_url=AUTH0_BASE_URL,
        access_token_url=AUTH0_BASE_URL + '/oauth/token',
        authorize_url=AUTH0_BASE_URL + '/authorize',
        client_kwargs={
            'scope': 'openid profile email',
        },
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if is_local_mode():
            session[constants.PROFILE_KEY] = get_local_profile()
            return f(*args, **kwargs)
        if constants.PROFILE_KEY not in session:
            return redirect('/login')
        return f(*args, **kwargs)

    return decorated


# Controllers API
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/callback')
def callback_handling():
    if auth0 is None:
        return "Auth0 is not configured", 503
    auth0.authorize_access_token()
    resp = auth0.get('userinfo')
    userinfo = resp.json()

    session[constants.JWT_PAYLOAD] = userinfo
    session[constants.PROFILE_KEY] = {
        'user_id': userinfo['sub'],
        'name': userinfo['name'],
        'email': userinfo['email'],
        'picture': userinfo['picture']
    }
    return redirect(url_for('contents'))


@app.route('/login')
def login():
    if is_local_mode():
        session[constants.PROFILE_KEY] = get_local_profile()
        return redirect(url_for('contents'))
    if auth0 is None:
        return "Auth0 is not configured", 503
    return auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL, audience=AUTH0_AUDIENCE)


@app.route('/contents', methods=['POST','GET'])
@requires_auth
@rate_limit('contents', 60)
def contents():
    if request.method == 'POST':
        if not is_valid_form_token(request.form.get('token')):
            return "Bad Request", 400
        try:
            steps, args = normalize_step_args(request.form.getlist('steps[]'), request.form.getlist('args[]'))
        except ValueError:
            error = 'Steps_and_Arguments_are_not_match.'
            return redirect(url_for('contents', error=error))
        res = build_task_record(
            request.form.get('task_name'),
            request.form.get('url'),
            request.form.get('c_method'),
            request.form.get('noti_email'),
            steps,
            args,
            session[constants.PROFILE_KEY]['user_id'],
            session['form_token'],
            schedule_enabled=request.form.get('schedule_enabled'),
        )
        db.urls.insert_one(res)

        # add tasks into queue and chaining with pipe
        try:
            enqueue_task(res['task_id'])
        except:
            pass

        msg = 'success'

        return redirect(url_for('contents', msg=msg))
        
    else:
        results = db.urls.find(
            {"user_id": session[constants.PROFILE_KEY]['user_id']}).sort("_id", -1)
        form_token = generate_task_token()
        session['form_token'] = form_token
        return render_template('add_contents.html', userinfo=session[constants.PROFILE_KEY],
                                records=results, formtoken=session['form_token'])


@app.route('/temphtml', methods=['POST'])
@requires_auth
@rate_limit('temphtml', 30)
def temphtml():
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('preview_id') or not data.get('url'):
            return "Missing preview_id or url", 400
        if not is_valid_preview_token(data.get('preview_id')):
            return "Invalid preview token", 400
        method = data.get('c_method', 'py_requests')
        preview_payload = build_preview_cache_payload(
            data['preview_id'],
            data['url'],
            method,
            get_current_user_id(),
        )
        try:
            cache_preview(preview_payload)
            return "success", 200
        except subprocess.CalledProcessError:
            return "Failed to cache preview content", 500


@app.route('/preview', methods=['POST'])
@requires_auth
@rate_limit('preview', 20)
def preview():
    if request.method == 'POST':
        data = request.get_json()
        required_keys = ('preview_id', 'steps', 'args', 'c_method', 'url')
        if not data or not all(k in data for k in required_keys):
            return "Missing required fields", 400
        if not is_valid_preview_token(data.get('preview_id')):
            return "Invalid preview token", 400

        try:
            steps, args = normalize_step_args(data.get('steps'), data.get('args'))
        except ValueError as ex:
            return str(ex), 400

        preview_payload = build_preview_run_payload(
            data['preview_id'],
            steps,
            args,
            data['c_method'],
            data['url'],
            get_current_user_id(),
        )

        # add task to queue
        try:
            ret = enqueue_preview(preview_payload)
            return str(ret), 200
        except:
            return "Crawler is having difficulty", 500


@app.route('/run_contents/<tid>', methods=['POST'])
@requires_auth
@rate_limit('run_contents', 30)
def run_contents(tid):
    if not is_valid_form_token(request.form.get('token')):
        return "Bad Request", 400

    user_id = session[constants.PROFILE_KEY]['user_id']
    record = db.urls.find_one({'task_id': tid, 'user_id': user_id}, {'task_id': 1})
    if not record:
        return redirect(url_for('contents', error='Task_not_found.'))

    try:
        enqueue_task(tid)
        return redirect(url_for('contents', msg='queued'))
    except Exception:
        return redirect(url_for('contents', msg='queue_failed'))


@app.route('/schedule_contents/<tid>', methods=['POST'])
@requires_auth
@rate_limit('schedule_contents', 30)
def schedule_contents(tid):
    if not is_valid_form_token(request.form.get('token')):
        return "Bad Request", 400

    user_id = session[constants.PROFILE_KEY]['user_id']
    schedule_enabled = normalize_boolean(request.form.get('schedule_enabled'), default=True)
    ret = db.urls.update_one(
        {'task_id': tid, 'user_id': user_id},
        {'$set': {'schedule_enabled': schedule_enabled}},
    )

    if ret.matched_count != 1:
        return redirect(url_for('contents', error='Task_not_found.'))

    msg = 'schedule_enabled' if schedule_enabled else 'schedule_paused'
    return redirect(url_for('contents', msg=msg))


@app.route('/del_contents/<tid>', methods=['GET'])
@requires_auth
def del_contents(tid):
    if request.method == 'GET':
        user_id = session[constants.PROFILE_KEY]['user_id']
        ret = db.urls.delete_one({"task_id": tid, "user_id": user_id})
        if ret.deleted_count == 1:
            db.contents.delete_many({"task_id": tid})
            db.preview_contents.delete_many(build_preview_cache_query(tid, user_id))
            try:
                os.remove(str(get_downloads_dir() / (tid + '.csv')))
            except:
                pass
        msg = 'deleted'
        return redirect(url_for('contents',msg=msg))


@app.route('/dw_csv/<tid>', methods=['GET'])
@requires_auth
def dw_csv(tid):
    if request.method == 'GET':
        user_id = session[constants.PROFILE_KEY]['user_id']
        ret = db.urls.find({"task_id": tid, "user_id": user_id})
        if len(list(ret)) != 0:
            filename = tid + '.csv'
            return send_from_directory(str(get_downloads_dir()), filename, as_attachment=True)
        return "No file found", 404


@app.route('/logout')
def logout():
    session.clear()
    if is_local_mode() or auth0 is None:
        return redirect(url_for('home'))
    params = {'returnTo': AUTH0_LOGOUT_REDIRECT_URL, 'client_id': AUTH0_CLIENT_ID}
    return redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))


@app.route('/dashboard')
@requires_auth
def dashboard():
    userinfo_pretty = json.dumps(session.get(constants.JWT_PAYLOAD, session.get(constants.PROFILE_KEY, {})), indent=4)
    return render_template('dashboard.html',
                           userinfo=session[constants.PROFILE_KEY],
                           userinfo_pretty=userinfo_pretty)


@app.route('/studio')
@requires_auth
def studio():
    if not is_studio_enabled():
        return 'Studio is disabled', 404

    studio_token = generate_task_token('studio-')
    session['studio_token'] = studio_token
    userinfo = session[constants.PROFILE_KEY]
    return render_template(
        'studio.html',
        userinfo=userinfo,
        studio_state=build_studio_state(userinfo, studio_token),
        studio_catalog=get_studio_method_catalog(),
    )


@app.route('/studio/api/task', methods=['POST'])
@requires_auth
@rate_limit('studio_task', 30)
def studio_task():
    if not is_studio_enabled():
        return jsonify(message='Studio is disabled'), 404

    try:
        payload = validate_studio_payload(request.get_json())
    except ValueError as ex:
        return jsonify(message=str(ex)), 400

    task_id = generate_task_token('studio-task-')
    userinfo = session[constants.PROFILE_KEY]
    record = build_task_record(
        payload['task_name'],
        payload['url'],
        payload['c_method'],
        payload['noti_email'],
        payload['steps'],
        payload['args'],
        userinfo['user_id'],
        task_id,
        schedule_enabled=payload.get('schedule_enabled', True),
    )
    db.urls.insert_one(record)

    try:
        enqueue_task(task_id)
        return jsonify(
            status='queued',
            task_id=task_id,
            message='Studio task saved and queued.',
            redirect_url=url_for('contents', msg='success'),
        ), 200
    except Exception:
        return jsonify(
            status='saved',
            task_id=task_id,
            message='Studio task saved, but queue dispatch failed.',
            redirect_url=url_for('contents'),
        ), 202


@app.route('/studio/api/inspector', methods=['POST'])
@requires_auth
@rate_limit('studio_inspector', 30)
def studio_inspector():
    if not is_studio_enabled():
        return jsonify(message='Studio is disabled'), 404

    payload = request.get_json() or {}
    preview_id = str(payload.get('preview_id', '')).strip()
    target_url = str(payload.get('url', '')).strip()
    selected_method = str(payload.get('c_method', '')).strip() or 'py_requests'
    force_refresh = bool(payload.get('force_refresh'))

    if not preview_id:
        return jsonify(message='Missing preview_id'), 400
    if not target_url.startswith(('http://', 'https://')):
        return jsonify(message='Target URL must start with http:// or https://'), 400
    if not is_valid_preview_token(preview_id):
        return jsonify(message='Invalid preview token'), 400

    try:
        user_id = get_current_user_id()
        cached_html = None if force_refresh else fetch_cached_preview_html(preview_id, user_id=user_id)
        if not cached_html:
            cache_preview(build_preview_cache_payload(preview_id, target_url, selected_method, user_id))
            cached_html = fetch_cached_preview_html(preview_id, user_id=user_id)

        if not cached_html:
            return jsonify(message='Inspector snapshot is unavailable'), 404

        return jsonify(build_inspector_response(preview_id, selected_method, cached_html, target_url)), 200
    except subprocess.CalledProcessError:
        return jsonify(message='Failed to build inspector snapshot'), 500


@app.route('/studio/api/copilot', methods=['POST'])
@requires_auth
@rate_limit('studio_copilot', 12)
def studio_copilot():
    if not is_studio_enabled():
        return jsonify(message='Studio is disabled'), 404

    payload = request.get_json() or {}

    try:
        return jsonify(
            suggest_studio_copilot_plan(
                payload.get('goal'),
                payload.get('url'),
                payload.get('c_method'),
                current_nodes=payload.get('nodes') if isinstance(payload.get('nodes'), list) else None,
                database=db,
            )
        ), 200
    except ValueError as ex:
        return jsonify(message=str(ex)), 400


@app.route('/studio/api/selector-memory', methods=['POST'])
@requires_auth
@rate_limit('studio_selector_memory', 30)
def studio_selector_memory():
    if not is_studio_enabled():
        return jsonify(message='Studio is disabled'), 404

    payload = request.get_json() or {}
    target_url = str(payload.get('url', '')).strip()
    selected_method = str(payload.get('c_method', '')).strip()

    if not target_url.startswith(('http://', 'https://')):
        return jsonify(message='Target URL must start with http:// or https://'), 400
    if selected_method not in get_studio_method_catalog():
        return jsonify(message='Unsupported crawl method'), 400

    return jsonify(get_selector_memory_summary(target_url, selected_method, database=db)), 200


if __name__ == "__main__":
    app.run(port=env.get('APP_PORT', 3000))
