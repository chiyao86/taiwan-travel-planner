"""回測系統 — 技術指標 / 訊號 / VectorBT 回測 / 報告圖表"""

import numpy as np
import pandas as pd
import vectorbt as vbt
import quantstats as qs
from sqlalchemy import create_engine, text
from numba import njit
from pathlib import Path

from config import get_db_url, REPORT_DIR, INIT_CASH, DEFAULT_FEES, DEFAULT_SLIPPAGE
from services.indicators import calculate_rsi, calculate_macd


def get_engine():
    return create_engine(get_db_url())


# ═══════════════════════════════════════════════════════
# STEP 1｜從 PostgreSQL 載入資料
# ═══════════════════════════════════════════════════════
def load_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    sql = """
        SELECT trade_date, open_price, high_price, low_price, close_price, volume
        FROM   stock_prices
        WHERE  symbol = :symbol
          AND  trade_date BETWEEN :start AND :end
        ORDER  BY trade_date;
    """
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(sql), conn,
            params={"symbol": symbol, "start": start, "end": end},
            parse_dates=["trade_date"],
            index_col="trade_date"
        )

    df.columns = ["open", "high", "low", "close", "volume"]

    if df.empty:
        with engine.connect() as conn:
            syms = pd.read_sql(text("SELECT DISTINCT symbol FROM stock_prices;"), conn)
        print(f"⚠️  查無 {symbol} 的資料，DB 裡現有的股票代碼：")
        print(syms["symbol"].tolist())
    else:
        print(f"✅ 載入 {symbol}：{len(df)} 筆 ({start} ~ {end})")

    return df


# ═══════════════════════════════════════════════════════
# STEP 2｜技術指標計算
# ═══════════════════════════════════════════════════════
def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    # 移動平均
    df["sma20"] = close.rolling(20).mean()
    df["sma60"] = close.rolling(60).mean()

    # MACD（使用共用模組）
    macd, macd_sig, macd_hist = calculate_macd(close)
    df["macd"]        = macd
    df["macd_signal"] = macd_sig
    df["macd_hist"]   = macd_hist

    # RSI-14（使用共用模組）
    df["rsi14"] = calculate_rsi(close, period=14)

    # 布林通道
    df["bb_mid"]   = close.rolling(20).mean()
    std            = close.rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * std
    df["bb_lower"] = df["bb_mid"] - 2 * std

    # ATR-14
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14).mean()

    df.dropna(inplace=True)
    print(f"📐 指標計算完成，剩餘 {len(df)} 筆有效資料")
    return df


# ═══════════════════════════════════════════════════════
# STEP 3｜Numba 加速：自訂訊號邏輯
# ═══════════════════════════════════════════════════════
@njit
def _sma_cross_signal(sma_fast: np.ndarray, sma_slow: np.ndarray) -> tuple:
    n       = len(sma_fast)
    entries = np.zeros(n, dtype=np.bool_)
    exits   = np.zeros(n, dtype=np.bool_)
    for i in range(1, n):
        if sma_fast[i - 1] < sma_slow[i - 1] and sma_fast[i] >= sma_slow[i]:
            entries[i] = True
        elif sma_fast[i - 1] > sma_slow[i - 1] and sma_fast[i] <= sma_slow[i]:
            exits[i] = True
    return entries, exits


@njit
def _rsi_signal(rsi: np.ndarray,
                oversold: float = 30.0,
                overbought: float = 70.0) -> tuple:
    n       = len(rsi)
    entries = np.zeros(n, dtype=np.bool_)
    exits   = np.zeros(n, dtype=np.bool_)
    for i in range(1, n):
        if rsi[i - 1] < oversold and rsi[i] >= oversold:
            entries[i] = True
        if rsi[i - 1] > overbought and rsi[i] <= overbought:
            exits[i] = True
    return entries, exits


