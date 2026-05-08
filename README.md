# Crawla - Build Scheduled Crawlers Faster

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sifeng86/crawla-the-spider-tool)

Crawla is a Docker-first scraping tool for turning a target page into a repeatable crawler quickly, then running it again on demand or on a schedule. It combines Requests/BS4, Selenium, Playwright, and optional Gemini-assisted extraction behind a web UI, a Studio workspace, and a CLI runtime.

The product focus is practical: help users find the right selector faster, keep crawlers alive when layouts drift, and make recurring extraction jobs easier to maintain. AI is used as an accelerator for narrow tasks, not as the default execution engine for the whole site.

Demo: https://crawla.cachigo.com

## Documentation

If you are starting from scratch, read these guides in this order:

* [docs/OPERATING_GUIDE.md](docs/OPERATING_GUIDE.md) - end-to-end local setup, screen-by-screen usage, extraction methods, preview flow, Studio flow, scheduling, and troubleshooting.
* [docs/AUTH0_SETUP.md](docs/AUTH0_SETUP.md) - step-by-step Auth0 setup for staging or production.

## What Crawla Is Good At

Crawla is strongest when you need to build and keep running a crawler for a page that changes over time.

Typical examples:
* Repeatedly scraping a specific block such as lottery results, exchange rates, notices, or article headlines.
* Building a browser-based crawler for pages that require clicks, waits, or JS rendering.
* Recovering from drifting selectors when class names or DOM paths change.
* Turning semi-structured pages into strict JSON with a small LLM prompt or schema.
* Saving a task once and re-running it manually, from the queue, or from a scheduler.

## Current Status

### Available Now
* Docker-first local stack with Flask, MongoDB, Redis, Selenium Chrome, and Celery.
* Four extraction methods: Requests/BS4, Selenium, Playwright, and LLM extraction.
* Step-based execution for Requests, Selenium, and Playwright.
* Studio workspace route with method catalog, draft schema, and task save/queue flow.
* Visual Inspector API for cached-preview or live-browser element picking and selector candidate generation.
* AI Copilot API for draft flow planning, including selector-memory grounding.
* Selector Memory for domain-scoped selector reuse across successful runs.
* Runtime selector repair pipeline for Requests, Selenium, and Playwright.
* JSON Schema based smart extraction for `py_llm`.
* CLI and scheduler-friendly task execution through `main.py`.

### Partial
* Studio UI is usable as a guided workspace, but it is still evolving toward a more complete authoring experience.
* Copilot can draft flows and reuse selector memory, but it does not replace user-owned flow design.
* Run event schema exists for richer debugging, but full live debugger visibility is not shipped yet.

### Deliberately Not In The Near-Term Plan
* High-frequency runtime AI orchestration that would materially increase LLM cost.
* Automatic runtime step completion that silently inserts missing steps.
* Teaching-mode healing that depends on frequent extra LLM calls during execution.

## Key Features

* **Set & Go Architecture**: Fully containerized local mode with built-in defaults.
* **4 Extraction Engines**: Use the cheapest runtime that fits the job, then escalate only when needed.
* **Selector Memory**: Successful selectors are stored by domain, method, and step for future reuse.
* **Runtime Self-Healing**: Requests, Selenium, and Playwright flows try memory, heuristics, and finally LLM repair when a locator fails.
* **Visual Inspector**: Generate CSS, XPath, and attribute candidates from either cached HTML or a browser-rendered DOM snapshot instead of guessing selectors manually.
* **AI Copilot**: Draft starter flows from a goal, URL, and runtime, grounded by method templates and selector memory.
* **Smart Data Extraction**: Use a prompt or strict JSON Schema with `py_llm` for semi-structured pages.
* **Concurrency & Scheduling**: Run tasks in parallel and schedule recurring crawls through CLI or queue workflows.

## Cost-Aware AI Principles

Crawla is designed for low-cost AI usage rather than LLM-first execution.

* Prefer `py_requests` or `py_playwright` plus Inspector and selector memory before reaching for `py_llm`.
* Use selector memory and heuristic fallbacks before LLM selector repair.
* Keep LLM tasks narrow: one selector fix, one schema extraction, one short planning output.
* Default to lighter models and small output budgets whenever possible.
* Keep Gemini optional. Local mode works without LLM features enabled.

Recommended Gemini settings for cost control:
* `model`: use a light/fast model such as Gemini Flash class models.
* `thinking_level`: set to `MINIMAL` when supported.
* `max_output_tokens`: set a low ceiling for narrow tasks.

## Quick Start

### Prerequisites
* Docker with Compose support
* Google Gemini API Key only if you want LLM-based features
* WSL or another Unix-like shell if you want to use the `cp` examples as written on Windows

