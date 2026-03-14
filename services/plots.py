"""互動式圖表 — Plotly 技術分析與回測圖表"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import vectorbt as vbt

from config import REPORT_DIR


def plot_sma_technical(df: pd.DataFrame, symbol: str):
    """
    SMA 策略專用技術圖（只顯示 K線 + SMA20 + SMA60 + 成交量）
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(
            f'{symbol} - K線圖 + SMA均線',
            '成交量'
        ),
        row_heights=[0.7, 0.3]
    )
    
    # K線圖
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K線',
            increasing_line_color='#d62728',
            decreasing_line_color='#2ca02c'
        ),
        row=1, col=1
    )
    
    # SMA20
    fig.add_trace(
        go.Scatter(x=df.index, y=df['sma20'], name='SMA20 (快線)',
                   line=dict(color='orange', width=2)),
        row=1, col=1
    )
    
    # SMA60
    fig.add_trace(
        go.Scatter(x=df.index, y=df['sma60'], name='SMA60 (慢線)',
                   line=dict(color='blue', width=2)),
        row=1, col=1
    )
    
    # 成交量
    colors = ['#d62728' if c >= o else '#2ca02c' 
              for c, o in zip(df['close'], df['open'])]
    fig.add_trace(
        go.Bar(x=df.index, y=df['volume'], name='成交量',
               marker=dict(color=colors), showlegend=False),
        row=2, col=1
    )
    
    fig.update_layout(
        height=800,
        title_text=f"{symbol} - SMA 均線交叉策略 - 技術分析",
        showlegend=True,
        hovermode='x unified',
        xaxis_rangeslider_visible=False
    )
    
    fig.update_yaxes(title_text="價格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    
    return fig


def plot_rsi_technical(df: pd.DataFrame, symbol: str):
    """
    RSI 策略專用技術圖（只顯示 K線 + RSI + 成交量）
    """
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(
            f'{symbol} - K線圖',
            'RSI (14)',
            '成交量'
        ),
        row_heights=[0.5, 0.3, 0.2]
    )
    
    # K線圖
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K線',
            increasing_line_color='#d62728',
            decreasing_line_color='#2ca02c'
        ),
        row=1, col=1
    )
    
    # RSI
    fig.add_trace(
        go.Scatter(x=df.index, y=df['rsi14'], name='RSI-14',
                   line=dict(color='purple', width=2)),
        row=2, col=1
    )
    
    # RSI 超買超賣線
    fig.add_hline(y=70, line=dict(color='red', width=1, dash='dash'),
                  row=2, col=1, annotation_text="超買(70)")
    fig.add_hline(y=30, line=dict(color='green', width=1, dash='dash'),
                  row=2, col=1, annotation_text="超賣(30)")
    
    fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1,
                  line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1,
                  line_width=0, row=2, col=1)
    
    # 成交量
    colors = ['#d62728' if c >= o else '#2ca02c' 
              for c, o in zip(df['close'], df['open'])]
    fig.add_trace(
        go.Bar(x=df.index, y=df['volume'], name='成交量',
               marker=dict(color=colors), showlegend=False),
        row=3, col=1
    )
    
    fig.update_layout(
        height=900,
        title_text=f"{symbol} - RSI 超買超賣策略 - 技術分析",
        showlegend=True,
        hovermode='x unified',
        xaxis_rangeslider_visible=False
    )
    
    fig.update_yaxes(title_text="價格", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
    fig.update_yaxes(title_text="成交量", row=3, col=1)
    
    return fig


def plot_macd_technical(df: pd.DataFrame, symbol: str):
    """
    MACD 策略專用技術圖（只顯示 K線 + MACD + 成交量）
    """
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(
            f'{symbol} - K線圖',
            'MACD (12, 26, 9)',
            '成交量'
        ),
        row_heights=[0.5, 0.3, 0.2]
    )
    
    # K線圖
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K線',
            increasing_line_color='#d62728',
            decreasing_line_color='#2ca02c'
        ),
        row=1, col=1
    )
    
    # MACD
    fig.add_trace(
        go.Scatter(x=df.index, y=df['macd'], name='MACD線',
                   line=dict(color='#1f77b4', width=2)),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df['macd_signal'], name='訊號線',
                   line=dict(color='#ff7f0e', width=2)),
        row=2, col=1
    )
    
    # MACD 柱狀圖
    colors_macd = ['#d62728' if h >= 0 else '#2ca02c' for h in df['macd_hist']]
    fig.add_trace(
        go.Bar(x=df.index, y=df['macd_hist'], name='MACD柱狀',
               marker=dict(color=colors_macd), showlegend=False),
        row=2, col=1
    )
    
    # 成交量
    colors = ['#d62728' if c >= o else '#2ca02c' 
              for c, o in zip(df['close'], df['open'])]
    fig.add_trace(
        go.Bar(x=df.index, y=df['volume'], name='成交量',
               marker=dict(color=colors), showlegend=False),
        row=3, col=1
    )
    
    fig.update_layout(
        height=900,
        title_text=f"{symbol} - MACD 趨勢動能策略 - 技術分析",
        showlegend=True,
        hovermode='x unified',
        xaxis_rangeslider_visible=False
    )
    
    fig.update_yaxes(title_text="價格", row=1, col=1)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    fig.update_yaxes(title_text="成交量", row=3, col=1)
    
    return fig