def get_signals(df: pd.DataFrame, strategy: str = "sma_cross") -> tuple:
    if strategy == "sma_cross":
        ent_arr, ext_arr = _sma_cross_signal(
            df["sma20"].to_numpy(), df["sma60"].to_numpy()
        )
    elif strategy == "rsi":
        ent_arr, ext_arr = _rsi_signal(df["rsi14"].to_numpy())
    elif strategy == "macd":
        ent_arr = (
            (df["macd"].shift(1) < df["macd_signal"].shift(1)) &
            (df["macd"] >= df["macd_signal"])
        ).to_numpy()
        ext_arr = (
            (df["macd"].shift(1) > df["macd_signal"].shift(1)) &
            (df["macd"] <= df["macd_signal"])
        ).to_numpy()
    else:
        raise ValueError(f"未知策略：{strategy}")

    entries = pd.Series(ent_arr, index=df.index)
    exits   = pd.Series(ext_arr, index=df.index)
    print(f"📣 [{strategy}] 進場訊號：{entries.sum()} 次，出場訊號：{exits.sum()} 次")
    return entries, exits


# ═══════════════════════════════════════════════════════
# STEP 4｜VectorBT 回測
# ═══════════════════════════════════════════════════════
def run_backtest(df: pd.DataFrame,
                 entries: pd.Series,
                 exits: pd.Series,
                 init_cash: float = INIT_CASH,
                 fees: float = DEFAULT_FEES,
                 slippage: float = DEFAULT_SLIPPAGE
                 ) -> vbt.Portfolio:
    portfolio = vbt.Portfolio.from_signals(
        close      = df["close"],
        entries    = entries,
        exits      = exits,
        init_cash  = init_cash,
        fees       = fees,
        slippage   = slippage,
        freq       = "D",
    )
    return portfolio


