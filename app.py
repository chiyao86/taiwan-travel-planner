"""
台灣旅遊規劃程式 - Streamlit 主應用
"""

import streamlit as st
from datetime import datetime, timedelta

# 頁面配置
st.set_page_config(
    page_title="台灣旅遊規劃助手",
    page_icon="🗺️",
    layout="wide"
)

# 主標題
st.title("🗺️ 台灣旅遊規劃助手")
st.markdown("---")

# 側邊欄 - 旅遊基本資訊
with st.sidebar:
    st.header("📋 旅遊資訊")
    
    # 日期選擇
    start_date = st.date_input(
        "出發日期",
        value=datetime.now(),
        min_value=datetime.now()
    )
    
    days = st.slider("旅遊天數", 1, 14, 3)
    end_date = start_date + timedelta(days=days-1)
    
    st.write(f"返回日期: {end_date}")
    
    # 地區選擇
    regions = st.multiselect(
        "想去哪些地區？",
        ["台北", "新北", "桃園", "新竹", "苗栗", "台中", 
         "彰化", "南投", "雲林", "嘉義", "台南", "高雄",
         "屏東", "宜蘭", "花蓮", "台東", "澎湖", "金門", "馬祖"],
        default=["台北", "台中"]
    )
    
    # 旅遊類型
    travel_type = st.multiselect(
        "旅遊類型",
        ["自然風景", "歷史古蹟", "美食小吃", "夜市", 
         "文化藝術", "購物", "親子", "登山健行", "海邊"],
        default=["美食小吃", "自然風景"]
    )
    
    # 預算
    budget = st.select_slider(
        "每日預算（住宿+餐飲+交通）",
        options=["經濟 (<2000)", "中等 (2000-4000)", "舒適 (4000-6000)", "豪華 (>6000)"],
        value="中等 (2000-4000)"
    )

# 主內容區
tab1, tab2, tab3 = st.tabs(["📍 推薦景點", "📅 行程規劃", "💡 旅遊建議"])

with tab1:
    st.header("推薦景點")
    
    if regions:
        st.success(f"已選擇 {len(regions)} 個地區：{', '.join(regions)}")
        
        # 示範景點資料（實際可以串接 API 或資料庫）
        attractions = {
            "台北": ["台北101", "故宮博物院", "西門町", "士林夜市", "陽明山"],
            "台中": ["高美濕地", "逢甲夜市", "彩虹眷村", "台中歌劇院", "宮原眼科"],
            "高雄": ["駁二藝術特區", "美麗島捷運站", "六合夜市", "旗津海岸", "蓮池潭"],
            "台南": ["安平古堡", "赤崁樓", "花園夜市", "奇美博物館", "神農街"],
        }
        
        cols = st.columns(2)
        for idx, region in enumerate(regions):
            with cols[idx % 2]:
                st.subheader(f"📍 {region}")
                if region in attractions:
                    for attraction in attractions[region]:
                        st.write(f"• {attraction}")
                else:
                    st.info(f"{region} 的景點資訊即將推出")
    else:
        st.warning("請在左側選擇想去的地區")

with tab2:
    st.header("行程規劃")
    
    if regions and days:
        st.info(f"為您規劃 {days} 天 {len(regions)} 個地區的行程")
        
        for day in range(1, days + 1):
            with st.expander(f"第 {day} 天 - {(start_date + timedelta(days=day-1)).strftime('%Y-%m-%d')}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**🌅 上午**")
                    morning = st.text_input(
                        "上午行程",
                        placeholder="輸入景點或活動",
                        key=f"morning_{day}"
                    )
                
                with col2:
                    st.markdown("**🌞 下午**")
                    afternoon = st.text_input(
                        "下午行程",
                        placeholder="輸入景點或活動",
                        key=f"afternoon_{day}"
                    )
                
                with col3:
                    st.markdown("**🌙 晚上**")
                    evening = st.text_input(
                        "晚上行程",
                        placeholder="輸入景點或活動",
                        key=f"evening_{day}"
                    )
                
                notes = st.text_area(
                    "備註",
                    placeholder="今日注意事項、美食推薦等",
                    key=f"notes_{day}",
                    height=80
                )
    else:
        st.warning("請在左側設定旅遊天數和地區")

with tab3:
    st.header("旅遊建議")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎒 行前準備")
        st.markdown("""
        - ✅ 確認住宿訂房
        - ✅ 規劃交通方式（自駕/大眾運輸）
        - ✅ 查詢景點營業時間
        - ✅ 預訂熱門餐廳
        - ✅ 檢查天氣預報
        - ✅ 準備雨具/防曬用品
        """)
        
        st.subheader("💰 預算參考")
        st.markdown(f"""
        - **住宿**： 1000-3000 元/晚
        - **餐飲**： 500-1000 元/天
        - **交通**： 300-800 元/天
        - **景點門票**： 0-500 元/天
        - **總計（{days}天）**： 約 {days * 2000}-{days * 5000} 元
        """)
    
    with col2:
        st.subheader("🚗 交通建議")
        if len(regions) == 1:
            st.info("單一地區旅遊，建議使用大眾運輸或租機車")
        elif len(regions) <= 3:
            st.info("跨地區旅遊，建議開車或搭高鐵")
        else:
            st.warning("跨多個地區，建議規劃環島路線，考慮租車")
        
        st.subheader("🌤️ 旅遊季節")
        current_month = datetime.now().month
        if current_month in [3, 4, 5]:
            st.success("春季：氣候宜人，適合賞花")
        elif current_month in [6, 7, 8]:
            st.warning("夏季：炎熱多雨，注意防曬和防颱")
        elif current_month in [9, 10, 11]:
            st.success("秋季：氣候涼爽，最佳旅遊季節")
        else:
            st.info("冬季：北部多雨，南部較溫暖")

# 頁尾
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
        <p>🗺️ 台灣旅遊規劃助手 | 讓您的旅程更輕鬆 ✈️</p>
    </div>
    """,
    unsafe_allow_html=True
)
