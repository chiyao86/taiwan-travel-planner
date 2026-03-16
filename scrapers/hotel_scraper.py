"""HotelScraper – scrapes hotel listings from Booking.com.

Employs multiple anti-bot measures:
* ``playwright-stealth`` to hide automation fingerprints
* Random User-Agent rotation
* Random scroll and mouse-move delays mimicking human behaviour
* Falls back to curated static hotel data when live scraping fails.
"""
import asyncio
import random
import re
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Page

try:
    from playwright_stealth import stealth_async
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False

from .base_scraper import BaseScraper, Hotel


# ---------------------------------------------------------------------------
# Booking.com search URL builder
# ---------------------------------------------------------------------------
BOOKING_BASE = "https://www.booking.com/searchresults.zh-tw.html"

BOOKING_CITY_NAMES: dict[str, str] = {
    "台北": "Taipei, Taiwan",
    "新北": "New Taipei, Taiwan",
    "桃園": "Taoyuan, Taiwan",
    "台中": "Taichung, Taiwan",
    "台南": "Tainan, Taiwan",
    "高雄": "Kaohsiung, Taiwan",
    "基隆": "Keelung, Taiwan",
    "新竹": "Hsinchu, Taiwan",
    "苗栗": "Miaoli, Taiwan",
    "彰化": "Changhua, Taiwan",
    "南投": "Nantou, Taiwan",
    "雲林": "Yunlin, Taiwan",
    "嘉義": "Chiayi, Taiwan",
    "屏東": "Pingtung, Taiwan",
    "宜蘭": "Yilan, Taiwan",
    "花蓮": "Hualien, Taiwan",
    "台東": "Taitung, Taiwan",
}

