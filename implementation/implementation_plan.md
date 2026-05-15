# Crawla 專案優化與升級計畫

經過全面的程式碼庫盤點，以下是針對您的 5 個核心需求所提出的分析與實作計畫。

## 1. 專案完整性檢查 (Completeness Check)
目前的 Crawla 具備良好的微服務雛形（Flask, Celery, Redis, MongoDB）與多樣化的爬取引擎（Requests, Selenium, Playwright, LLM）。
**發現的缺口與需補強處**：
- **強依賴外部服務**：啟動高度依賴 Auth0 與外部 MongoDB，缺乏單機/本地端開箱即用的 fallback。
- **LLM 模式功能未完成**：在 UI 中，`py_llm` 模式無法被儲存 (Save is disabled)。
- **環境設定繁瑣**：密碼需手動進入 Docker 執行 Python 腳本加密。
- **基礎設施遺漏**：`docker-compose.yml` 缺少 MongoDB 服務，使用者無法一鍵架設所有必要組件。

## 2. 爬蟲速度優化 (Speed Optimization)
- **非同步並發處理 (Async IO)**：目前的 `main.py` 在處理 `py_requests` 時為同步執行。我們將引入 `asyncio` 與 `aiohttp` 或 `ThreadPoolExecutor`，讓多個爬取任務能平行處理。
- **瀏覽器池化 (Browser Pooling)**：Selenium 與 Playwright 每次任務皆啟動新 Browser 實例，開銷極大。我們將實作複用機制 (Reuse Context) 或長駐的 Headless Browser Pool，大幅降低啟動延遲。
- **資料庫寫入優化**：在儲存結果時，實作批次插入 (Batch Insert) 減少 I/O 等待。

## 3. 設定便利性 (Set and go)
- **All-in-one Docker Compose**：將 MongoDB 加入 `docker-compose.yml`。使用者只需執行 `docker-compose up -d` 即可啟動完整環境。
- **Local Dev Mode (Auth Bypass)**：在 `.env` 加入 `APP_ENV=local` 模式。啟動此模式時，自動繞過 Auth0 驗證並自動登入為預設管理員，完全免設定。
- **自動化金鑰與加密**：移除手動執行 `key_generator.py` 的流程。系統將在首次啟動時自動產生所需的 Secret Key 並處理加密，使用者只需在 `.env` 填寫明文即可。

## 4. 使用者體驗 (User Experience)
- **Premium Design (現代美學重構)**：捨棄傳統的 Bootstrap 4 預設外觀。導入 **Glassmorphism (毛玻璃特效)**、**全域暗黑模式 (Dark Mode)**、平滑過渡動畫 (Micro-animations) 與現代字體 (Inter/Outfit)。
- **互動式 Preview**：優化「Preview」按鈕的體驗，以 Skeleton Loader 取代傳統 GIF，並將結果以結構化的卡片或表格呈現。
- **無縫表單操作**：步驟與參數的增刪將加入滑順的拖曳與動畫效果。

## 5. 打造全世界最厲害的工具 (Best in the world features)
要成為世界級工具，我們將導入以下破壞性創新功能：
- **LLM Self-Healing (自我修復爬蟲)**：當網頁改版導致原有的 CSS Selector 失效時，系統會自動將周邊的 DOM 結構餵給 LLM，並由 LLM 自動推斷與修復新的 Selector，讓爬蟲具備「免疫力」。
- **Smart Data Extraction (智慧結構化)**：升級 LLM 模式，不再只是單純回傳字串，而是讓使用者定義 JSON Schema，讓 LLM 將雜亂的網頁內容精準提取為結構化資料。
- *(Future)* **Visual Selector**：整合一套前端檢視器，讓使用者直接點擊網頁元素即可產生抓取步驟，達成真正的 No-Code。

---

## User Review Required
> [!IMPORTANT]
> **請您評估並選擇以下實作順序，或直接核准全盤計畫：**
> 1. **優先重構 UI/UX**：直接套用 Premium Design，讓工具外觀先達到「世界級」水準。
> 2. **優先處理 Set & Go**：修改 Docker 與 Auth 邏輯，讓任何人都能一鍵啟動。
> 3. **優先實作進階功能**：先完成 LLM Self-Healing 與 Browser Pooling 等核心技術。

您可以告訴我您最看重哪一塊，或者回覆「**核准 (Approve)**」，我將由**「Set & Go 環境優化」**開始，接續**「UI重構」**，最後實作**「速度優化與 LLM 進階功能」**。
