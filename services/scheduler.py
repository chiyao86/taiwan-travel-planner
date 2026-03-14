"""排程服務 — APScheduler 定時執行爬取 + 回測 + AI 分析 + LINE 推送"""

import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import REPORT_DIR, INIT_CASH, DEFAULT_FEES, DEFAULT_SLIPPAGE

# 全域排程器（整個 app 共用一個）
_scheduler = None
_schedule_logs = []


def get_scheduler():
    """取得單例 scheduler（確保在 Streamlit 中不會重複初始化）"""
    global _scheduler
    if _scheduler is None:
        # 使用 Asia/Taipei 時區
        _scheduler = BackgroundScheduler(
            daemon=True,
            timezone=pytz.timezone('Asia/Taipei')
        )
        if not _scheduler.running:
            _scheduler.start()
            add_log("🚀 APScheduler 已啟動 (Asia/Taipei 時區)")
    return _scheduler


def add_log(message: str):
    """新增排程紀錄"""
    global _schedule_logs
    tw_tz = pytz.timezone('Asia/Taipei')
    timestamp = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    _schedule_logs.append(log_entry)
    # 只保留最近 100 筆
    if len(_schedule_logs) > 100:
        _schedule_logs.pop(0)
    print(log_entry)


def scheduled_job(symbols: list, crawl_days: int = 730,
                  init_cash: float = INIT_CASH,
                  fees: float = DEFAULT_FEES,
                  slippage: float = DEFAULT_SLIPPAGE,
                  do_crawl: bool = True,
                  do_backtest: bool = True,
                  do_analyze: bool = True,
                  do_notify: bool = True):
    """
    排程任務：爬取 → 回測 → AI 分析 → LINE 推送
    """
    from datetime import date, timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=crawl_days)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    add_log(f"🚀 排程開始執行：{', '.join(symbols)} ({start_str} ~ {end_str})")

    for symbol in symbols:
        try:
            # 爬取
            if do_crawl:
                from services.crawler import crawl_stock
                count = crawl_stock(symbol, start_str, end_str)
                add_log(f"📡 {symbol} 爬取完成：{count} 筆")

            # 回測
            if do_backtest:
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                plt.show = lambda *a, **kw: None

                from services.backtest import run_all_strategies
                results = run_all_strategies(
                    symbol, start_str, end_str,
                    init_cash=init_cash, fees=fees, slippage=slippage
                )
                if results:
                    add_log(f"📊 {symbol} 回測完成：{len(results)} 種策略")
                else:
                    add_log(f"⚠️ {symbol} 回測失敗")

            # AI 分析 + LINE 推送
            if do_analyze:
                from services.analyzer import analyze_report
                from services.backtest import ALL_STRATEGIES
                for strat in ALL_STRATEGIES:
                    report_file = REPORT_DIR / f"{symbol}_{strat}_report.html"
                    if not report_file.exists():
                        continue
                    analysis = analyze_report(symbol, report_file=report_file)
                    if analysis:
                        add_log(f"🤖 {symbol} [{strat}] AI 分析完成")

                        if do_notify:
                            from services.notifier import send_analysis_report
                            header = f"📊 {symbol} [{strat}] 排程回測分析\n{'='*30}\n\n"
                            send_analysis_report(symbol, header + analysis)
                            add_log(f"📤 {symbol} LINE 推送完成")

                    time.sleep(2)

        except Exception as e:
            add_log(f"❌ {symbol} 執行失敗：{e}")

    add_log("✅ 排程任務全部完成")


def add_scheduled_job(job_id: str, hour: int, minute: int, **kwargs):
    """新增定時排程任務"""
    scheduler = get_scheduler()
    
    # 如果已存在同 ID 的任務，先移除
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    # 使用 Asia/Taipei 時區
    trigger = CronTrigger(
        hour=hour,
        minute=minute,
        timezone=pytz.timezone('Asia/Taipei')
    )
    scheduler.add_job(
        scheduled_job,
        trigger=trigger,
        id=job_id,
        kwargs=kwargs,
        replace_existing=True
    )
    add_log(f"📅 已設定排程：每天 {hour:02d}:{minute:02d} 執行 (ID: {job_id})")


def remove_scheduled_job(job_id: str):
    """移除排程任務"""
    scheduler = get_scheduler()
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        add_log(f"🗑️ 已移除排程 (ID: {job_id})")
        return True
    return False


def get_scheduled_jobs() -> list:
    """取得所有排程任務"""
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else "N/A",
            "trigger": str(job.trigger),
        })
    return jobs


def get_logs() -> list:
    """取得排程紀錄"""
    return _schedule_logs.copy()


def is_scheduler_running() -> bool:
    """檢查 scheduler 是否正在運行"""
    scheduler = get_scheduler()
    return scheduler.running