def plot_backtest_interactive(portfolio: vbt.Portfolio, symbol: str, strategy: str, 
                               init_cash: float, buy_price: float = None, 
                               sell_price: float = None):
    """
    互動式回測結果圖表（Plotly）
    顯示：資產淨值、買賣點、損益分析
    
    Args:
        portfolio: VectorBT Portfolio 物件
        symbol: 股票代號
        strategy: 策略名稱
        init_cash: 初始資金
        buy_price: 買入價格（可選，用於顯示損益）
        sell_price: 賣出價格（可選，用於顯示損益）
    """
    strategy_zh = {
        "sma_cross": "SMA 均線交叉策略",
        "rsi": "RSI 超買超賣策略",
        "macd": "MACD 訊號線交叉策略",
    }.get(strategy, strategy)
    
    value = portfolio.value()
    returns = portfolio.returns()
    cum_ret = (1 + returns).cumprod()
    trades = portfolio.trades.records_readable
    
    # 獲取買賣點
    entry_dates = trades["Entry Timestamp"].values if "Entry Timestamp" in trades.columns else []
    exit_dates = trades["Exit Timestamp"].values if "Exit Timestamp" in trades.columns else []
    entry_prices = trades["Entry Price"].values if "Entry Price" in trades.columns else []
    exit_prices = trades["Exit Price"].values if "Exit Price" in trades.columns else []
    
    entry_vals = [value.asof(d) for d in entry_dates] if len(entry_dates) else []
    exit_vals = [value.asof(d) for d in exit_dates] if len(exit_dates) else []
    
    # 創建子圖
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            '資產淨值走勢 + 交易點位',
            '每日報酬率',
            '累積報酬率'
        ),
        row_heights=[0.4, 0.3, 0.3]
    )
    
    # ─── 子圖 1：資產淨值 + 買賣點 ───
    fig.add_trace(
        go.Scatter(x=value.index, y=value.values, name='資產淨值',
                   line=dict(color='#1f77b4', width=2)),
        row=1, col=1
    )
    
    # 買入點
    if len(entry_vals):
        fig.add_trace(
            go.Scatter(x=entry_dates, y=entry_vals, mode='markers',
                       name='買入點', marker=dict(color='green', size=12, symbol='triangle-up')),
            row=1, col=1
        )
    
    # 賣出點
    if len(exit_vals):
        fig.add_trace(
            go.Scatter(x=exit_dates, y=exit_vals, mode='markers',
                       name='賣出點', marker=dict(color='red', size=12, symbol='triangle-down')),
            row=1, col=1
        )
    
    # 初始資金線
    fig.add_hline(y=init_cash, line=dict(color='gray', width=1, dash='dash'),
                  row=1, col=1, annotation_text=f"初始資金: ${init_cash:,.0f}")
    
    # ─── 子圖 2：每日報酬率 ───
    colors_ret = ['#d62728' if r < 0 else '#2ca02c' for r in returns.values]
    fig.add_trace(
        go.Bar(x=returns.index, y=returns.values * 100, name='每日報酬率',
               marker=dict(color=colors_ret), showlegend=False),
        row=2, col=1
    )
    fig.add_hline(y=0, line=dict(color='black', width=1, dash='dash'), row=2, col=1)
    
    # ─── 子圖 3：累積報酬率 ───
    fig.add_trace(
        go.Scatter(x=cum_ret.index, y=cum_ret.values, name='累積報酬',
                   line=dict(color='purple', width=2),
                   fill='tonexty', fillcolor='rgba(128, 0, 128, 0.1)'),
        row=3, col=1
    )
    fig.add_hline(y=1.0, line=dict(color='gray', width=1, dash='dash'),
                  row=3, col=1, annotation_text="基準線(1.0)")
    
    # ─── 更新佈局 ───
    final_value = value.iloc[-1]
    total_profit = final_value - init_cash
    profit_pct = (total_profit / init_cash) * 100
    
    title = (f"{symbol} - {strategy_zh} - 回測結果<br>"
             f"<sub>初始: ${init_cash:,.0f} | 最終: ${final_value:,.2f} | "
             f"損益: ${total_profit:,.2f} ({profit_pct:+.2f}%)</sub>")
    
    fig.update_layout(
        height=1000,
        title_text=title,
        title_font_size=18,
        showlegend=True,
        hovermode='x unified'
    )
    
    fig.update_yaxes(title_text="淨值 (USD)", row=1, col=1)
    fig.update_yaxes(title_text="報酬率 (%)", row=2, col=1)
    fig.update_yaxes(title_text="累積倍數", row=3, col=1)
    fig.update_xaxes(title_text="日期", row=3, col=1)
    
    return fig
