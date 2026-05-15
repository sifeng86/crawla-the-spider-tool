# Crawla Auth0 Setup

This guide is for staging or production. Local Docker development uses `APP_ENV=local` and signs every visitor in as `Local Admin` by design.

## 1. Decide Which Mode You Want

### Local mode

Use this when you just want to develop or test crawler behavior quickly.

* `APP_ENV=local`
* `/login` creates a `local_admin` session
* no Auth0 redirect happens

### Staging or production mode

Use this when you want real user login.

* `APP_ENV=production`
* `/login` redirects to Auth0
* `/callback` creates the session from the Auth0 user profile
* saved tasks are scoped by Auth0 user id

## 2. Create The Auth0 Application

In Auth0:

1. Create or open your tenant.
2. Create a `Regular Web Application`.
3. Copy the following values:
   * Client ID
   * Client Secret
   * Domain
4. Make sure your app is allowed to request `openid profile email`.

## 3. Configure URLs In Auth0

Set the following values in the Auth0 application settings.

### Allowed Callback URLs

Use the exact URL that Crawla will receive after login, for example:

```text
https://crawla.example.com/callback
```

### Allowed Logout URLs

Use the exact URL that Crawla should return to after logout, for example:

```text
https://crawla.example.com/
```

### Allowed Web Origins

Use your app origin, for example:

```text
https://crawla.example.com
```

If you have both staging and production, add both sets explicitly.

## 4. Fill `.env.production`

For Docker deployments, start from the production example file at the repository root:

```bash
cp .env.production.example .env.production
```

Then set:

```env
APP_ENV=production
SECRET_KEY=replace-with-a-long-random-secret
CRAWLA_STUDIO_ENABLED=true

AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CALLBACK_URL=https://crawla.example.com/callback
AUTH0_LOGOUT_REDIRECT_URL=https://crawla.example.com/
AUTH0_AUDIENCE=
```

Notes:

* `SECRET_KEY` is required in production mode.
* `AUTH0_AUDIENCE` is optional unless your Auth0 setup requires an API audience.
* `AUTH0_CALLBACK_URL` and `AUTH0_LOGOUT_REDIRECT_URL` must exactly match the values configured in Auth0.
* `login/.env` is still a fallback for direct non-Docker app runs, but Docker Compose production should use `.env.production` with `--env-file`.

## 5. Start Or Restart The Stack

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

If the stack is already running and you only changed environment or templates:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml restart crawla_web
```

## 6. Verify Login Flow

Test the full path:

1. Open `/login`.
2. Confirm the browser redirects to Auth0.
3. Sign in with a real Auth0 user.
4. Confirm Crawla returns to `/callback` and lands inside the app.
5. Confirm the UI shows that user's profile, not `Local Admin`.

## 7. Verify Logout Flow

1. Click `Logout`.
2. Confirm Crawla clears the session.
3. Confirm Auth0 returns the browser to `AUTH0_LOGOUT_REDIRECT_URL`.

## 8. Verify User Isolation

Each Auth0 user should only see their own data.

Manual check:

1. Log in as user A and create a task.
2. Log out.
3. Log in as user B.
4. Confirm user B does not see user A's task.

This same scoping also applies to preview cache access and Studio task saves.

## 9. Common Mistakes

### The app still shows `Local Admin`

You are still in local mode. Check that `APP_ENV=production` is actually loaded inside the running web container.

### `/login` returns `Auth0 is not configured`

One or more required values are empty:

* `AUTH0_CLIENT_ID`
* `AUTH0_CLIENT_SECRET`
* `AUTH0_DOMAIN`
* `AUTH0_CALLBACK_URL`
* `AUTH0_LOGOUT_REDIRECT_URL`

### Auth0 login works, but the callback fails

Usually one of these is wrong:

* callback URL mismatch between Auth0 and `AUTH0_CALLBACK_URL`
* wrong application type in Auth0
* tenant domain copied incorrectly

### Logout returns to the wrong place

Check `AUTH0_LOGOUT_REDIRECT_URL` and make sure the same exact URL is listed in Auth0 Allowed Logout URLs.