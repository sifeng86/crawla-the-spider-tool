# Crawla - The Premium AI Web Spider Tool

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sifeng86/crawla-the-spider-tool)

Crawla is an advanced, AI-powered web spider tool designed to simplify data extraction. Built with a stunning modern Glassmorphism interface, it allows developers and data engineers to configure crawlers visually without dealing with complex code.

With the latest 2.0 update, Crawla introduces **LLM Self-Healing** (auto-fixing broken selectors) and **Smart Data Extraction** (JSON Schema parsing) directly powered by Google Gemini AI, along with parallel processing for ultra-fast scraping.

Demo: https://crawla.cachigo.com

## ✨ Key Features
* **Set & Go Architecture**: Fully containerized with MongoDB, Redis, and Selenium Chrome included. Local Docker mode starts with built-in defaults.
* **Premium UX/UI**: Beautiful Glassmorphism design, full Dark Mode support, and interactive Skeleton Loaders.
* **LLM Self-Healing**: Automatically repairs broken CSS selectors using Gemini AI when websites update their layout.
* **Smart Data Extraction**: Pass a JSON Schema and let LLM parse unstructured pages into perfect JSON automatically.
* **High-Speed Concurrency**: Uses `ThreadPoolExecutor` to crawl multiple URLs simultaneously.
* **4 Extraction Engines**: Choose between ⚡ Requests (BS4), 🌐 Selenium, 🎭 Playwright, or 🧠 LLM AI extraction.

## 🚀 Getting Started (Set & Go)

### Prerequisites
* Docker with Compose support
* Google Gemini API Key (Optional — only required for LLM features)

### One-Command Local Start

**Step 1 — Start the application**
```bash
docker compose up -d --build
```

That's enough for local mode.
* Open your browser to `http://localhost:3000`
* Click `Get Started`, then local mode signs you in as Local Admin.
* MongoDB, Redis, Selenium Chrome, and the Celery worker are all managed by Docker.

**Step 2 — (Optional) Configure LLM features**

For AI-powered extraction, set `GOOGLE_API_KEY` in your shell before starting Docker, or create `login/setting/config.json` from the example file for advanced LLM configuration:
```bash
cp login/setting/config_example.json login/setting/config.json
```
Then insert your `google_api_key` under `llm.gemini.api_key`.
For faster preview responses with compatible Gemini/Gemma models, you can also set `llm.gemini.thinking_level` to `MINIMAL` in `login/setting/config.json`.

**Step 3 — (Optional) File-based app settings**
```bash
cp login/.env_example login/.env
```

---

## 🛠 Advanced Configuration (Production)

Change `APP_ENV=production` in `login/.env` and configure Auth0 to enable full authentication.

### Auth0 Configuration (Production only)
In `login/.env`, fill in:
```env
APP_ENV=production
AUTH0_CLIENT_ID=your_client_id
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_SECRET=your_secret
AUTH0_CALLBACK_URL=https://your-domain.com/callback
AUTH0_LOGOUT_REDIRECT_URL=https://your-domain.com/
```

### MongoDB Atlas (Production only)
To use a managed Atlas cluster instead of the bundled MongoDB, set in `login/setting/config.json`:
```json
{
  "mongo_mode": "atlas",
  "atlas_host": "cluster.mongodb.net",
  "atlas_db": "crawla",
  "atlas_user": "username",
  "atlas_pw": "encrypted_password"
}
```
Atlas passwords must be encrypted. Inside the Docker container, run:
```bash
docker exec -it crawla_web bash
python key_generator.py     # generates login/key/secret.key
python encrypt_token.py     # encrypts your plaintext password
```

### Periodic Jobs (Crontab)
Schedule automated crawl runs via crontab:
```bash
# Run all tasks every day at 1 AM
0 1 * * * docker exec -t crawla_web python ./main.py --all >> /log/crawla.log 2>&1
```

Options:
* `--all` — all tasks
* `--py_requests` — Requests/BS4 tasks only
* `--py_selenium` — Selenium tasks only
* `--py_playwright` — Playwright tasks only
* `--py_llm` — LLM tasks only
* `--task TASKID` — specific task by ID
* `--user USERID` — latest task for a specific user

---

## 💡 Extraction Methods

### ⚡ Requests (BS4)
Fast HTTP requests + BeautifulSoup CSS/tag selectors. Best for static pages with no JavaScript rendering.

### 🌐 Selenium
Full Chrome browser automation. Use for pages that require JavaScript execution or user interaction (click, scroll, form fill).

### 🎭 Playwright
Modern browser automation — faster and lighter than Selenium with superior anti-detection. Supports the same step types as Selenium.

### 🧠 LLM (AI-Powered)
Uses Google Gemini to extract data from the page. Two modes:

**Standard Prompt**: Enter any natural language question in the Arguments field.
> *Example: "What is the price of the product?"*

**Smart Data Extraction (JSON Schema)**: Enter a valid JSON Schema (must start with `{` and include `"type"`). Crawla prompts Gemini to extract the page content directly into your requested JSON format.
> *Example: `{"type": "object", "properties": {"title": {"type": "string"}, "price": {"type": "number"}}}`*

LLM tasks can be saved and scheduled just like other methods.

---

## 🔧 LLM Self-Healing

When a BS4 navigation step (e.g., `select_one("#price > span")`) fails to find an element, Crawla automatically:
1. Extracts the surrounding HTML snippet from the page.
2. Sends it to Gemini with the failing selector.
3. Gemini suggests a new working selector.
4. Crawla retries the step with the healed selector.

This is automatic for the BeautifulSoup flow. Browser-driven self-healing is not enabled yet.

---

## 🏗 Architecture

```
login/server.py      → Flask Web UI + REST API
main.py              → Crawler engine (ThreadPoolExecutor concurrency)
celery_task1.py      → Async task queue (Celery + Redis)
login/lib/
  ├── mongo.py       → MongoDB connection (pooled, Atlas + local)
  ├── celery.py      → Redis/Celery connection helper
  ├── step_helper.py → Safe step dispatch (BS4 / Selenium / Playwright)
  ├── llm_handler.py → Gemini AI (caching, self-healing, smart extraction)
  ├── stealth.py     → Anti-detection (UA rotation, stealth scripts)
  ├── rate_limiter.py→ Per-domain rate limiting (thread-safe)
  └── playwright_helper.py → Playwright stealth context manager
```

**Infrastructure (Docker Compose):**
| Service | Image | Port |
|---------|-------|------|
| `crawla_web` | Python 3.12 + Flask + Celery | 3000 |
| `crawla_mongo` | mongo:6.0 | 27017 (internal) |
| `crawla_redis` | redis:7.4-alpine | 6379 (internal) |
| `crawla_chrome` | selenium/standalone-chrome:131 | 4444 (internal) |

---

## 📝 License
This project is licensed under the Apache License 2.0 - see the LICENSE.txt file for details.

## 🤝 Authors
* Alan Gan
* UI/UX & Core Optimizations by Antigravity
