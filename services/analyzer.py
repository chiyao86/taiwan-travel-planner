"""Groq AI 分析 — 讀取回測報告 HTML + AI 生成投資分析"""

from groq import Groq
from bs4 import BeautifulSoup
from pathlib import Path

from config import GROQ_API_KEY, GROQ_MODEL, REPORT_DIR

groq_client = Groq(api_key=GROQ_API_KEY)


def extract_report_data(html_file: Path) -> dict:
    """從 HTML 報告中提取關鍵績效數據"""
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    title = soup.find('h1')
    title_text = title.get_text() if title else "未知標題"

    data = {'title': title_text, 'metrics': {}}

    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                data['metrics'][key] = value

    return data


def analyze_with_groq(report_data: dict, symbol: str) -> str:
    """使用 Groq AI 分析報告數據"""
    metrics_text = "\n".join([f"{k}: {v}" for k, v in report_data['metrics'].items()])

    system_prompt = """你是華爾街資深量化交易分析師，擁有 15 年以上的股票市場經驗和 CFA（特許金融分析師）資格。

你的專業領域包括：
• 量化交易策略設計與評估
• 風險管理與資產配置
• 技術指標分析與市場趨勢判斷
• 回測數據的深度解讀

你的分析風格：
• 數據導向，以實際績效指標為依據
• 風險意識強，重視下檔保護
• 客觀中立，不盲目推薦或否定
• 語言專業但易懂，適合一般投資人閱讀

請用繁體中文回答，提供專業且實用的投資建議。"""

    user_prompt = f"""請根據以下技術量化回測報告，為投資人提供專業分析與建議：

【標的資訊】
股票代碼：{symbol}
報告標題：{report_data['title']}

【關鍵績效指標】
{metrics_text}

【分析要求】
請從以下角度進行深入分析，並給出具體建議：

1. **績效表現分析**
   - 總報酬率與年化報酬率是否達到投資目標？
   - 與大盤或同類資產相比表現如何？
   - 是否具有長期持有價值？

2. **風險評估**
   - 最大回撤（Max Drawdown）的風險水平
   - 夏普比率（Sharpe Ratio）的風險調整後報酬
   - 波動度與下檔風險分析
   - 投資人可承受的風險等級

3. **交易效率分析**
   - 勝率與平均獲利/虧損比
   - 交易頻率是否合理
   - 交易成本對績效的影響
   - 策略的穩定性與可複製性

4. **實戰投資建議**
   - 這個策略是否值得實際投入資金？
   - 建議的資金比例與進場時機
   - 需要注意的風險點與停損設定
   - 後續優化建議（如有）

5. **總結與評級**
   - 給出綜合評分（1-10分）
   - 適合的投資人類型（保守/穩健/積極）
   - 一句話總結建議

請以專業但不艱澀的方式說明，控制在 700-1000 字，讓一般投資人也能理解。"""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.6,
        max_tokens=2500,
        top_p=0.9
    )

    return response.choices[0].message.content


def analyze_report(symbol: str, report_file: Path = None) -> str:
    """讀取指定股票的 HTML 報告並回傳 AI 分析結果"""
    if report_file is None:
        report_file = REPORT_DIR / f"{symbol}_report.html"

    if not report_file.exists():
        print(f"❌ 找不到報告檔案：{report_file}")
        return None

    print(f"📖 讀取 {symbol} 報告數據...")
    report_data = extract_report_data(report_file)
    print(f"✓ 提取到 {len(report_data['metrics'])} 個指標")

    print("🤖 使用 Groq AI 分析中...")
    analysis = analyze_with_groq(report_data, symbol)
    print("✓ 分析完成")

    return analysis
