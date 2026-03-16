"""Taiwan Travel Planner – Streamlit UI.

Main entry-point for the application.  Provides a clean sidebar for
configuration and a main content area that shows the AI-generated
itinerary, attraction cards, hotel suggestions and navigation links.
"""
import datetime
import os
import sys

import streamlit as st

# Ensure project root is importable when running via `streamlit run app.py`
sys.path.insert(0, os.path.dirname(__file__))

from manager.travel_manager import TravelManager  # noqa: E402
from utils.navigation import NavigationLinkGenerator  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ATTRACTIONS_PER_DAY = 4       # multiplier when computing max_attractions
MAX_ATTRACTIONS_CAP = 20      # upper bound on attractions fetched per plan

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="台灣旅遊規劃師 🗺️",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .main-title { font-size: 2.5rem; font-weight: 700; color: #1a6b3c; }
    .section-header { font-size: 1.4rem; font-weight: 600; margin-top: 1rem; }
    .attraction-card {
        background: #f0f8f0; border-left: 4px solid #1a6b3c;
        padding: 0.8rem 1rem; border-radius: 6px; margin-bottom: 0.6rem;
    }
    .hotel-card {
        background: #f0f4ff; border-left: 4px solid #2456a4;
        padding: 0.8rem 1rem; border-radius: 6px; margin-bottom: 0.6rem;
    }
    .nav-link { font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Cached data-fetching helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_travel_plan(
    city: str,
    days: int,
    budget: str,
    preferences: tuple[str, ...],
    check_in: str,
    check_out: str,
    groq_api_key: str,
):
    """Fetch and cache a complete travel plan (TTL = 1 hour)."""
    manager = TravelManager(
        groq_api_key=groq_api_key,
        headless=True,
        max_attractions=min(days * ATTRACTIONS_PER_DAY, MAX_ATTRACTIONS_CAP),
        max_hotels=5,
    )
    return manager.create_plan(
        city=city,
        days=days,
        budget=budget,
        preferences=list(preferences),
        check_in=check_in,
        check_out=check_out,
    )


# ---------------------------------------------------------------------------
# Sidebar – user settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/72/"
        "Flag_of_the_Republic_of_China.svg/320px-Flag_of_the_Republic_of_China.svg.png",
        width=80,
    )
    st.markdown("## 🗺️ 台灣旅遊規劃師")
    st.markdown("---")

    city = st.selectbox(
        "🏙️ 目標縣市",
        options=["台北", "台中", "台南", "高雄", "花蓮"],
        index=0,
    )

    days = st.slider("📅 旅遊天數", min_value=1, max_value=5, value=3)

    today = datetime.date.today()
    check_in = st.date_input("🛬 入住日期", value=today + datetime.timedelta(days=7))
    check_out = st.date_input(
        "🛫 退房日期",
        value=today + datetime.timedelta(days=7 + days),
        min_value=check_in + datetime.timedelta(days=1),
    )

    budget = st.selectbox(
        "💰 預算等級",
        options=["經濟", "中等", "豪華"],
        index=1,
    )

    preference_options = ["美食", "文化歷史", "自然景觀", "購物", "夜生活", "親子活動", "戶外冒險"]
    preferences = st.multiselect(
        "🎯 旅遊偏好（可複選）",
        options=preference_options,
        default=["美食", "文化歷史"],
    )

    st.markdown("---")
    groq_api_key = st.text_input(
        "🔑 Groq API Key（選填）",
        type="password",
        help="提供 API Key 可啟用 AI 個人化行程。可至 https://console.groq.com 免費取得。",
        value=os.getenv("GROQ_API_KEY", ""),
    )

    st.markdown("---")
    generate_btn = st.button("🚀 開始規劃行程", use_container_width=True, type="primary")

# ---------------------------------------------------------------------------
# Main content area
# ---------------------------------------------------------------------------
st.markdown('<p class="main-title">🗺️ 台灣旅遊規劃師</p>', unsafe_allow_html=True)
st.markdown(
    "利用 **Playwright** 動態爬蟲 + **Groq AI (Llama 3.3)** 自動生成專屬旅遊行程，"
    "並整合 **Google Maps** 導航連結！"
)
st.markdown("---")

if generate_btn:
    if check_out <= check_in:
        st.error("⚠️ 退房日期必須晚於入住日期，請重新選擇。")
        st.stop()

    with st.spinner(f"⏳ 正在爬取 {city} 的最新旅遊資訊並生成 AI 行程，請稍候…"):
        plan = fetch_travel_plan(
            city=city,
            days=days,
            budget=budget,
            preferences=tuple(preferences),
            check_in=str(check_in),
            check_out=str(check_out),
            groq_api_key=groq_api_key,
        )

    # -------------------------------------------------------------------
    # Overview metrics
    # -------------------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏙️ 城市", plan.city)
    col2.metric("📅 天數", f"{plan.days} 天")
    col3.metric("💰 預算", plan.budget)
    col4.metric("🎯 景點數", len(plan.attractions))
    st.markdown("---")

    # -------------------------------------------------------------------
    # Tabs: Itinerary | Attractions | Hotels | Navigation
    # -------------------------------------------------------------------
    tab_itinerary, tab_attractions, tab_hotels, tab_navigation = st.tabs(
        ["📋 行程規劃", "🏛️ 推薦景點", "🏨 推薦住宿", "🧭 地圖導航"]
    )

    # ---- Itinerary ----
    with tab_itinerary:
        st.markdown(f"*行程生成時間：{plan.generated_at}*")
        st.markdown(plan.itinerary_markdown)

    # ---- Attractions ----
    with tab_attractions:
        st.markdown(f"### 🏛️ {city} 推薦景點（共 {len(plan.attractions)} 處）")
        if not plan.attractions:
            st.info("暫無景點資訊。")
        else:
            for i, attr in enumerate(plan.attractions, 1):
                with st.expander(f"{i}. {attr.name}", expanded=(i <= 3)):
                    st.markdown(
                        f'<div class="attraction-card">'
                        f"<b>{attr.name}</b><br>"
                        f"{'📍 ' + attr.address if attr.address else ''}<br>"
                        f"{attr.description or ''}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if attr.source_url:
                        st.markdown(f"[🔗 官方網站]({attr.source_url})")
                    nav_url = NavigationLinkGenerator([attr.name]).generate_place_link(attr.name)
                    st.markdown(f"[📍 Google Maps]({nav_url})")

    # ---- Hotels ----
    with tab_hotels:
        st.markdown(f"### 🏨 {city} 推薦住宿（共 {len(plan.hotels)} 間）")
        if not plan.hotels:
            st.info("暫無住宿資訊。")
        else:
            cols = st.columns(min(len(plan.hotels), 3))
            for idx, hotel in enumerate(plan.hotels):
                with cols[idx % 3]:
                    st.markdown(
                        f'<div class="hotel-card">'
                        f"<b>{hotel.name}</b><br>"
                        f"💰 {hotel.price}<br>"
                        f"⭐ 評分：{hotel.rating}<br>"
                        f"{'📍 ' + hotel.address if hotel.address else ''}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    # ---- Navigation ----
    with tab_navigation:
        st.markdown("### 🧭 Google Maps 導航連結")

        if plan.full_route_url:
            st.markdown(
                f"#### 🗺️ 完整路線（一鍵導航全程）\n"
                f"[點此開啟 Google Maps 完整路線]({plan.full_route_url})"
            )
            st.markdown("---")

        if plan.segment_links:
            st.markdown("#### 📍 逐段導航連結")
            for seg in plan.segment_links:
                st.markdown(
                    f'<span class="nav-link">🔸 [{seg["label"]}]({seg["url"]})</span>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("景點不足兩處，無法生成逐段導航。")

else:
    # Landing page when no plan has been generated yet
    st.info("👈 請在左側欄設定旅遊條件，然後點擊「**🚀 開始規劃行程**」")

    st.markdown(
        """
### 功能特色

| 功能 | 說明 |
| ---- | ---- |
| 🕷️ 動態爬蟲 | 使用 Playwright 爬取台灣各縣市最新景點 |
| 🤖 AI 行程 | Groq Llama 3.3 生成個性化 Markdown 行程 |
| 🏨 住宿推薦 | 從 Booking.com 爬取最新飯店資訊 |
| 🧭 地圖導航 | 一鍵生成 Google Maps 路線 |
| ⚡ 快取優化 | 1 小時結果快取，避免重複爬取 |

### 支援城市

- 🏙️ **台北**：故宮、101、淡水老街…
- 🏙️ **台中**：彩虹村、高美濕地、逢甲夜市…
- 🏙️ **台南**：赤崁樓、安平古堡、花園夜市…
- 🏙️ **高雄**：蓮池潭、駁二藝術特區、旗津…
- 🏙️ **花蓮**：太魯閣、七星潭、鯉魚潭…
        """
    )
