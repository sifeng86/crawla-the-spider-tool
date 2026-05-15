#!/bin/bash
set -euo pipefail

start_web() {
	if [[ "${CRAWLA_WEB_SERVER:-auto}" == "gunicorn" || "${APP_ENV:-local}" == "production" ]]; then
		gunicorn --config /work/gunicorn.conf.py --chdir /work/login "server:app" &
	else
		flask run --host=0.0.0.0 --port="${APP_PORT:-3000}" &
	fi
	web_pid=$!
}

shutdown() {
	kill -TERM "${web_pid:-0}" "${celery_pid:-0}" 2>/dev/null || true
}

celery -A celery_task1 worker --loglevel=info --without-gossip --without-mingle &
celery_pid=$!

start_web

trap shutdown INT TERM

wait -n "$web_pid" "$celery_pid"
status=$?

shutdown
wait "$web_pid" "$celery_pid" 2>/dev/null || true

exit "$status"