# Fallback hotel data (used when live scraping is blocked / unavailable)
FALLBACK_HOTELS: dict[str, list[dict]] = {
    "台北": [
        {"name": "台北君悅大飯店", "price": "NT$ 6,800/晚起", "rating": "9.0", "address": "台北市信義區松壽路2號"},
        {"name": "W台北", "price": "NT$ 7,200/晚起", "rating": "9.2", "address": "台北市信義區忠孝東路五段10號"},
        {"name": "台北喜來登大飯店", "price": "NT$ 5,500/晚起", "rating": "8.8", "address": "台北市中正區忠孝東路一段12號"},
        {"name": "台北美侖大飯店", "price": "NT$ 3,800/晚起", "rating": "8.5", "address": "台北市中山區民族東路"},
        {"name": "西門町商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台北市萬華區西寧南路"},
        {"name": "台北諾富特華航酒店", "price": "NT$ 4,200/晚起", "rating": "8.6", "address": "台北市大同區承德路三段"},
        {"name": "台北晶華酒店", "price": "NT$ 6,000/晚起", "rating": "9.1", "address": "台北市中山區中山北路二段"},
        {"name": "台北老爺大酒店", "price": "NT$ 5,200/晚起", "rating": "8.9", "address": "台北市中山區中山北路二段37-1號"},
        {"name": "台北萬豪酒店", "price": "NT$ 7,500/晚起", "rating": "9.3", "address": "台北市中山區樂群二路199號"},
        {"name": "台北凱撒大飯店", "price": "NT$ 3,500/晚起", "rating": "8.4", "address": "台北市中正區忠孝西路一段38號"},
        {"name": "台北東區商旅", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "台北市大安區忠孝東路四段"},
        {"name": "台北福華大飯店", "price": "NT$ 4,000/晚起", "rating": "8.7", "address": "台北市大安區仁愛路三段160號"},
        {"name": "寒舍艾麗酒店", "price": "NT$ 5,800/晚起", "rating": "9.0", "address": "台北市信義區松仁路38號"},
        {"name": "台北文華東方酒店", "price": "NT$ 9,000/晚起", "rating": "9.5", "address": "台北市中山區敦化北路166號"},
        {"name": "北投麗禧溫泉酒店", "price": "NT$ 8,000/晚起", "rating": "9.4", "address": "台北市北投區中山路1-2號"},
        {"name": "西華飯店", "price": "NT$ 4,500/晚起", "rating": "8.8", "address": "台北市中山區樂群三路111號"},
        {"name": "馥敦飯店南京館", "price": "NT$ 2,800/晚起", "rating": "8.3", "address": "台北市中山區南京東路三段"},
        {"name": "花園大酒店", "price": "NT$ 2,200/晚起", "rating": "8.1", "address": "台北市中山區中山北路二段1號"},
        {"name": "神旺商務酒店", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "台北市大安區忠孝東路四段511號"},
        {"name": "台北金典酒店", "price": "NT$ 3,200/晚起", "rating": "8.5", "address": "台北市中山區中山北路三段"},
    ],
    "新北": [
        {"name": "淡水漁人碼頭大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "新北市淡水區觀海路"},
        {"name": "板橋凱撒大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "新北市板橋區縣民大道二段"},
        {"name": "新北市碧潭悠活渡假村", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "新北市新店區碧潭路"},
        {"name": "鶯歌陶瓷旅店", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "新北市鶯歌區文化路"},
        {"name": "烏來飛瀑溫泉旅館", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "新北市烏來區溫泉街"},
        {"name": "九份山城旅社", "price": "NT$ 2,000/晚起", "rating": "8.5", "address": "新北市瑞芳區九份"},
        {"name": "三芝海景精品旅店", "price": "NT$ 2,500/晚起", "rating": "8.2", "address": "新北市三芝區淺水灣"},
        {"name": "新店翠谷旅店", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "新北市新店區中央路"},
        {"name": "板橋馥台旅行", "price": "NT$ 1,900/晚起", "rating": "8.2", "address": "新北市板橋區文化路一段"},
        {"name": "淡水殼牌倉庫旁民宿", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "新北市淡水區鼻頭街"},
        {"name": "三峽北大商旅", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "新北市三峽區大學路"},
        {"name": "林口長庚商旅", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "新北市林口區文化一路二段"},
        {"name": "汐止假日飯店", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "新北市汐止區大同路三段"},
        {"name": "深坑豆腐老街旅館", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "新北市深坑區北深路三段"},
        {"name": "金山青年活動中心", "price": "NT$ 1,200/晚起", "rating": "7.9", "address": "新北市金山區中山路1號"},
    ],
    "桃園": [
        {"name": "諾富特桃園機場飯店", "price": "NT$ 4,500/晚起", "rating": "8.7", "address": "桃園市大園區航站南路1號"},
        {"name": "桃園喜來登大飯店", "price": "NT$ 4,800/晚起", "rating": "8.9", "address": "桃園市桃園區中正路"},
        {"name": "桃園統御大飯店", "price": "NT$ 2,500/晚起", "rating": "8.3", "address": "桃園市桃園區中山路"},
        {"name": "中壢萬豪酒店", "price": "NT$ 3,800/晚起", "rating": "8.6", "address": "桃園市中壢區元化路"},
        {"name": "大溪老街旅館", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "桃園市大溪區中山路"},
        {"name": "石門水庫景觀飯店", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "桃園市龍潭區石門水庫"},
        {"name": "桃園金典酒店", "price": "NT$ 3,200/晚起", "rating": "8.5", "address": "桃園市桃園區館前路"},
        {"name": "拉拉山山莊", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "桃園市復興區拉拉山"},
        {"name": "青埔商旅", "price": "NT$ 2,000/晚起", "rating": "8.1", "address": "桃園市中壢區高鐵北路"},
        {"name": "桃園長榮桂冠酒店", "price": "NT$ 5,000/晚起", "rating": "8.8", "address": "桃園市中壢區中豐路"},
        {"name": "蘆竹南崁商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "桃園市蘆竹區南竹路"},
        {"name": "桃園華泰王子飯店", "price": "NT$ 3,500/晚起", "rating": "8.5", "address": "桃園市桃園區中正路"},
        {"name": "龍潭大池旁民宿", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "桃園市龍潭區龍潭大池"},
        {"name": "復興山城民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "桃園市復興區三民里"},
        {"name": "八德商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "桃園市八德區大同路"},
    ],
    "台中": [
        {"name": "日月千禧酒店", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "台中市西屯區市政北一路"},
        {"name": "台中金典酒店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "台中市西區館前路"},
        {"name": "台中長榮桂冠酒店", "price": "NT$ 5,000/晚起", "rating": "8.9", "address": "台中市西屯區台灣大道二段"},
        {"name": "逢甲商旅", "price": "NT$ 1,600/晚起", "rating": "8.3", "address": "台中市西屯區逢甲路"},
        {"name": "台中萬楓酒店", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "台中市西屯區台灣大道三段"},
        {"name": "台中亞緻大飯店", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "台中市西區英才路"},
        {"name": "清新溫泉飯店", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "台中市北屯區松竹路三段"},
        {"name": "台中豐邑摩天飯店", "price": "NT$ 2,200/晚起", "rating": "8.2", "address": "台中市南屯區"},
        {"name": "台中星享道酒店", "price": "NT$ 1,900/晚起", "rating": "8.4", "address": "台中市南屯區公益路二段"},
        {"name": "大毅老爺行旅", "price": "NT$ 5,500/晚起", "rating": "9.1", "address": "台中市中區中山路"},
        {"name": "台中永豐棧麗緻酒店", "price": "NT$ 3,600/晚起", "rating": "8.8", "address": "台中市西屯區台灣大道二段689號"},
        {"name": "台中承億文旅", "price": "NT$ 2,500/晚起", "rating": "8.6", "address": "台中市中區中山路"},
        {"name": "武陵富野渡假村", "price": "NT$ 6,000/晚起", "rating": "9.1", "address": "台中市和平區武陵路3號"},
        {"name": "清境老英格蘭莊園", "price": "NT$ 7,500/晚起", "rating": "9.2", "address": "南投縣仁愛鄉大同村定遠新村49號"},
        {"name": "台中福華大飯店", "price": "NT$ 3,000/晚起", "rating": "8.4", "address": "台中市西屯區福上路"},
        {"name": "台中皇品大飯店", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "台中市南區建國路"},
        {"name": "台中中信大飯店", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "台中市南區建國北路"},
        {"name": "台中大飯店", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "台中市北區中清路一段"},
        {"name": "台中悦來商旅", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "台中市北區太平路"},
        {"name": "東豐鐵馬道旁民宿", "price": "NT$ 1,200/晚起", "rating": "7.9", "address": "台中市東勢區"},
    ],
    "台南": [
        {"name": "台南晶英酒店", "price": "NT$ 5,500/晚起", "rating": "9.3", "address": "台南市中西區西門路一段"},
        {"name": "台南大員皇冠假日酒店", "price": "NT$ 4,200/晚起", "rating": "8.8", "address": "台南市安平區"},
        {"name": "台南富信大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "台南市中西區公園路"},
        {"name": "台南永豐棧酒店", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "台南市南區西門路四段"},
        {"name": "台南老爺行旅", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "台南市中西區西門路二段"},
        {"name": "台南亞緻大飯店", "price": "NT$ 3,600/晚起", "rating": "8.7", "address": "台南市北區成功路"},
        {"name": "台南商務會館", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "台南市東區"},
        {"name": "台南萬怡酒店", "price": "NT$ 5,000/晚起", "rating": "9.1", "address": "台南市中西區民族路二段"},
        {"name": "台南大億麗緻酒店", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "台南市中西區西門路一段"},
        {"name": "承億文旅台南糖果城堡", "price": "NT$ 2,200/晚起", "rating": "8.5", "address": "台南市北區成功路"},
        {"name": "台南古都商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台南市中西區"},
        {"name": "台南福華大飯店", "price": "NT$ 3,000/晚起", "rating": "8.4", "address": "台南市中西區公園路67號"},
        {"name": "奇美博物館附近民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台南市仁德區"},
        {"name": "關子嶺溫泉大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "台南市白河區關子嶺"},
        {"name": "七股鹽山旁民宿", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "台南市七股區"},
        {"name": "台南安平老街旅店", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台南市安平區安平路"},
        {"name": "安平艾葳飯店", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "台南市安平區"},
        {"name": "台南桂田酒店", "price": "NT$ 6,500/晚起", "rating": "9.2", "address": "台南市中西區"},
        {"name": "台南長榮酒店", "price": "NT$ 5,200/晚起", "rating": "8.9", "address": "台南市北區"},
        {"name": "台南東璽精品旅館", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "台南市東區"},
    ],
    "高雄": [
        {"name": "高雄漢來大飯店", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "高雄市前金區成功一路"},
        {"name": "高雄國賓大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "高雄市前金區民生二路"},
        {"name": "高雄福華大飯店", "price": "NT$ 3,200/晚起", "rating": "8.5", "address": "高雄市苓雅區四維三路"},
        {"name": "駁二艾尼斯旅店", "price": "NT$ 1,800/晚起", "rating": "8.7", "address": "高雄市鹽埕區"},
        {"name": "高雄萬豪酒店", "price": "NT$ 6,500/晚起", "rating": "9.3", "address": "高雄市前鎮區中鋼路"},
        {"name": "高雄寒軒國際大飯店", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "高雄市苓雅區四維三路33號"},
        {"name": "高雄義大天悅飯店", "price": "NT$ 5,200/晚起", "rating": "9.0", "address": "高雄市大樹區三和里學城路一段"},
        {"name": "高雄旗津海岸汽車旅館", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "高雄市旗津區廟前路"},
        {"name": "高雄承億文旅", "price": "NT$ 2,500/晚起", "rating": "8.6", "address": "高雄市前金區中正四路"},
        {"name": "高雄天閣酒店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "高雄市前鎮區成功二路"},
        {"name": "高雄金典酒店", "price": "NT$ 5,800/晚起", "rating": "9.1", "address": "高雄市苓雅區自強三路"},
        {"name": "高雄商務大飯店", "price": "NT$ 1,200/晚起", "rating": "7.9", "address": "高雄市三民區"},
        {"name": "高雄中信大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "高雄市苓雅區四維三路"},
        {"name": "西子灣沙灘會館", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "高雄市鼓山區蓮海路"},
        {"name": "高雄長谷飯店", "price": "NT$ 2,200/晚起", "rating": "8.2", "address": "高雄市新興區中正四路"},
        {"name": "美濃客棧", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "高雄市美濃區中山路"},
        {"name": "高雄翰品酒店", "price": "NT$ 4,200/晚起", "rating": "8.8", "address": "高雄市前鎮區"},
        {"name": "高雄維多利亞酒店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "高雄市苓雅區"},
        {"name": "高雄佳寶汽車旅館", "price": "NT$ 1,400/晚起", "rating": "8.0", "address": "高雄市三民區九如二路"},
        {"name": "高雄港都商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "高雄市鹽埕區"},
    ],
    "基隆": [
        {"name": "基隆長榮桂冠酒店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "基隆市中正區北寧路"},
        {"name": "基隆都督大飯店", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "基隆市中正區"},
        {"name": "基隆海景商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "基隆市中山區"},
        {"name": "正濱漁港旅店", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "基隆市中正區正濱漁港"},
        {"name": "基隆和平島渡假中心", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "基隆市中正區平一路360號"},
        {"name": "八斗子海景民宿", "price": "NT$ 1,800/晚起", "rating": "8.3", "address": "基隆市中正區八斗子"},
        {"name": "基隆成功旅館", "price": "NT$ 1,200/晚起", "rating": "8.0", "address": "基隆市仁愛區成功一路"},
        {"name": "基隆亞太大飯店", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "基隆市中正區義二路"},
        {"name": "信義商務旅館", "price": "NT$ 1,400/晚起", "rating": "8.1", "address": "基隆市仁愛區信義區"},
        {"name": "基隆海洋廣場旅館", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "基隆市中正區港西街"},
        {"name": "暖暖溫泉旅館", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "基隆市暖暖區暖暖街"},
        {"name": "碧砂漁港旁旅館", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "基隆市中正區碧砂漁港"},
        {"name": "基隆金龍大飯店", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "基隆市仁愛區仁三路"},
        {"name": "基隆輝煌商旅", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "基隆市中山區中山一路"},
        {"name": "七堵商旅", "price": "NT$ 1,300/晚起", "rating": "7.9", "address": "基隆市七堵區興中路"},
    ],
    "新竹": [
        {"name": "新竹喜來登大飯店", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "新竹市東區中央路"},
        {"name": "新竹老爺行旅", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "新竹市東區中正路"},
        {"name": "新竹福華大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "新竹市東區中山路"},
        {"name": "新竹璞石行旅", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "新竹市北區明湖路"},
        {"name": "竹北商旅", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "新竹縣竹北市光明一路"},
        {"name": "內灣山城旅館", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "新竹縣橫山鄉內灣村"},
        {"name": "清泉溫泉山莊", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "新竹縣五峰鄉清泉村"},
        {"name": "司馬庫斯山莊", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "新竹縣尖石鄉司馬庫斯"},
        {"name": "新竹豪景大飯店", "price": "NT$ 2,200/晚起", "rating": "8.2", "address": "新竹市東區中正路"},
        {"name": "新竹華邑酒店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "新竹市北區中華路"},
        {"name": "薰衣草森林渡假民宿", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "新竹縣尖石鄉新樂村"},
        {"name": "新竹科學城商旅", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "新竹市東區力行路"},
        {"name": "峨眉湖景民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "新竹縣峨眉鄉"},
        {"name": "北埔客家民宿", "price": "NT$ 1,600/晚起", "rating": "8.2", "address": "新竹縣北埔鄉北埔老街"},
        {"name": "新竹飛輪大飯店", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "新竹市北區"},
    ],
    "苗栗": [
        {"name": "泰安溫泉大飯店", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "苗栗縣泰安鄉泰安溫泉"},
        {"name": "苗栗伊仕丹大飯店", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "苗栗市縣府路"},
        {"name": "三義木雕旅館", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "苗栗縣三義鄉廣聲新城"},
        {"name": "南庄山城民宿", "price": "NT$ 2,000/晚起", "rating": "8.4", "address": "苗栗縣南庄鄉南庄老街"},
        {"name": "大湖草莓農場旅館", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "苗栗縣大湖鄉"},
        {"name": "飛牛牧場渡假村", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "苗栗縣通霄鎮飛牛牧場"},
        {"name": "苑裡藺草編織民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "苗栗縣苑裡鎮"},
        {"name": "頭屋明德水庫民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "苗栗縣頭屋鄉明德村"},
        {"name": "苗栗客家文化渡假村", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "苗栗縣銅鑼鄉銅科南路"},
        {"name": "獅頭山宗教民宿", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "苗栗縣南庄鄉獅山村"},
        {"name": "西湖渡假村旅館", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "苗栗縣三灣鄉西湖村"},
        {"name": "後龍海邊民宿", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "苗栗縣後龍鎮海邊路"},
        {"name": "銅鑼工業區旁商旅", "price": "NT$ 1,800/晚起", "rating": "8.0", "address": "苗栗縣銅鑼鄉"},
        {"name": "竹南商務飯店", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "苗栗縣竹南鎮中正路"},
        {"name": "通霄觀海民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "苗栗縣通霄鎮通霄里"},
    ],
    "彰化": [
        {"name": "彰化福泰商務飯店", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "彰化市中正路一段"},
        {"name": "鹿港老街旅館", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "彰化縣鹿港鎮中山路"},
        {"name": "彰化城市商旅", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "彰化市彰南路"},
        {"name": "員林假日商旅", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "彰化縣員林市中正路"},
        {"name": "田尾花卉民宿", "price": "NT$ 1,800/晚起", "rating": "8.3", "address": "彰化縣田尾鄉公路花園"},
        {"name": "二林葡萄酒莊旅館", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "彰化縣二林鎮"},
        {"name": "溪湖糖廠旁民宿", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "彰化縣溪湖鎮彰水路"},
        {"name": "彰化市大飯店", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "彰化市中正路二段"},
        {"name": "王功漁港海景民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "彰化縣芳苑鄉王功漁港"},
        {"name": "北斗商旅", "price": "NT$ 1,400/晚起", "rating": "8.0", "address": "彰化縣北斗鎮斗中路"},
        {"name": "芬園休閒農場民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "彰化縣芬園鄉"},
        {"name": "彰化香格里拉農場", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "彰化縣秀水鄉"},
        {"name": "大村葡萄民宿", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "彰化縣大村鄉"},
        {"name": "福興海洋民宿", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "彰化縣福興鄉"},
        {"name": "和美城市商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "彰化縣和美鎮"},
    ],
    "南投": [
        {"name": "日月潭涵碧樓大飯店", "price": "NT$ 10,000/晚起", "rating": "9.5", "address": "南投縣魚池鄉日月村涵碧路142號"},
        {"name": "日月行館", "price": "NT$ 8,000/晚起", "rating": "9.3", "address": "南投縣魚池鄉日月村中正路101號"},
        {"name": "清境老英格蘭莊園", "price": "NT$ 7,500/晚起", "rating": "9.2", "address": "南投縣仁愛鄉大同村定遠新村49號"},
        {"name": "清境農場山莊", "price": "NT$ 5,000/晚起", "rating": "8.9", "address": "南投縣仁愛鄉大同村壽亭巷170號"},
        {"name": "溪頭米堤大飯店", "price": "NT$ 4,800/晚起", "rating": "8.8", "address": "南投縣鹿谷鄉森林路79號"},
        {"name": "九族文化村附近民宿", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "南投縣魚池鄉大林村"},
        {"name": "埔里紙教堂旁旅館", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "南投縣埔里鎮桃米里"},
        {"name": "南投瑞品商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "南投市三和路"},
        {"name": "竹山鎮商旅", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "南投縣竹山鎮中正路"},
        {"name": "杉林溪渡假村", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "南投縣竹山鎮大鞍里杉林溪路"},
        {"name": "合歡山莊", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "南投縣仁愛鄉合歡山"},
        {"name": "惠蓀林場山莊", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "南投縣仁愛鄉互助村"},
        {"name": "奧萬大楓情莊園", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "南投縣仁愛鄉松林村"},
        {"name": "日月潭大淶閣大飯店", "price": "NT$ 6,500/晚起", "rating": "9.1", "address": "南投縣魚池鄉水社村"},
        {"name": "鹿谷鄉凍頂茶民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "南投縣鹿谷鄉凍頂巷"},
    ],
    "雲林": [
        {"name": "劍湖山王子大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "雲林縣古坑鄉坑口村1號"},
        {"name": "斗六商務旅館", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "雲林縣斗六市府文路"},
        {"name": "西螺老街旅店", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "雲林縣西螺鎮太和路"},
        {"name": "北港朝天宮旁旅館", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "雲林縣北港鎮中山路"},
        {"name": "古坑咖啡山莊", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "雲林縣古坑鄉草嶺村"},
        {"name": "虎尾糖廠旁民宿", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "雲林縣虎尾鎮廉使里"},
        {"name": "草嶺山莊", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "雲林縣古坑鄉草嶺村"},
        {"name": "口湖海邊民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "雲林縣口湖鄉成龍村"},
        {"name": "麥寮工業區商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "雲林縣麥寮鄉"},
        {"name": "台西觀光漁市旁民宿", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "雲林縣台西鄉"},
        {"name": "元長花生故鄉民宿", "price": "NT$ 1,400/晚起", "rating": "7.9", "address": "雲林縣元長鄉"},
        {"name": "四湖農村民宿", "price": "NT$ 1,300/晚起", "rating": "7.9", "address": "雲林縣四湖鄉"},
        {"name": "土庫旅館", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "雲林縣土庫鎮中正路"},
        {"name": "二崙客家民宿", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "雲林縣二崙鄉"},
        {"name": "林內鄉生態民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "雲林縣林內鄉"},
    ],
    "嘉義": [
        {"name": "嘉義耐斯王子大飯店", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "嘉義市西區世賢路二段"},
        {"name": "阿里山賓館", "price": "NT$ 5,500/晚起", "rating": "8.9", "address": "嘉義縣阿里山鄉中正村16號"},
        {"name": "高山青旅館", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "嘉義縣阿里山鄉"},
        {"name": "嘉義福泰商務飯店", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "嘉義市東區中山路"},
        {"name": "奮起湖老街民宿", "price": "NT$ 2,000/晚起", "rating": "8.4", "address": "嘉義縣竹崎鄉奮起湖"},
        {"name": "嘉義香格里拉大飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "嘉義市東區垂楊路"},
        {"name": "布袋漁港旁民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "嘉義縣布袋鎮"},
        {"name": "民雄農村民宿", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "嘉義縣民雄鄉"},
        {"name": "達邦部落生態民宿", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "嘉義縣阿里山鄉達邦村"},
        {"name": "嘉義市商旅", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "嘉義市中正路"},
        {"name": "水上旅館", "price": "NT$ 1,400/晚起", "rating": "7.9", "address": "嘉義縣水上鄉"},
        {"name": "鰲鼓濕地旁民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "嘉義縣東石鄉"},
        {"name": "太平老街旅館", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "嘉義縣大林鎮"},
        {"name": "嘉義長庚商旅", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "嘉義市東區"},
        {"name": "嘉義好萊塢大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "嘉義市東區興業西路"},
    ],
    "屏東": [
        {"name": "墾丁夏都沙灘酒店", "price": "NT$ 5,500/晚起", "rating": "9.0", "address": "屏東縣恆春鎮墾丁路451號"},
        {"name": "墾丁凱撒大飯店", "price": "NT$ 4,800/晚起", "rating": "8.9", "address": "屏東縣恆春鎮墾丁路"},
        {"name": "墾丁福容大飯店", "price": "NT$ 4,000/晚起", "rating": "8.7", "address": "屏東縣恆春鎮南灣路"},
        {"name": "恆春古城旅舍", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "屏東縣恆春鎮中正路"},
        {"name": "小琉球海邊民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "屏東縣琉球鄉"},
        {"name": "東港商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "屏東縣東港鎮"},
        {"name": "四重溪溫泉旅館", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "屏東縣車城鄉溫泉村"},
        {"name": "屏東市福華大飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "屏東市中山路"},
        {"name": "霧台部落山莊", "price": "NT$ 3,200/晚起", "rating": "8.7", "address": "屏東縣霧台鄉"},
        {"name": "三地門排灣族民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "屏東縣三地門鄉"},
        {"name": "大鵬灣水岸旅館", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "屏東縣東港鎮大鵬灣"},
        {"name": "牡丹鄉旭海山莊", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "屏東縣牡丹鄉旭海村"},
        {"name": "海生館旁旅館", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "屏東縣車城鄉後灣村"},
        {"name": "潮州商務旅館", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "屏東縣潮州鎮"},
        {"name": "佳冬洋樓民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "屏東縣佳冬鄉"},
    ],
    "宜蘭": [
        {"name": "礁溪老爺大飯店", "price": "NT$ 6,500/晚起", "rating": "9.3", "address": "宜蘭縣礁溪鄉五峰路69號"},
        {"name": "礁溪長榮鳳凰酒店", "price": "NT$ 5,500/晚起", "rating": "9.1", "address": "宜蘭縣礁溪鄉大忠村五峰路"},
        {"name": "礁溪寒沐酒店", "price": "NT$ 7,000/晚起", "rating": "9.4", "address": "宜蘭縣礁溪鄉中山路二段"},
        {"name": "宜蘭力麗觀光飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "宜蘭市建軍路"},
        {"name": "蘇澳冷泉旁旅館", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "宜蘭縣蘇澳鎮冷泉路"},
        {"name": "羅東商旅", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "宜蘭縣羅東鎮中正北路"},
        {"name": "頭城海邊民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "宜蘭縣頭城鎮"},
        {"name": "冬山河旁旅館", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "宜蘭縣冬山鄉冬山路"},
        {"name": "太平山松濤苑", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "宜蘭縣大同鄉太平山"},
        {"name": "棲蘭山莊", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "宜蘭縣大同鄉棲蘭村"},
        {"name": "員山農場民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "宜蘭縣員山鄉"},
        {"name": "龜山島海景民宿", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "宜蘭縣頭城鎮"},
        {"name": "三星蔥蒜農場民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "宜蘭縣三星鄉"},
        {"name": "宜蘭城市商旅", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "宜蘭市神農路"},
        {"name": "南澳溫泉旅館", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "宜蘭縣南澳鄉南澳溫泉"},
    ],
    "花蓮": [
        {"name": "花蓮理想大地度假村", "price": "NT$ 6,500/晚起", "rating": "9.1", "address": "花蓮縣壽豐鄉理想路1號"},
        {"name": "花蓮翰品酒店", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "花蓮市國聯一路51號"},
        {"name": "花蓮美侖大飯店", "price": "NT$ 4,200/晚起", "rating": "8.7", "address": "花蓮市林森路1號"},
        {"name": "花蓮統帥大飯店", "price": "NT$ 2,500/晚起", "rating": "8.3", "address": "花蓮市中山路2號"},
        {"name": "花蓮遠雄悅來大飯店", "price": "NT$ 7,000/晚起", "rating": "9.2", "address": "花蓮縣壽豐鄉鹽寮村福德180號"},
        {"name": "花蓮馥麗溫泉大飯店", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "花蓮縣秀林鄉崇德村"},
        {"name": "花蓮星空渡假村", "price": "NT$ 5,000/晚起", "rating": "8.8", "address": "花蓮縣壽豐鄉"},
        {"name": "花蓮鯉魚潭大飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "花蓮縣壽豐鄉池南路"},
        {"name": "花蓮瑞穗天合國際觀光酒店", "price": "NT$ 8,000/晚起", "rating": "9.4", "address": "花蓮縣瑞穗鄉溫泉路"},
        {"name": "花蓮商旅", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "花蓮市中山路"},
        {"name": "花蓮福容大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "花蓮市海岸路51號"},
        {"name": "花蓮頤鈁商旅", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "花蓮市國聯二路"},
        {"name": "七星潭海景民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "花蓮縣新城鄉七星街"},
        {"name": "太魯閣晶英酒店", "price": "NT$ 9,000/晚起", "rating": "9.5", "address": "花蓮縣秀林鄉天祥路"},
        {"name": "花蓮光復糖廠旁民宿", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "花蓮縣光復鄉"},
        {"name": "秀姑巒溪旁民宿", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "花蓮縣瑞穗鄉"},
        {"name": "花蓮亞士都飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "花蓮市中山路"},
        {"name": "花蓮山月村落", "price": "NT$ 5,500/晚起", "rating": "9.0", "address": "花蓮縣壽豐鄉"},
        {"name": "吉安幸福農場民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "花蓮縣吉安鄉"},
        {"name": "六十石山民宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "花蓮縣富里鄉"},
    ],
    "台東": [
        {"name": "知本老爺大酒店", "price": "NT$ 5,500/晚起", "rating": "9.1", "address": "台東縣卑南鄉知本溫泉路"},
        {"name": "台東娜路彎大酒店", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "台東市中興路二段"},
        {"name": "綠島朝日溫泉民宿", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "台東縣綠島鄉"},
        {"name": "蘭嶼朗島民宿", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "台東縣蘭嶼鄉"},
        {"name": "池上天堂路民宿", "price": "NT$ 2,000/晚起", "rating": "8.4", "address": "台東縣池上鄉伯朗大道"},
        {"name": "鹿野熱氣球民宿", "price": "NT$ 2,500/晚起", "rating": "8.6", "address": "台東縣鹿野鄉高台"},
        {"name": "台東桂田酒店", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "台東市中山路"},
        {"name": "台東富野渡假酒店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "台東市中華路四段"},
        {"name": "知本溫泉旅館", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "台東縣卑南鄉知本溫泉路"},
        {"name": "成功漁港旁民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台東縣成功鎮"},
        {"name": "都蘭藝術部落民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "台東縣東河鄉都蘭村"},
        {"name": "太麻里金針山民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台東縣太麻里鄉金針山"},
        {"name": "台東知本悠活麗緻酒店", "price": "NT$ 6,000/晚起", "rating": "9.2", "address": "台東縣卑南鄉溫泉村"},
        {"name": "卑南文化公園旁民宿", "price": "NT$ 1,500/晚起", "rating": "8.1", "address": "台東市康樂路"},
        {"name": "關山親水公園民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台東縣關山鎮"},
    ],
}

# Budget-level price filter thresholds (NT$ per night)
BUDGET_MAX_PRICE: dict[str, int] = {
    "經濟": 2000,
    "中等": 5000,
    "豪華": 999999,
}


class HotelScraper(BaseScraper):
    """Scrapes hotel data from Booking.com for a given Taiwan city.

    Parameters
    ----------
    city : str
        Target city (台北、新北、桃園、台中、台南、高雄、基隆、新竹、苗栗、
        彰化、南投、雲林、嘉義、屏東、宜蘭、花蓮、台東).
    check_in : str
        Check-in date in ``YYYY-MM-DD`` format.
    check_out : str
        Check-out date in ``YYYY-MM-DD`` format.
    budget : str
        One of ``經濟``、``中等``、``豪華``.
    headless : bool
        Whether to run Chromium headlessly (default ``True``).
    max_items : int
        Maximum number of hotels to return (default ``20``).
    """

    def __init__(
        self,
        city: str,
        check_in: str = "",
        check_out: str = "",
        budget: str = "中等",
        headless: bool = True,
        max_items: int = 20,
    ):
        super().__init__(headless=headless)
        self.city = city
        self.check_in = check_in
        self.check_out = check_out
        self.budget = budget
        self.max_items = max_items

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch(self, **kwargs) -> list[Hotel]:
        """Fetch hotel listings.

        Attempts live scraping; falls back to static data on failure.
        """
        try:
            hotels = await self._scrape()
            if not hotels:
                hotels = self._fallback_hotels()
            return hotels[: self.max_items]
        except Exception:
            return self._fallback_hotels()[: self.max_items]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_price_rating(price_str: str) -> str:
        """Derive a cost-level indicator ($, $$, $$$) from a price string.

        Parses the first numeric value from strings like ``"NT$ 3,800/晚起"``
        and maps it to a tier:

        * ``$``   – NT$ < 2,000 / night  (economy)
        * ``$$``  – NT$ 2,000–5,000 / night (moderate)
        * ``$$$`` – NT$ > 5,000 / night  (luxury)
        """
        try:
            # Extract the first run of digits (with optional comma separators)
            # from strings like "NT$ 3,800/晚起" or "3800 TWD per night"
            match = re.search(r"[\d,]+", price_str.replace("NT$", "").lstrip())
            if not match:
                return "$$"
            amount = int(match.group().replace(",", ""))
        except (ValueError, AttributeError):
            return "$$"

        if amount < 2000:
            return "$"
        if amount <= 5000:
            return "$$"
        return "$$$"

    def _build_url(self) -> str:
        """Construct the Booking.com search URL."""
        city_en = BOOKING_CITY_NAMES.get(self.city, self.city)
        params = f"?ss={quote_plus(city_en)}&lang=zh-tw&sb=1&src=index&src_elem=sb"
        if self.check_in:
            parts = self.check_in.split("-")
            if len(parts) == 3:
                params += f"&checkin_year={parts[0]}&checkin_month={parts[1]}&checkin_monthday={parts[2]}"
        if self.check_out:
            parts = self.check_out.split("-")
            if len(parts) == 3:
                params += f"&checkout_year={parts[0]}&checkout_month={parts[1]}&checkout_monthday={parts[2]}"
        return BOOKING_BASE + params

    async def _scrape(self) -> list[Hotel]:
        """Launch stealth browser and scrape Booking.com results."""
        hotels: list[Hotel] = []
        url = self._build_url()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1366, "height": 768},
                locale="zh-TW",
                timezone_id="Asia/Taipei",
            )
            page = await context.new_page()

            if _STEALTH_AVAILABLE:
                await stealth_async(page)

            try:
                await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                await self.random_delay(2.5, 5.0)
                await self._human_scroll(page)
                await self.random_delay(1.0, 2.0)

                # Try multiple selector strategies for resilience
                for selector in [
                    "div[data-testid='property-card']",
                    "div.sr_property_block",
                    "div.hotel_itm_inner",
                ]:
                    cards = await page.query_selector_all(selector)
                    if cards:
                        for card in cards[: self.max_items]:
                            hotel = await self._parse_card(card)
                            if hotel:
                                hotels.append(hotel)
                        break
            finally:
                await context.close()
                await browser.close()

        return hotels

    @staticmethod
    async def _human_scroll(page: Page) -> None:
        """Simulate slow human-like scrolling."""
        for _ in range(random.randint(4, 7)):
            scroll_y = random.randint(250, 600)
            await page.evaluate(f"window.scrollBy(0, {scroll_y})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
            # Occasionally scroll back up slightly
            if random.random() < 0.2:
                await page.evaluate(f"window.scrollBy(0, -{random.randint(100, 300)})")
                await asyncio.sleep(random.uniform(0.3, 0.8))

    async def _parse_card(self, card) -> Hotel | None:
        """Extract a :class:`Hotel` from a property card element."""
        try:
            name_el = await card.query_selector(
                "[data-testid='title'], .sr-hotel__name, h3.hotel-name"
            )
            name = (await name_el.inner_text()).strip() if name_el else ""
            if not name:
                return None

            price_el = await card.query_selector(
                "[data-testid='price-and-discounted-price'], .bui-price-display__value, .price"
            )
            price = (await price_el.inner_text()).strip() if price_el else "價格請洽官網"

            rating_el = await card.query_selector(
                "[data-testid='review-score'] div, .bui-review-score__badge, .score"
            )
            rating = (await rating_el.inner_text()).strip() if rating_el else "N/A"

            addr_el = await card.query_selector(
                "[data-testid='address'], .hp_address_subtitle, .address"
            )
            address = (await addr_el.inner_text()).strip() if addr_el else ""

            img_el = await card.query_selector("img")
            image_url = ""
            if img_el:
                image_url = (await img_el.get_attribute("src")) or ""

            return Hotel(
                name=name,
                price=price,
                rating=rating,
                price_rating=self._compute_price_rating(price),
                address=address,
                city=self.city,
                image_url=image_url,
                source_url=self._build_url(),
            )
        except Exception:
            return None

    def _fallback_hotels(self) -> list[Hotel]:
        """Return curated static hotel data filtered by budget."""
        data = FALLBACK_HOTELS.get(self.city, [])
        max_price = BUDGET_MAX_PRICE.get(self.budget, 999999)
        results = []
        for item in data:
            # Parse first numeric segment from price string for filtering
            try:
                raw = item["price"].replace("NT$", "").replace(",", "").split("/")[0].strip()
                price_val = int("".join(c for c in raw if c.isdigit()))
            except (ValueError, IndexError):
                price_val = 0
            if price_val <= max_price:
                results.append(
                    Hotel(
                        name=item["name"],
                        price=item["price"],
                        rating=item["rating"],
                        price_rating=self._compute_price_rating(item["price"]),
                        address=item.get("address", ""),
                        city=self.city,
                    )
                )
        return results