### Local Mode

**Step 1 - Start the stack**
```bash
docker compose up -d --build
```

That is enough for local mode.
* Open `http://localhost:3000`
* Click `Get Started`
* Local mode signs you in as Local Admin
* MongoDB, Redis, Selenium Chrome, and Celery are managed by Docker

**Step 2 - Optional app settings**

WSL / macOS / Linux:
```bash
cp login/.env_example login/.env
```

PowerShell:
```powershell
Copy-Item login/.env_example login/.env
```

**Step 3 - Optional LLM settings**

WSL / macOS / Linux:
```bash
cp login/setting/config_example.json login/setting/config.json
```

PowerShell:
```powershell
Copy-Item login/setting/config_example.json login/setting/config.json
```

Then add your Gemini API key under `llm.gemini.api_key`.

For lower-cost LLM usage, prefer settings like:
```json
{
  "llm": {
    "gemini": {
      "model": "gemini-2.5-flash-preview-04-17",
      "thinking_level": "MINIMAL",
      "max_output_tokens": 512
    }
  }
}
```

## Core Workflow

The intended workflow is straightforward:

1. Pick the cheapest runtime that can solve the page.
2. Load a preview or browser view.
3. Use Inspector to generate selector candidates instead of writing them blind.
4. Save a task with visible steps and arguments.
5. Re-run it manually, from the queue, or from a scheduler.
6. Let selector memory and runtime healing reduce maintenance when the site drifts.

For recurring pages such as lottery results, notices, or price blocks, this is the main value of Crawla today.

## Web UI Map

* `/login` - local mode creates a `Local Admin` session automatically; production and staging redirect to Auth0.
* `/contents` - classic builder for step-based task creation, previews, saved-task controls, schedule toggling, and CSV download.
* `/studio` - visual workspace with method cards, draft payload, inspector, copilot, flow editor, and selector-memory panels.
* `/dashboard` - signed-in profile summary.

For a full walkthrough of each screen, see [docs/OPERATING_GUIDE.md](docs/OPERATING_GUIDE.md).

## Authentication Modes

### Local Mode

`docker compose up -d --build` defaults to `APP_ENV=local`, so clicking `Get Started` signs you in as `Local Admin`. This is the intended development mode.

### Staging / Production Mode

Set `APP_ENV=production` and provide the Auth0 settings in `login/.env`. Crawla will then redirect `/login` to Auth0, create a session from the returned user profile, and scope saved tasks by that user id.

Each authenticated user sees only their own tasks, previews, and Studio saves.

See [docs/AUTH0_SETUP.md](docs/AUTH0_SETUP.md) for the complete setup flow.

## Extraction Methods

### Requests / BS4

Fast HTTP requests with BeautifulSoup selectors. Best for static pages, low-cost previews, and broad recurring crawls.

### Selenium

Remote Chrome browser automation. Best when you need compatibility with existing browser-oriented steps or interaction flows.

### Playwright

The primary Studio browser runtime for richer locators and future stateful flows. Best for JS-heavy pages, clicks, waits, and modern browser automation.

### LLM Extraction

Gemini-backed extraction for pages that are noisy or semi-structured.

Supported modes:
* **Prompt mode**: ask a direct question in the argument field.
* **JSON Schema mode**: provide a strict schema and return structured JSON.

Use `py_llm` when schema extraction is the simplest path, not as the default answer for every site.

## Studio Workspace

Studio is the product direction for building crawlers faster while keeping the final flow visible and editable.

### Available Now
* `/studio` workspace shell and draft schema.
* Method catalog with starter nodes for each runtime.
* `/studio/api/inspector` for selector picking from cached HTML or live browser DOM snapshots.
* Inspector uses cached HTML for `py_requests` and `py_llm`, and browser-rendered DOM snapshots for `py_selenium` and `py_playwright`.
* `/studio/api/copilot` for goal-to-flow draft generation.
* `/studio/api/selector-memory` for domain-level selector memory summaries.
* Studio task save and queue dispatch flow.

### Partial
* The workspace already supports draft planning and selector-guided authoring, but it is not yet a fully stateful multi-step browser IDE.
* Copilot drafts are grounded and useful, but they are still suggestions that users should review and own.

### Coming Later
* Richer stateful flow authoring.
* Better run visibility and healing traces.
* Broader productized integrations around notifications and operational workflows.

## Selector Memory And Runtime Healing

When a self-healable navigation step fails, Crawla does not jump straight to LLM.

