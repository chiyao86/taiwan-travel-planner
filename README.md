# 📈 股票回測分析系統

自動化股票量化回測平台 — 從資料爬取到 AI 投資分析，一條龍完成。

## 功能特色

| 模組 | 功能 |
|------|------|
| **爬蟲** | 用 yfinance 爬取美股 / 台股歷史資料，存入資料庫 |
| **回測** | SMA / RSI / MACD 策略 × VectorBT 回測引擎 |
| **ML 預測** | XGBoost 機器學習預測明日漲跌 |
| **圖表** | Plotly 互動式技術分析圖 + 回測結果圖 |
| **AI 分析** | Groq AI（Llama 3.3 70B）生成專業投資分析報告 |
| **通知** | LINE Push 推送分析結果 |
| **排程** | APScheduler 定時自動執行 |
| **前端** | Streamlit 互動式 Web 介面 |

## 專案結構

```
├── app.py                  # CLI 主入口（python app.py）
├── streamlit_app.py        # Streamlit Web 前端（streamlit run streamlit_app.py）
├── config.py               # 統一設定（DB / API Key / 路徑）
├── services/
│   ├── __init__.py
│   ├── crawler.py          # 股票爬蟲（yfinance → PostgreSQL / SQLite）
│   ├── backtest.py         # 回測引擎（指標 / 訊號 / VectorBT）
│   ├── indicators.py       # 共用技術指標計算（RSI / MACD）
│   ├── plots.py            # Plotly 互動式圖表
│   ├── predictor.py        # XGBoost 機器學習預測
│   ├── analyzer.py         # Groq AI 分析
│   ├── notifier.py         # LINE Push 推送
│   └── scheduler.py        # APScheduler 定時排程
├── 回測報告/               # 輸出資料夾（HTML 報告 / PNG 圖表）
├── .env                    # 環境變數（API Key 等，不上傳 Git）
├── .gitignore              # Git 排除規則
└── requirements.txt        # Python 依賴
```

## 技術棧

- **語言**：Python 3.11
- **資料庫**：PostgreSQL（本地開發）/ SQLite（雲端部署）
- **回測引擎**：VectorBT + Numba JIT 加速
- **技術指標**：Pandas 原生計算（SMA / EMA / MACD / RSI / 布林通道 / ATR）
- **機器學習**：XGBoost 迴歸模型
- **報告**：QuantStats HTML 報告
- **AI**：Groq API（Llama 3.3 70B）
- **通知**：LINE Bot SDK（Push Message）
- **排程**：APScheduler
- **前端**：Streamlit
- **視覺化**：Plotly + Matplotlib

## 快速開始

### 1. 環境設定

```bash
# 建立 conda 環境
conda create -n stock_py311 python=3.11 -y
conda activate stock_py311

# 安裝依賴
pip install -r requirements.txt
```

### 2. 設定 `.env`

```env
# --- 資料庫模式 ---
# "postgres" = 本地 PostgreSQL（預設）
# "sqlite"   = SQLite（雲端部署 / 無 PostgreSQL 環境）
DB_MODE=postgres

# --- PostgreSQL 設定（DB_MODE=postgres 時使用）---
DB_HOST=localhost
DB_PORT=5432
DB_NAME=stock_db
DB_USER=postgres
DB_PASSWORD=5432

# --- API Keys ---
GROQ_API_KEY=你的GROQ_API_KEY

# --- LINE 推送（選填）---
LINE_CHANNEL_ACCESS_TOKEN=你的LINE_TOKEN
LINE_USER_ID=你的LINE_USER_ID
```

### 3. 確認資料庫

- **PostgreSQL 模式**：確保 PostgreSQL 已啟動，資料表會在首次爬取時自動建立
- **SQLite 模式**：設定 `DB_MODE=sqlite`，無需額外設定

### 4. 執行

**Web 模式**（Streamlit，推薦）：
```bash
streamlit run streamlit_app.py
```

**CLI 模式**（終端互動）：
```bash
python app.py
```

## 部署到 Hugging Face Spaces

1. 在 [Hugging Face](https://huggingface.co) 建立 Space（選 Streamlit SDK）
2. 將程式碼推送到 HF 的 Git 倉庫
3. 在 Space Settings → Secrets 加入環境變數：
   - `DB_MODE` = `sqlite`
   - `GROQ_API_KEY` = 你的 Key
   - `LINE_CHANNEL_ACCESS_TOKEN` = 你的 Token（選填）
   - `LINE_USER_ID` = 你的 ID（選填）
4. 系統會自動使用 SQLite 作為資料庫

## 流程圖

```
使用者輸入股票代碼 + 日期範圍
        ↓
  STEP 1：yfinance 爬取 → 資料庫
        ↓
  STEP 2：計算技術指標 → 三種策略回測
        ↓  產出：技術分析圖 / 回測結果圖 / HTML 報告
  STEP 3：XGBoost 機器學習預測
        ↓
  STEP 4：Groq AI 分析回測報告
        ↓
  STEP 5：LINE Push 推送結果
```

## API Key 取得

| 服務 | 取得方式 |
|------|---------|
| **Groq API** | [Groq Console](https://console.groq.com/) → 免費註冊 → API Keys |
| **LINE Bot** | [LINE Developers](https://developers.line.biz/) → 建立 Provider + Channel |
