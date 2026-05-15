import os


def _int_setting(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _positive_int_setting(name: str, default: int, minimum: int = 1) -> int:
    return max(_int_setting(name, default), minimum)


wsgi_app = 'server:app'
chdir = '/work/login'
bind = f"0.0.0.0:{os.getenv('APP_PORT', '3000')}"
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')
workers = _positive_int_setting('GUNICORN_WORKERS', 2)
threads = _positive_int_setting('GUNICORN_THREADS', 4)
timeout = _positive_int_setting('GUNICORN_TIMEOUT', 120)
graceful_timeout = _positive_int_setting('GUNICORN_GRACEFUL_TIMEOUT', 30)
keepalive = _positive_int_setting('GUNICORN_KEEPALIVE', 5)
max_requests = _positive_int_setting('GUNICORN_MAX_REQUESTS', 1000)
max_requests_jitter = max(_int_setting('GUNICORN_MAX_REQUESTS_JITTER', 100), 0)
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
accesslog = '-'
errorlog = '-'
capture_output = True
worker_tmp_dir = '/dev/shm'
preload_app = False
proc_name = 'crawla-web'