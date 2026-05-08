# Crawla Operator Guide

This guide explains the current product as it exists today: how to start it locally, what each screen does, how to create tasks, how previews behave, and how to use Studio without guessing.

## 1. Start The Local Stack

Prerequisites:

* Docker with Compose support
* Optional Gemini API key if you want LLM features

Start the stack:

```bash
docker compose up -d --build
```

Open `http://localhost:3000`, click `Get Started`, and you will land in local mode as `Local Admin`.

In local mode:

* Auth0 is bypassed intentionally.
* Every task belongs to `local_admin`.
* MongoDB, Redis, Selenium Chrome, and Celery are managed by Docker.

Optional config files:

```bash
cp login/.env_example login/.env
cp login/setting/config_example.json login/setting/config.json
```

On PowerShell, use `Copy-Item` instead of `cp`.

## 2. Screen Map

After login, the main routes are:

* `/contents` - classic task builder and saved-task list
* `/studio` - visual authoring workspace
* `/dashboard` - profile/session detail
* `/logout` - clears the current session

Use `/contents` if you want the fastest path to a working crawler. Use `/studio` if you want a more guided flow with inspector, copilot, and a visible node graph.

## 3. Classic Builder Walkthrough

The classic builder is the most direct way to create a task.

### Step 1 - Fill in task metadata

Required fields:

* `Task Name` - your internal label for the saved task
* `Notification Email` - recipient used by email-related flows
* `Url` - target page to preview and crawl

Optional but important:

* `Include this task in scheduled batch runs` - if enabled, `main.py --all` will include the task

### Step 2 - Choose an extraction method

Use the cheapest runtime that can solve the page:

* `Requests (BS4)` - best for static pages and low-cost previews
* `Selenium` - best if you already rely on Selenium-style browser steps
* `Playwright` - best for modern JS-heavy pages, clicks, waits, and richer browser automation
* `LLM` - best for prompt-based or schema-based extraction from noisy pages

### Step 3 - Configure steps

For `py_requests`, `py_selenium`, and `py_playwright`, each row has:

* `Action` - the step function to execute
* `Arguments` - the selector or argument passed to that step

Use `Add Step` to append rows. Use the delete icon to remove a row.

For `py_llm`:

* the action becomes `LLM - Enter your prompt / JSON schema`
* the argument box should contain either a natural-language prompt or a JSON schema
* selector-healing and step chaining do not apply the same way they do for the other runtimes

### Step 4 - Run preview before saving

Click `Live Preview` to validate the current configuration.

Preview behavior depends on method:

* `py_requests` and `py_llm` prime a preview cache first
* `py_selenium` and `py_playwright` run against a live browser session

If preview succeeds, the result appears below the form.

### Step 5 - Save the task

Click `Save Task` once preview output and step arguments look correct.

The task will then appear in the saved-task table with action buttons for:

* `Run now`
* `Pause schedule` / `Enable schedule`
* `CSV`
* delete

## 4. How Preview And Healing Work

When a selector fails in a step-based runtime, Crawla tries to repair it in this order:

1. Selector memory for the same domain
2. Deterministic heuristic fallback candidates
3. LLM replacement suggestion
4. Retry with the recovered parameter and store the success back into selector memory

This applies to Requests, Selenium, and Playwright flows. It does not generate missing steps.

## 5. Extraction Method Guidance

### Requests / BS4

Choose this when the page is server-rendered and you can reach the data with HTML plus CSS selectors.

Typical steps:

* `select_one`
* `select_all`
* `find_element_by_id`
* `find_element_by_class`
* `ext_str_get_text`

### Selenium

Choose this when the page needs browser compatibility or existing Selenium-oriented actions.

Typical steps:

* `find_element_by_css`
* `find_elements_by_css`
* `click`
* `ext_str_get_text`
* `ext_str_get_attribute`

### Playwright

Choose this when the page is JS-heavy or you need the stronger browser runtime used by Studio.

Typical steps:

* `find_element_by_css`
* `find_elements_by_css`
* `find_element_by_xpath`
* `click`
* `ext_str_get_text`
* `ext_str_get_attribute`
* `ext_str_get_href`

