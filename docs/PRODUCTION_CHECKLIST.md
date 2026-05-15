# Crawla Production Checklist

Use this checklist when you are about to ship Crawla behind a real domain.

## 1. Prepare the Docker env file

1. Copy `.env.production.example` to `.env.production`.
2. Fill the required app and Auth0 values.
3. Keep sensitive values in environment variables or `*_FILE` variables.

Recommended command:

```bash
cp .env.production.example .env.production
```

## 2. Fill the required values

Required:

* `APP_ENV=production`
* `SECRET_KEY`
* `AUTH0_CLIENT_ID`
* `AUTH0_CLIENT_SECRET`
* `AUTH0_DOMAIN`
* `AUTH0_CALLBACK_URL`
* `AUTH0_LOGOUT_REDIRECT_URL`

Optional but common:

* `AUTH0_AUDIENCE`
* `CRAWLA_STUDIO_ENABLED`
* `GOOGLE_API_KEY` or `GOOGLE_API_KEY_FILE`
* `CRAWLA_WEB_SERVER=gunicorn`

## 3. Choose your secret style

Simplest:

* put the secret directly in `.env.production`

Safer:

* put the secret in a file managed by Docker or your host
* point the app at that file with `*_FILE`

Examples:

* `CRAWLA_ATLAS_PASSWORD_FILE=/run/secrets/crawla_atlas_password`
* `CRAWLA_REDIS_PASSWORD_FILE=/run/secrets/crawla_redis_password`
* `CRAWLA_MAIL_PASSWORD_FILE=/run/secrets/crawla_mail_password`
* `GOOGLE_API_KEY_FILE=/run/secrets/crawla_google_api_key`

## 4. Pick your data services

Local container defaults:

* `CRAWLA_MONGO_MODE=local`
* `CRAWLA_REDIS_HOST_PORT=local`

Managed services:

* set `CRAWLA_MONGO_URI` for MongoDB Atlas or another hosted cluster
* set `CRAWLA_REDIS_URL` for hosted Redis

Legacy split settings still work, but the direct URI form is simpler.

## 5. Mail settings

Only fill these if you want email notifications:

* `CRAWLA_HOST_URL`
* `CRAWLA_MAIL_HOST`
* `CRAWLA_MAIL_PORT`
* `CRAWLA_MAIL_SENDER`
* `CRAWLA_MAIL_USER`
* `CRAWLA_MAIL_PASSWORD` or `CRAWLA_MAIL_PASSWORD_FILE`

## 6. Start the production stack

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

Notes:

* this compose file avoids the source bind mount from local development
* MongoDB, Redis, and Chrome are only exposed inside the Docker network
* web is bound to `127.0.0.1:${APP_PORT}` so you can place a reverse proxy in front
* the production template starts the app with Gunicorn using conservative defaults

## 6.1 Gunicorn defaults

The production template already includes a simple stable Gunicorn profile:

* `GUNICORN_WORKERS=2`
* `GUNICORN_THREADS=4`
* `GUNICORN_TIMEOUT=120`
* `GUNICORN_GRACEFUL_TIMEOUT=30`
* `GUNICORN_KEEPALIVE=5`
* `GUNICORN_MAX_REQUESTS=1000`
* `GUNICORN_MAX_REQUESTS_JITTER=100`

Raise workers later only if you have measured the load.

## 7. Verify Auth0

1. Open `/login`.
2. Confirm the browser redirects to Auth0.
3. Log in with a real user.
4. Confirm the UI does not show `Local Admin`.
5. Click `Logout` and confirm the browser returns to the configured logout URL.

## 8. Verify task isolation

1. Log in as user A.
2. Create a task.
3. Log out.
4. Log in as user B.
5. Confirm user B cannot see user A's task.

## 9. Verify crawler features

1. Open `/contents` and create a preview.
2. Save a task and run `Run now`.
3. Open `/studio` if Studio is enabled.
4. Run a Studio preview.
5. Download a CSV from the saved task list.

## 10. Run the regression suite

```bash
docker compose --env-file .env.production -f docker-compose.production.yml exec crawla_web python -m unittest discover -s tests -v
```

Only ship once this passes.

## 11. Keep in mind

* The image now uses Gunicorn in production mode, but you should still place it behind a real reverse proxy.
* The new env-first loader is the recommended path.
* `login/setting/config.json` is now best treated as an optional legacy fallback for non-sensitive defaults.
* If you previously stored a Gemini or mail secret in `config.json`, move it to environment variables or a `*_FILE` secret and clear the JSON value before shipping.