Current recovery order:
1. Try selector memory from previous successful runs on the same domain.
2. Try deterministic heuristic fallback candidates derived from the failed selector.
3. Only then ask Gemini for a replacement parameter.
4. Retry the step with the recovered parameter and store the success back into selector memory.

This applies to step-based Requests, Selenium, and Playwright flows. It repairs wrong or drifting locator parameters, but it does not generate missing runtime steps.

## Scheduling And Automation

Tasks can be saved and run through the app or invoked directly through `main.py`.

The saved-task list now supports two low-cost control points that make recurring crawls easier to manage:

* `Run now` queues a saved task immediately without changing its schedule status.
* Scheduled batch runs only execute tasks where `schedule_enabled` is not set to `false`, so a task can be paused without deleting it.

Example crontab:
```bash
# Run all tasks every day at 1 AM
0 1 * * * docker exec -t crawla_web python ./main.py --all >> /log/crawla.log 2>&1
```

CLI options:
* `--all` - all tasks
* `--py_requests` - Requests/BS4 tasks only
* `--py_selenium` - Selenium tasks only
* `--py_playwright` - Playwright tasks only
* `--py_llm` - LLM tasks only
* `--task TASKID` - specific task by ID
* `--user USERID` - latest task for a specific user

## Advanced Configuration

### Auth0 For Production

Set `APP_ENV=production` in `login/.env` and configure Auth0.

```env
APP_ENV=production
AUTH0_CLIENT_ID=your_client_id
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_SECRET=your_secret
AUTH0_CALLBACK_URL=https://your-domain.com/callback
AUTH0_LOGOUT_REDIRECT_URL=https://your-domain.com/
```

Use a Regular Web Application in Auth0. The callback URL must exactly match `AUTH0_CALLBACK_URL`, and the logout URL must exactly match `AUTH0_LOGOUT_REDIRECT_URL`.

For the full checklist, including verification steps, see [docs/AUTH0_SETUP.md](docs/AUTH0_SETUP.md).

### MongoDB Atlas

To use Atlas instead of the bundled MongoDB, update `login/setting/config.json`:

```json
{
  "mongo_mode": "atlas",
  "atlas_host": "cluster.mongodb.net",
  "atlas_db": "crawla",
  "atlas_user": "username",
  "atlas_pw": "encrypted_password"
}
```

Atlas passwords must be encrypted. Inside the Docker container:
```bash
docker exec -it crawla_web bash
python key_generator.py
python encrypt_token.py
```

## Architecture

```text
login/server.py      -> Flask web UI + Studio/API routes
main.py              -> Crawler engine + selector healing pipeline
celery_task1.py      -> Async task queue (Celery + Redis)
login/lib/
  mongo.py           -> MongoDB connection (Atlas + local)
  celery.py          -> Redis/Celery helper
  step_helper.py     -> Safe step dispatch for BS4 / Selenium / Playwright
  llm_handler.py     -> Gemini integration, caching, self-healing, schema extraction
  selector_memory.py -> Domain-scoped selector reuse and fallback ranking
  studio.py          -> Studio schema, method catalog, feature flags
  studio_inspector.py-> Cached-preview and browser-snapshot element picker
  studio_copilot.py  -> Goal-to-flow planning with selector-memory grounding
  stealth.py         -> Anti-detection helpers
  rate_limiter.py    -> Per-domain rate limiting
  playwright_helper.py -> Playwright stealth context manager
```

**Infrastructure (Docker Compose)**

| Service | Image | Port |
|---------|-------|------|
| `crawla_web` | Python 3.12 + Flask + Celery | 3000 |
| `crawla_mongo` | mongo:6.0 | 27017 (internal) |
| `crawla_redis` | redis:7.4-alpine | 6379 (internal) |
| `crawla_chrome` | selenium/standalone-chrome:131 | 4444 (internal) |

## Troubleshooting

### Local mode only shows `Local Admin`

That is expected when `APP_ENV=local`. To test real Auth0 login, switch to `APP_ENV=production` with valid `AUTH0_*` values. See [docs/AUTH0_SETUP.md](docs/AUTH0_SETUP.md).

### Buttons or method switches do nothing

Rebuild or restart the web container after pulling frontend changes:

```bash
docker compose up -d --build
```

If the app was already running before a template or JS change, use:

```bash
docker compose restart crawla_web
```

### Browser preview cannot reach a local target

When Selenium or Playwright runs inside Docker, `127.0.0.1` points at the browser container, not your host machine. Use a container-reachable target such as `http://crawla_web:3000/` when you are testing against the local stack.

## License

This project is licensed under the Apache License 2.0. See `LICENSE.txt` for details.

## Authors

* Alan Gan
* UI/UX and core optimizations by Antigravity
