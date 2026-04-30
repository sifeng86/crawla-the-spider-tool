# Crawla 驗證後現況 (Walkthrough)

本文件改為描述目前已驗證的實作狀態，而不是早期升級提案。

## 1. Local Start
- `docker compose up -d --build` 會啟動 `crawla_web`、`crawla_mongo`、`crawla_redis`、`crawla_chrome`。
- Docker 預設使用 `APP_ENV=local`，`/login` 會直接建立 `Local Admin` session 並導向 `/contents`。
- 生產模式若要使用 Auth0，仍需在 `login/.env` 提供完整 Auth0 設定。

## 2. UI 與 Preview
- 目前前端使用 glassmorphism 風格、深色背景與 skeleton loader；`Live Preview` 按鈕會先 warm up Requests/LLM preview cache。
- `py_requests` 與 `py_llm` 會使用 preview cache；`py_selenium` 與 `py_playwright` 直接對 live browser 執行 preview。

## 3. 執行模型
- `main.py` 使用 `ThreadPoolExecutor(max_workers=5)` 平行處理批次任務。
- 正式寫入資料時，結果會經 `save_results_batch()` 以 `insert_many()` 批次落到 MongoDB。

## 4. AI 功能
- LLM Self-Healing 已驗證支援 step-based 的 `py_requests`、`py_selenium`、`py_playwright`。
- `py_llm` 不使用 selector healing；它走 prompt/schema extraction。
- Smart Data Extraction 在 `py_llm` 輸入 JSON Schema 時，會回傳結構化 JSON，CSV 匯出也會保持 JSON 序列化格式。

## 5. 已知限制
- LLM 功能需要可用的 Gemini API key，否則不會成功回傳 AI 結果。
- Atlas/郵件等 production secrets 仍需依現有流程加密，並沒有移除 `encrypt_token.py` 這類工具需求。
- Docker 內的 browser-based preview 若要打本機服務，目標網址必須使用 container-reachable host，例如 `http://crawla_web:3000/`。
