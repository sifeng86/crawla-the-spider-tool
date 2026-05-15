# CLAUDE.md
Guidance for Claude Code on this repository.

---

## Overview
Crawla: Web UI spider tool. Flask + Python + MongoDB + Redis + Selenium.
- 4 crawl methods: `py_requests`, `py_selenium`, `py_playwright`, `py_llm`

## Architecture
```
login/server.py → Web UI
main.py → Crawler engine
login/lib/* → Helpers
MongoDB → Tasks/results
Redis → Rate limiting/cache
Selenium Chrome → JS rendering
```

## Commands
```bash
# Build/run
docker compose build
docker compose up [-d]
docker compose down

# Encrypt secrets
docker run -it -v ${PWD}:/work crawla_web:latest bash
python key_generator.py
python encrypt_token.py

# Run crawlers
docker exec crawla_web python main.py --all|--py_requests|--py_selenium|--task TASKID|--user USERID

# Utilities
docker exec crawla_web python export_csv.py --task TASKID
docker exec crawla_web python sendmail.py --task TASKID
```

## Rules
1.  Prefer environment variables or `*_FILE` secrets; treat `login/setting/config.json` as a legacy fallback for non-sensitive defaults.
2.  If legacy secrets are still stored in `login/setting/config.json`, encrypted values remain required there.
3.  No `exec()` for crawl steps, use `StepExecutor`
4.  All requests use stealth headers + automatic rate limiting

## Key Files
`main.py`, `login/server.py`, `login/lib/step_helper.py`, `login/lib/mongo.py`, `encrypt_token.py`, `export_csv.py`