# ═══════════════════════════════════════════════════════
# STEP 5｜績效報告
# ═══════════════════════════════════════════════════════
def print_stats(portfolio: vbt.Portfolio, init_cash: float = INIT_CASH):
    """印出核心績效指標 + 每筆交易成本/獲利/持有時間"""
    # 檢查資料是否為空
    if len(portfolio.wrapper.index) == 0:
        print("⚠️  回測資料為空，無法生成績效報告")
        return
    
    stats  = portfolio.stats()
    trades = portfolio.trades.records_readable

    labels = {
        "Start":                   "回測開始日期",
        "End":                     "回測結束日期",
        "Period":                  "回測總天數",
        "Total Return [%]":        "總報酬率 (%)",
        "Annualized Return [%]":   "年化報酬率 (%)",
        "Max Drawdown [%]":        "最大回撤 (%) ← 越小越好",
        "Sharpe Ratio":            "夏普值 ← >1 良好 >2 優秀",
        "Win Rate [%]":            "勝率 (%)",
        "Total Trades":            "總交易次數",
    }

    print("\n" + "═" * 60)
    print("📊  回測績效摘要")
    print("═" * 60)
    for en, zh in labels.items():
        if en in stats.index:
            print(f"  {zh:<32} {stats[en]}")

    final_value  = portfolio.value().iloc[-1]
    total_profit = final_value - init_cash
    print(f"  {'初始資金':<32} ${init_cash:>12,.2f}")
    print(f"  {'最終資產':<32} ${final_value:>12,.2f}")
    profit_sign = "+" if total_profit >= 0 else ""
    print(f"  {'總損益':<32} {profit_sign}${total_profit:>11,.2f}")
    print("═" * 60)
    print("💡 夏普值：衡量每承擔一單位風險能獲得多少報酬")
    print("💡 最大回撤：資產從高點跌至低點的最大跌幅")
    print("💡 勝率：獲利交易次數佔總交易次數的比例")

    if trades.empty:
        print("\n⚠️  無任何交易紀錄")
        return

    col_map = {
        "entry_time":  ["Entry Timestamp", "Entry Index"],
        "exit_time":   ["Exit Timestamp",  "Exit Index"],
        "entry_price": ["Avg Entry Price", "Entry Price"],
        "exit_price":  ["Avg Exit Price",  "Exit Price"],
        "size":        ["Size"],
        "pnl":         ["PnL"],
        "return":      ["Return [%]", "Return"],
    }

    def find_col(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    ec  = find_col(trades, col_map["entry_time"])
    xc  = find_col(trades, col_map["exit_time"])
    ep  = find_col(trades, col_map["entry_price"])
    xp  = find_col(trades, col_map["exit_price"])
    sc  = find_col(trades, col_map["size"])
    pnl = find_col(trades, col_map["pnl"])
    rc  = find_col(trades, col_map["return"])

    print(f"\n{'─' * 60}")
    print("📋  每筆交易明細")
    print(f"{'─' * 60}")
    header = f"  {'#':>3}  {'買入日':^12}  {'賣出日':^12}  {'持有':>5}  {'成本(USD)':>12}  {'獲利(USD)':>12}  {'報酬率':>8}"
    print(header)
    print(f"{'─' * 60}")

    for i, row in trades.iterrows():
        entry_dt = pd.to_datetime(row[ec]) if ec else None
        exit_dt  = pd.to_datetime(row[xc]) if xc else None
        days     = (exit_dt - entry_dt).days if (entry_dt and exit_dt) else "-"

        entry_px = row[ep] if ep else 0
        size     = row[sc] if sc else 0
        cost     = entry_px * size
        profit   = row[pnl] if pnl else 0
        ret      = row[rc]  if rc  else 0

        entry_str  = entry_dt.strftime("%Y-%m-%d") if entry_dt else "N/A"
        exit_str   = exit_dt.strftime("%Y-%m-%d")  if exit_dt  else "N/A"
        days_str   = f"{days}天" if isinstance(days, int) else days
        profit_str = f"+{profit:,.2f}" if profit >= 0 else f"{profit:,.2f}"
        ret_str    = f"{ret:.2f}%" if isinstance(ret, float) else str(ret)

        print(f"  {i+1:>3}  {entry_str:^12}  {exit_str:^12}  {days_str:>5}  ${cost:>11,.2f}  {profit_str:>12}  {ret_str:>8}")

    print(f"{'─' * 60}")
    total_pnl = trades[pnl].sum() if pnl else 0
    sign = "+" if total_pnl >= 0 else ""
    print(f"  {'合計損益':>50}  {sign}${total_pnl:>10,.2f}")
    print(f"{'─' * 60}")


# ═══════════════════════════════════════════════════════
# 圖表：技術分析圖
# ═══════════════════════════════════════════════════════
def _get_cjk_font():
    """自動偵測可用的中文字型（跨平台）"""
    import matplotlib.font_manager as fm
    candidates = ["Microsoft JhengHei", "Noto Sans CJK TC", "Noto Sans TC",
                  "WenQuanYi Micro Hei", "SimHei", "Arial Unicode MS", "sans-serif"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            return font
    return "sans-serif"


def plot_analysis(df: pd.DataFrame, symbol: str):
    """技術分析圖：K線 / 布林通道 / 成交量 / MACD / RSI + 下方說明"""
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import matplotlib.dates as mdates
    from matplotlib import rcParams

    rcParams["font.family"]        = _get_cjk_font()
    rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(16, 18))
    fig.suptitle(f"{symbol}  |  技術分析圖", fontsize=15, fontweight="bold", y=0.99)

    gs = gridspec.GridSpec(
        5, 1,
        height_ratios=[3.5, 1.2, 1.5, 1.5, 1.2],
        hspace=0.55,
        left=0.08, right=0.95, top=0.96, bottom=0.03
    )

    dates = df.index

    # ── 子圖 1：K 線 + 布林通道 + 均線 ──
    ax1 = fig.add_subplot(gs[0])
    for d, row in df.iterrows():
        color = "#d62728" if row["close"] >= row["open"] else "#2ca02c"
        ax1.plot([d, d], [row["low"], row["high"]], color=color, linewidth=0.8)
        ax1.bar(d, abs(row["close"] - row["open"]),
                bottom=min(row["open"], row["close"]),
                color=color, width=0.6, alpha=0.85)

    ax1.plot(dates, df["bb_upper"], color="gray",   linewidth=0.8, linestyle="--", label="布林上軌")
    ax1.plot(dates, df["bb_mid"],   color="orange",  linewidth=1.0, linestyle="--", label="布林中軌(SMA20)")
    ax1.plot(dates, df["bb_lower"], color="gray",   linewidth=0.8, linestyle="--", label="布林下軌")
    ax1.fill_between(dates, df["bb_upper"], df["bb_lower"], alpha=0.05, color="blue")
    ax1.plot(dates, df["sma60"], color="blue", linewidth=1.2, label="SMA60")
    ax1.set_title("① K 線圖 + 布林通道 + 均線", fontsize=11, loc="left", pad=5)
    ax1.set_ylabel("價格 (USD)")
    ax1.legend(loc="upper left", fontsize=8, ncol=3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.grid(alpha=0.25)

    # ── 子圖 2：成交量 ──
    ax2 = fig.add_subplot(gs[1])
    vol_colors = ["#d62728" if c >= o else "#2ca02c"
                  for c, o in zip(df["close"], df["open"])]
    ax2.bar(dates, df["volume"], color=vol_colors, width=0.6, alpha=0.8)
    ax2.set_title("② 成交量", fontsize=11, loc="left", pad=5)
    ax2.set_ylabel("成交量")
    ax2.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x/1e6:.0f}M")
    )
    ax2.grid(alpha=0.25)

    # ── 子圖 3：MACD ──
    ax3 = fig.add_subplot(gs[2])
    hist_colors = ["#d62728" if h >= 0 else "#2ca02c" for h in df["macd_hist"]]
    ax3.bar(dates, df["macd_hist"], color=hist_colors, width=0.6, alpha=0.7, label="柱狀圖")
    ax3.plot(dates, df["macd"],        color="#1f77b4", linewidth=1.2, label="MACD 線")
    ax3.plot(dates, df["macd_signal"], color="#ff7f0e", linewidth=1.2, label="訊號線")
    ax3.axhline(0, color="black", linewidth=0.6, linestyle="--")
    ax3.set_title("③ MACD（12, 26, 9）", fontsize=11, loc="left", pad=5)
    ax3.set_ylabel("MACD")
    ax3.legend(loc="upper left", fontsize=8, ncol=3)
    ax3.grid(alpha=0.25)

    # ── 子圖 4：RSI ──
    ax4 = fig.add_subplot(gs[3])
    ax4.plot(dates, df["rsi14"], color="purple", linewidth=1.2, label="RSI-14")
    ax4.axhline(70, color="#d62728", linestyle="--", linewidth=0.8, alpha=0.8, label="超買(70)")
    ax4.axhline(30, color="#2ca02c", linestyle="--", linewidth=0.8, alpha=0.8, label="超賣(30)")
    ax4.fill_between(dates, df["rsi14"], 70, where=(df["rsi14"] >= 70), alpha=0.15, color="#d62728")
    ax4.fill_between(dates, df["rsi14"], 30, where=(df["rsi14"] <= 30), alpha=0.15, color="#2ca02c")
    ax4.set_ylim(0, 100)
    ax4.set_title("④ RSI（14）", fontsize=11, loc="left", pad=5)
    ax4.set_ylabel("RSI")
    ax4.legend(loc="upper left", fontsize=8, ncol=3)
    ax4.grid(alpha=0.25)

    # ── 子圖 5：說明文字 ──
    ax5 = fig.add_subplot(gs[4])
    ax5.axis("off")
    note = (
        "【圖表看法】\n"
        "① K線圖：紅色 = 收漲（收盤 > 開盤），綠色 = 收跌；布林通道收窄代表盤整，擴張代表趨勢啟動\n"
        "② 成交量：配合K線看，量增價漲為強勢訊號；量縮代表觀望，突破時須有量才可信\n"
        "③ MACD：藍線（MACD）上穿橘線（訊號線）為買進參考，下穿為賣出參考；柱狀由負轉正也是多頭訊號\n"
        "④ RSI：高於70進入超買區（可能回落），低於30進入超賣區（可能反彈）；50為多空分界線"
    )
    ax5.text(
        0.01, 0.98, note,
        transform=ax5.transAxes,
        fontsize=10.5,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#f0f4ff",
                  edgecolor="#aabbdd", alpha=0.9),
        linespacing=1.9
    )

    fname = REPORT_DIR / f"{symbol}_技術分析.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"📊 技術分析圖已儲存：{fname}")
    plt.show()


