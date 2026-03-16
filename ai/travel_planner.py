"""TravelPlanner – wraps Groq SDK to generate AI travel itineraries.

Uses the Llama 3.3 model served through Groq's API to produce rich,
Markdown-formatted itineraries from a list of attractions and hotels.
"""
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scrapers.base_scraper import Attraction, Hotel

try:
    from groq import Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False


MODEL = "llama-3.3-70b-versatile"
_MAX_HOTELS_IN_TABLE = 3  # number of hotels shown in the fallback itinerary table

_SYSTEM_PROMPT = """你是一位專業的台灣旅遊規劃師，擅長根據景點資訊生成詳細、實用的中文旅遊行程。
你生成的行程需要：
1. 清楚標示每天的安排，包含時間、景點、交通建議
2. 提供每個景點的簡短介紹與小提示
3. 推薦當地特色美食
4. 使用 Markdown 格式，方便閱讀
5. 語氣親切、充滿熱情，讓旅客期待這趟旅程"""


class TravelPlanner:
    """AI-powered itinerary generator using Groq + Llama 3.3.

    Parameters
    ----------
    api_key : str, optional
        Groq API key.  Falls back to the ``GROQ_API_KEY`` environment
        variable when not provided.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self._client = Groq(api_key=self.api_key) if (_GROQ_AVAILABLE and self.api_key) else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_itinerary(
        self,
        city: str,
        days: int,
        attractions: list,
        hotels: list,
        budget: str = "中等",
        preferences: list[str] | None = None,
    ) -> str:
        """Generate a Markdown travel itinerary.

        Parameters
        ----------
        city : str
            Destination city.
        days : int
            Number of travel days (1–5).
        attractions : list[Attraction]
            Scraped attraction objects.
        hotels : list[Hotel]
            Scraped hotel objects.
        budget : str
            Budget level – 經濟、中等 or 豪華.
        preferences : list[str], optional
            Travel preferences (e.g. ``["美食", "文化", "自然"]``).

        Returns
        -------
        str
            Markdown-formatted itinerary string.
        """
        if self._client is None:
            return self._fallback_itinerary(city, days, attractions, hotels, budget, preferences)

        prompt = self._build_prompt(city, days, attractions, hotels, budget, preferences or [])
        try:
            response = self._client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4096,
            )
            return response.choices[0].message.content or self._fallback_itinerary(
                city, days, attractions, hotels, budget, preferences
            )
        except Exception as exc:
            return (
                f"> ⚠️ AI 服務暫時無法使用（{exc}），以下為基本行程建議：\n\n"
                + self._fallback_itinerary(city, days, attractions, hotels, budget, preferences)
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(
        city: str,
        days: int,
        attractions: list,
        hotels: list,
        budget: str,
        preferences: list[str],
    ) -> str:
        attraction_list = "\n".join(
            f"- **{a.name}**：{a.description or '著名景點'}（{a.address or '請查詢地圖'}）"
            for a in attractions
        )
        hotel_list = "\n".join(
            f"- **{h.name}**：{h.price}，評分 {h.rating}（{h.address or '請查詢地圖'}）"
            for h in hotels
        ) or "（住宿資訊暫無）"
        pref_str = "、".join(preferences) if preferences else "綜合體驗"

        return f"""請為我規劃一趟 {days} 天的 {city} 旅遊行程。

**旅遊偏好**：{pref_str}
**預算等級**：{budget}

**可參考的景點**：
{attraction_list}

**推薦住宿**：
{hotel_list}

請生成詳細的 {days} 天行程，每天包含：
- 上午、下午、晚上的活動安排
- 每個景點的遊覽時間建議
- 景點之間的交通方式
- 推薦的當地美食
- 實用的旅遊小提示

請使用繁體中文，以 Markdown 格式輸出。"""

    @staticmethod
    def _fallback_itinerary(
        city: str,
        days: int,
        attractions: list,
        hotels: list,
        budget: str,
        preferences: list[str] | None,
    ) -> str:
        """Generate a simple template itinerary without AI."""
        lines = [
            f"# 🗺️ {city} {days} 天旅遊行程",
            "",
            f"**預算等級**：{budget}　**旅遊偏好**：{'、'.join(preferences or ['綜合體驗'])}",
            "",
        ]

        # Spread attractions across days
        per_day = max(1, len(attractions) // days) if attractions else 2
        attraction_chunks = [
            attractions[i : i + per_day] for i in range(0, len(attractions), per_day)
        ]

        for day_idx in range(days):
            lines.append(f"## 第 {day_idx + 1} 天")
            lines.append("")
            day_attractions = (
                attraction_chunks[day_idx] if day_idx < len(attraction_chunks) else []
            )

            if not day_attractions:
                lines += [
                    "| 時段 | 活動 |",
                    "| ---- | ---- |",
                    "| 上午 | 自由活動 |",
                    "| 下午 | 探索當地 |",
                    "| 晚上 | 品嚐美食 |",
                    "",
                ]
            else:
                lines += [
                    "| 時段 | 景點 | 建議時間 | 交通 |",
                    "| ---- | ---- | -------- | ---- |",
                ]
                time_slots = ["09:00 上午", "14:00 下午", "19:00 晚上"]
                for i, attr in enumerate(day_attractions):
                    slot = time_slots[i % len(time_slots)]
                    lines.append(
                        f"| {slot} | {attr.name} | 1.5 小時 | 捷運 / 計程車 |"
                    )
                lines.append("")
                if day_attractions:
                    lines.append("### 💡 小提示")
                    for attr in day_attractions:
                        if attr.description:
                            lines.append(f"- **{attr.name}**：{attr.description}")
                lines.append("")

        if hotels:
            lines += [
                "## 🏨 推薦住宿",
                "",
                "| 飯店 | 價格 | 評分 |",
                "| ---- | ---- | ---- |",
            ]
            for h in hotels[:_MAX_HOTELS_IN_TABLE]:
                lines.append(f"| {h.name} | {h.price} | ⭐ {h.rating} |")
            lines.append("")

        lines += [
            "---",
            "> 💡 **提示**：請提供 Groq API Key 以啟用 AI 個人化行程規劃功能。",
        ]
        return "\n".join(lines)