### LLM Extraction

Choose this when a schema or prompt is simpler than building a selector chain.

Supported input styles:

* prompt mode - ask for the information you want directly
* JSON schema mode - provide a strict schema and return structured JSON

Use this narrowly. It is not meant to replace cheaper deterministic runtimes everywhere.

## 6. Studio Walkthrough

Studio is the guided workspace. It is more powerful than the classic builder, but it expects you to understand the purpose of each panel.

### Method matrix

This selects the runtime family. Each method card swaps the starter nodes and guidance copy for that runtime.

### Workspace controls

This panel sets:

* task name
* target URL
* notification email
* preview controls
* save action

Buttons:

* `Prime Preview` - warms the preview cache for Requests or LLM flows
* `Run Preview` - executes the current draft against preview or live browser
* `Save Task` - validates the payload and queues the saved draft

### Visual inspector

Load the inspector to get a safe DOM snapshot and candidate selectors for a chosen node.

Source behavior depends on the method:

* `py_requests` and `py_llm` use cached HTML.
* `py_selenium` and `py_playwright` use a browser-rendered DOM snapshot.

Use it when:

* you want selector candidates instead of typing them manually
* you are building or repairing a browser or Requests locator

### AI copilot

Write a short goal, then click `Generate Flow`.

Copilot can:

* draft starter nodes
* ground suggestions with selector-memory hits when available
* give you a visible plan that you can still edit manually

Copilot does not own the flow. You should review every suggested node.

### Flow blueprint

This is the editable node list. Each node has:

* title
* step
* args
* intent

This is the part that becomes the saved task payload.

### Selector memory

This panel shows recent successful selector repairs for the same domain.

Use it as a signal that:

* the site has drifted before
* a known-good fallback may already exist

## 7. Saved Task Operations

Once a task is saved, you can:

* queue it immediately with `Run now`
* pause or enable inclusion in scheduled batch runs
* download the latest CSV output
* delete the task and its related saved data

Scheduled batch runs respect `schedule_enabled`.

## 8. CLI And Scheduling

Run tasks manually through the container:

```bash
docker exec -t crawla_web python ./main.py --all
docker exec -t crawla_web python ./main.py --task TASKID
docker exec -t crawla_web python ./main.py --py_playwright
```

Common flags:

* `--all`
* `--py_requests`
* `--py_selenium`
* `--py_playwright`
* `--py_llm`
* `--task TASKID`
* `--user USERID`

Example cron entry:

```bash
0 1 * * * docker exec -t crawla_web python ./main.py --all >> /log/crawla.log 2>&1
```

## 9. Auth Modes

### Local mode

* default Docker behavior
* no Auth0 redirect
* session user is `local_admin`

### Production / staging mode

* requires `APP_ENV=production`
* requires valid `AUTH0_*` settings
* `/login` redirects to Auth0
* each user sees only their own tasks and previews

For setup details, use [AUTH0_SETUP.md](AUTH0_SETUP.md).

## 10. Troubleshooting

### I only see `Local Admin`

That is expected in local mode. Switch to `APP_ENV=production` with Auth0 config if you need real user login.

### Extraction method or buttons do nothing

Restart or rebuild the web container so the running container picks up the latest templates and scripts:

```bash
docker compose up -d --build
docker compose restart crawla_web
```

### Browser preview cannot reach localhost

Inside Docker, Selenium and Playwright do not see your host's `127.0.0.1` the way your browser does. Use a container-reachable host such as `http://crawla_web:3000/` when the preview target is another service in the same stack.

### Preview is slow

That is normal for:

* browser methods
* large pages
* LLM-based extraction

Requests and LLM previews also spend time priming cache before the actual preview call.

### Studio is confusing

Use this order:

1. pick method
2. set URL
3. run preview or load inspector
4. inspect selectors or generate a draft flow
5. edit node arguments
6. save task

If you want the fastest path to success, start in `/contents`, then move to `/studio` once you know the site needs richer authoring.