# ═══════════════════════════════════════════════════════
# 圖表：回測結果圖
# ═══════════════════════════════════════════════════════
def plot_portfolio(portfolio: vbt.Portfolio, symbol: str, strategy: str):
    """自訂 matplotlib 版面，含中文說明區塊"""
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib import rcParams

    rcParams["font.family"]        = _get_cjk_font()
    rcParams["axes.unicode_minus"] = False

    strategy_zh = {
        "sma_cross": "SMA 均線交叉策略（黃金/死亡交叉）",
        "rsi":       "RSI 超買超賣策略",
        "macd":      "MACD 訊號線交叉策略",
    }.get(strategy, strategy)

    close      = portfolio.close
    value      = portfolio.value()
    returns    = portfolio.returns()
    cum_ret    = (1 + returns).cumprod()
    trades     = portfolio.trades.records_readable

    entry_dates = trades["Entry Timestamp"].values  if "Entry Timestamp"  in trades.columns else []
    exit_dates  = trades["Exit Timestamp"].values   if "Exit Timestamp"   in trades.columns else []
    entry_vals  = [value.asof(d) for d in entry_dates] if len(entry_dates) else []
    exit_vals   = [value.asof(d) for d in exit_dates]  if len(exit_dates)  else []

    fig = plt.figure(figsize=(16, 14))
    fig.suptitle(f"{symbol}  |  {strategy_zh}  |  回測結果",
                 fontsize=15, fontweight="bold", y=0.98)

    gs = gridspec.GridSpec(
        4, 1,
        height_ratios=[3, 2, 2, 1.2],
        hspace=0.55,
        left=0.08, right=0.95, top=0.93, bottom=0.04
    )

    # ── 子圖 1：資產淨值 ──
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(value.index, value.values, color="#1f77b4", linewidth=1.8, label="資產淨值")
    if len(entry_vals):
        ax1.scatter(entry_dates, entry_vals, marker="^", color="green",
                    s=120, zorder=5, label="進場（買入）")
    if len(exit_vals):
        ax1.scatter(exit_dates, exit_vals, marker="v", color="red",
                    s=120, zorder=5, label="出場（賣出）")
    ax1.set_title("① 資產淨值走勢", fontsize=12, loc="left", pad=6)
    ax1.set_ylabel("淨值 (USD)")
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(alpha=0.3)

    # ── 子圖 2：每日報酬率 ──
    ax2 = fig.add_subplot(gs[1])
    colors = ["#d62728" if r < 0 else "#2ca02c" for r in returns.values]
    ax2.bar(returns.index, returns.values * 100, color=colors, width=1.2, alpha=0.8)
    ax2.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax2.set_title("② 每日報酬率", fontsize=12, loc="left", pad=6)
    ax2.set_ylabel("報酬率 (%)")
    ax2.grid(alpha=0.3)

    # ── 子圖 3：累積報酬率 ──
    ax3 = fig.add_subplot(gs[2])
    ax3.plot(cum_ret.index, cum_ret.values, color="purple", linewidth=1.8, label="策略累積報酬")
    ax3.axhline(1.0, color="gray", linewidth=0.8, linestyle="--", label="基準線（不交易）")
    ax3.fill_between(cum_ret.index, cum_ret.values, 1,
                     where=(cum_ret.values >= 1), alpha=0.2, color="green", label="獲利區間")
    ax3.fill_between(cum_ret.index, cum_ret.values, 1,
                     where=(cum_ret.values < 1),  alpha=0.2, color="red",   label="虧損區間")
    ax3.set_title("③ 累積報酬率", fontsize=12, loc="left", pad=6)
    ax3.set_ylabel("累積倍數（1 = 本金）")
    ax3.legend(loc="upper left", fontsize=9)
    ax3.grid(alpha=0.3)

    # ── 子圖 4：圖表說明 ──
    ax4 = fig.add_subplot(gs[3])
    ax4.axis("off")
    explanation = (
        "【圖表看法】\n"
        "① 資產淨值走勢：藍線代表資金總額變化，▲綠色三角為買入點，▼紅色三角為賣出點\n"
        "② 每日報酬率：綠色柱 = 當天獲利，紅色柱 = 當天虧損；柱子越高代表當天漲跌越大\n"
        "③ 累積報酬率：從 1.0 開始，高於 1.0（綠色區域）代表整體獲利，低於 1.0（紅色區域）代表虧損\n"
        "   例如數值 1.3 表示本金成長 30%；灰色虛線為基準線（持有不動）"
    )
    ax4.text(
        0.01, 0.95, explanation,
        transform=ax4.transAxes,
        fontsize=10.5,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#f0f4ff", edgecolor="#aabbdd", alpha=0.9),
        linespacing=1.8
    )

    fname = REPORT_DIR / f"{symbol}_{strategy}_回測結果.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"📊 圖表已儲存：{fname}")
    plt.show()


