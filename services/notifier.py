"""LINE 推送通知 — 僅 Push（單向推送），無 Webhook"""

from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import LineBotApiError

from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)


def send_text(message: str) -> bool:
    """推送文字訊息到 LINE"""
    if not LINE_USER_ID:
        print("⚠️ 未設定 LINE_USER_ID，僅顯示在終端：")
        print("-" * 60)
        print(message)
        print("-" * 60)
        return False

    try:
        if len(message) > 5000:
            chunks = [message[i:i+4900] for i in range(0, len(message), 4900)]
            for i, chunk in enumerate(chunks):
                line_bot_api.push_message(LINE_USER_ID, TextSendMessage(text=chunk))
                print(f"✓ 已發送第 {i+1}/{len(chunks)} 段訊息")
        else:
            line_bot_api.push_message(LINE_USER_ID, TextSendMessage(text=message))
            print("✓ LINE 訊息發送成功")
        return True

    except LineBotApiError as e:
        print(f"❌ LINE 推送失敗：{e}")
        if hasattr(e, 'error') and hasattr(e.error, 'message'):
            print(f"  錯誤詳情：{e.error.message}")
        return False


def send_analysis_report(symbol: str, analysis: str) -> bool:
    """格式化並推送 AI 分析報告"""
    header = f"📊 {symbol} 回測分析報告\n{'='*30}\n\n"
    return send_text(header + analysis)