# ═══════════════════════════════════════════════════════
# QuantStats HTML 報告
# ═══════════════════════════════════════════════════════
def export_quantstats(portfolio: vbt.Portfolio,
                      symbol: str,
                      strategy: str,
                      output_html: str = None):
    returns = portfolio.returns()
    returns.index = pd.to_datetime(returns.index)

    print("\n📄 QuantStats 報告說明：")
    print("   Cumulative Returns  → 累積報酬率走勢")
    print("   EOY Returns         → 每年度報酬率")
    print("   Drawdown            → 回撤（跌幅）走勢圖")
    print("   Rolling Sharpe      → 滾動夏普值（穩定性）")
    print("   Monthly Returns     → 每月報酬熱力圖（綠漲紅跌）")

    if output_html:
        output_path = REPORT_DIR / output_html
    else:
        output_path = REPORT_DIR / f"{symbol}_report.html"

    qs.reports.html(returns,
                    output=str(output_path),
                    title=f"{symbol} {strategy} 回測報告")
    print(f"✅ HTML 報告已儲存：{output_path}，用瀏覽器開啟即可查看")


# ═══════════════════════════════════════════════════════
# 高層 API：完整回測流程
# ═══════════════════════════════════════════════════════
ALL_STRATEGIES = ["sma_cross", "rsi", "macd"]


def run_all_strategies(symbol: str, start: str, end: str,
                       init_cash: float = INIT_CASH,
                       fees: float = DEFAULT_FEES,
                       slippage: float = DEFAULT_SLIPPAGE,
                       strategies: list = None) -> dict:
    """跑指定策略（預設全部），回傳 {strategy: portfolio}"""
    if strategies is None:
        strategies = ALL_STRATEGIES
    df = load_data(symbol, start, end)
    if df.empty:
        print(f"❌ {symbol} 在指定日期範圍 ({start} ~ {end}) 內無資料")
        print(f"   請確認：1) 已執行爬蟲  2) 日期範圍正確  3) 股票代碼正確")
        return {}

    df = calc_indicators(df)
    
    # 過濾掉 NaN 值並檢查資料量
    df_clean = df.dropna()
    if len(df_clean) < 60:
        print(f"⚠️  {symbol} 有效資料不足（僅 {len(df_clean)} 筆）")
        print(f"   建議：爬取至少 60 天以上的歷史資料（因為需要計算 SMA60）")
        return {}
    
    plot_analysis(df, symbol)

    results = {}
    for strat in strategies:
        print(f"\n{'─'*50}")
        print(f"  📌 策略：{strat}")
        print(f"{'─'*50}")

        entries, exits = get_signals(df, strategy=strat)
        pf = run_backtest(df, entries, exits,
                          init_cash=init_cash, fees=fees, slippage=slippage)

        # 檢查回測資料是否有效
        if len(pf.wrapper.index) == 0:
            print(f"⚠️  {symbol} [{strat}] 回測資料為空，跳過此策略")
            continue
        
        print_stats(pf, init_cash=init_cash)
        plot_portfolio(pf, symbol, strat)
        export_quantstats(pf, symbol, strat,
                          output_html=f"{symbol}_{strat}_report.html")
        results[strat] = pf

    return results
