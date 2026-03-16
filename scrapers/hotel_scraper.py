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
    "基隆": "Keelung, Taiwan",
    "新竹": "Hsinchu, Taiwan",
    "苗栗": "Miaoli, Taiwan",
    "彰化": "Changhua, Taiwan",
    "南投": "Nantou, Taiwan",
    "雲林": "Yunlin, Taiwan",
    "嘉義": "Chiayi, Taiwan",
    "台南": "Tainan, Taiwan",
    "高雄": "Kaohsiung, Taiwan",
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
        {"name": "台北文華東方酒店", "price": "NT$ 9,500/晚起", "rating": "9.5", "address": "台北市松山區敦化北路166號"},
        {"name": "台北柯達大飯店", "price": "NT$ 2,800/晚起", "rating": "8.3", "address": "台北市中山區林森北路"},
        {"name": "台北意舍酒店", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "台北市大安區仁愛路四段"},
        {"name": "台北富邦大飯店", "price": "NT$ 4,500/晚起", "rating": "8.8", "address": "台北市中正區南昌路二段"},
        {"name": "台北大倉久和大飯店", "price": "NT$ 8,000/晚起", "rating": "9.4", "address": "台北市中山區南京東路一段9號"},
        {"name": "六福皇宮", "price": "NT$ 5,800/晚起", "rating": "9.0", "address": "台北市中山區民生東路三段"},
        {"name": "台北亞都麗緻大飯店", "price": "NT$ 6,200/晚起", "rating": "9.1", "address": "台北市中山區民族東路41號"},
        {"name": "捷絲旅台北西門", "price": "NT$ 2,000/晚起", "rating": "8.5", "address": "台北市萬華區漢中街"},
        {"name": "和逸飯店台北忠孝館", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "台北市大安區忠孝東路四段"},
        {"name": "台北金普頓大安酒店", "price": "NT$ 7,800/晚起", "rating": "9.3", "address": "台北市大安區仁愛路"},
        {"name": "台北承億文旅", "price": "NT$ 2,400/晚起", "rating": "8.4", "address": "台北市大同區承德路一段"},
        {"name": "台北聖禧行旅", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "台北市大同區民族西路"},
        {"name": "台北旅印商旅", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "台北市中山區"},
        {"name": "台北松山意舍酒店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "台北市松山區敦化北路"},
        {"name": "台北喜悅旅店", "price": "NT$ 1,200/晚起", "rating": "7.9", "address": "台北市萬華區"},
        {"name": "台北商旅", "price": "NT$ 1,900/晚起", "rating": "8.2", "address": "台北市大同區"},
        {"name": "台北公寓式酒店", "price": "NT$ 2,500/晚起", "rating": "8.3", "address": "台北市信義區"},
        {"name": "台北希爾頓酒店", "price": "NT$ 5,000/晚起", "rating": "8.9", "address": "台北市中正區忠孝西路"},
    ],
    "新北": [
        {"name": "福容大飯店淡水漁人碼頭", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "新北市淡水區觀海路83號"},
        {"name": "淡水亞太飯店", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "新北市淡水區"},
        {"name": "烏來馥蘭朵溫泉度假酒店", "price": "NT$ 5,500/晚起", "rating": "9.0", "address": "新北市烏來區烏來街"},
        {"name": "烏來春暖溫泉民宿", "price": "NT$ 2,200/晚起", "rating": "8.5", "address": "新北市烏來區"},
        {"name": "板橋凱撒大飯店", "price": "NT$ 4,200/晚起", "rating": "8.8", "address": "新北市板橋區縣民大道二段"},
        {"name": "新北新板希爾頓酒店", "price": "NT$ 6,000/晚起", "rating": "9.2", "address": "新北市板橋區新板特區"},
        {"name": "三重商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "新北市三重區"},
        {"name": "中和商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "新北市中和區"},
        {"name": "新店碧潭溫泉飯店", "price": "NT$ 3,000/晚起", "rating": "8.3", "address": "新北市新店區新店路"},
        {"name": "九份山城民宿", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "新北市瑞芳區九份"},
        {"name": "平溪老街民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "新北市平溪區"},
        {"name": "野柳海洋世界渡假酒店", "price": "NT$ 3,500/晚起", "rating": "8.5", "address": "新北市萬里區野柳"},
        {"name": "淡水漁人碼頭商旅", "price": "NT$ 2,000/晚起", "rating": "8.1", "address": "新北市淡水區"},
        {"name": "新莊行旅", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "新北市新莊區"},
        {"name": "土城福容大飯店", "price": "NT$ 3,200/晚起", "rating": "8.4", "address": "新北市土城區學府路"},
        {"name": "鶯歌陶瓷民宿", "price": "NT$ 1,900/晚起", "rating": "8.3", "address": "新北市鶯歌區"},
        {"name": "三峽老街特色旅館", "price": "NT$ 1,600/晚起", "rating": "8.1", "address": "新北市三峽區"},
        {"name": "烏來溫泉山莊", "price": "NT$ 4,500/晚起", "rating": "8.8", "address": "新北市烏來區"},
        {"name": "金山皇冠假日酒店", "price": "NT$ 4,800/晚起", "rating": "8.9", "address": "新北市金山區"},
        {"name": "石碇山城民宿", "price": "NT$ 2,000/晚起", "rating": "8.4", "address": "新北市石碇區"},
        {"name": "坪林茶鄉民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "新北市坪林區"},
        {"name": "貢寮福隆海景民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "新北市貢寮區"},
        {"name": "深坑老街旅宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "新北市深坑區"},
        {"name": "蘆洲商旅", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "新北市蘆洲區"},
        {"name": "汐止商務旅館", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "新北市汐止區"},
        {"name": "泰山商旅", "price": "NT$ 1,300/晚起", "rating": "7.7", "address": "新北市泰山區"},
        {"name": "樹林商旅", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "新北市樹林區"},
        {"name": "永和商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "新北市永和區"},
        {"name": "雙溪山村民宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "新北市雙溪區"},
        {"name": "萬里溫泉民宿", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "新北市萬里區"},
    ],
    "桃園": [
        {"name": "桃園大溪老爺行旅", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "桃園市大溪區"},
        {"name": "桃園萬豪酒店", "price": "NT$ 5,500/晚起", "rating": "9.1", "address": "桃園市桃園區"},
        {"name": "諾富特桃園機場酒店", "price": "NT$ 4,000/晚起", "rating": "8.7", "address": "桃園市大園區機場路"},
        {"name": "桃園大園格逸雅旅", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "桃園市大園區"},
        {"name": "桃園中壢商旅", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "桃園市中壢區"},
        {"name": "大溪威斯汀度假酒店", "price": "NT$ 6,500/晚起", "rating": "9.2", "address": "桃園市大溪區"},
        {"name": "桃園福朋喜來登", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "桃園市桃園區"},
        {"name": "中壢歐悅商旅", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "桃園市中壢區"},
        {"name": "八德商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "桃園市八德區"},
        {"name": "桃園統領大飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "桃園市桃園區"},
        {"name": "平鎮大飯店", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "桃園市平鎮區"},
        {"name": "龍潭大池旁民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "桃園市龍潭區"},
        {"name": "楊梅好漾民宿", "price": "NT$ 1,700/晚起", "rating": "8.1", "address": "桃園市楊梅區"},
        {"name": "新屋民宿", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "桃園市新屋區"},
        {"name": "觀音海岸民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "桃園市觀音區"},
        {"name": "桃園機場捷運沿線商旅", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "桃園市蘆竹區"},
        {"name": "石門水庫渡假民宿", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "桃園市龍潭區石門"},
        {"name": "復興山城民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "桃園市復興區"},
        {"name": "大溪老街民宿", "price": "NT$ 2,500/晚起", "rating": "8.6", "address": "桃園市大溪區"},
        {"name": "拉拉山山莊", "price": "NT$ 3,200/晚起", "rating": "8.7", "address": "桃園市復興區拉拉山"},
        {"name": "桃園亞緻大飯店", "price": "NT$ 4,200/晚起", "rating": "8.9", "address": "桃園市桃園區中正路"},
        {"name": "中壢加賀屋", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "桃園市中壢區"},
        {"name": "桃園老爺行旅", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "桃園市桃園區"},
        {"name": "蘆竹商旅", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "桃園市蘆竹區"},
        {"name": "林口商旅", "price": "NT$ 1,800/晚起", "rating": "8.0", "address": "桃園市龜山區"},
        {"name": "桃園青年旅館", "price": "NT$ 800/晚起", "rating": "7.7", "address": "桃園市桃園區"},
        {"name": "中壢駅前商旅", "price": "NT$ 1,900/晚起", "rating": "8.2", "address": "桃園市中壢區中山路"},
        {"name": "桃源仙谷溫泉民宿", "price": "NT$ 4,000/晚起", "rating": "8.9", "address": "桃園市復興區華陵里"},
        {"name": "大溪威斯頓大飯店", "price": "NT$ 5,000/晚起", "rating": "9.0", "address": "桃園市大溪區中央路"},
        {"name": "桃園欣欣大飯店", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "桃園市桃園區"},
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
        {"name": "台中豪景大酒店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "台中市西屯區"},
        {"name": "台中福華大飯店", "price": "NT$ 4,200/晚起", "rating": "8.8", "address": "台中市中港路"},
        {"name": "武陵富野渡假村", "price": "NT$ 6,800/晚起", "rating": "9.3", "address": "台中市和平區武陵路"},
        {"name": "台中全國大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "台中市西屯區"},
        {"name": "台中愛麗絲國際大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "台中市西屯區"},
        {"name": "台中商旅", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "台中市中區"},
        {"name": "台中霧峰民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台中市霧峰區"},
        {"name": "台中新社山城民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "台中市新社區"},
        {"name": "谷關溫泉山莊", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "台中市和平區谷關"},
        {"name": "台中萬怡酒店", "price": "NT$ 5,200/晚起", "rating": "9.0", "address": "台中市西屯區市政路"},
        {"name": "台中林酒店", "price": "NT$ 7,000/晚起", "rating": "9.4", "address": "台中市西屯區惠來路二段"},
        {"name": "台中格萊天漾大飯店", "price": "NT$ 4,000/晚起", "rating": "8.9", "address": "台中市北屯區文心路四段"},
        {"name": "台中意舍酒店", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "台中市北區"},
        {"name": "台中紅點文旅", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台中市中區中山路"},
        {"name": "台中加賀屋大飯店", "price": "NT$ 6,500/晚起", "rating": "9.2", "address": "台中市西屯區台灣大道"},
        {"name": "逢甲住宿", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "台中市西屯區"},
        {"name": "台中鳥日商旅", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "台中市烏日區"},
        {"name": "台中嘎拉旅店", "price": "NT$ 1,700/晚起", "rating": "8.1", "address": "台中市西屯區"},
    ],
    "基隆": [
        {"name": "基隆長榮桂冠酒店", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "基隆市仁愛區麥金路62號"},
        {"name": "基隆海景大飯店", "price": "NT$ 2,500/晚起", "rating": "8.3", "address": "基隆市中正區"},
        {"name": "基隆商旅", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "基隆市仁愛區"},
        {"name": "基隆港景旅宿", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "基隆市中正區"},
        {"name": "和平島民宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "基隆市中正區和平島"},
        {"name": "碧砂漁港旁旅館", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "基隆市中正區碧砂港"},
        {"name": "基隆信義商旅", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "基隆市信義區"},
        {"name": "基隆安樂民宿", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "基隆市安樂區"},
        {"name": "八斗子海景民宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "基隆市中正區八斗子"},
        {"name": "基隆七堵商旅", "price": "NT$ 1,300/晚起", "rating": "7.7", "address": "基隆市七堵區"},
        {"name": "暖暖商旅", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "基隆市暖暖區"},
        {"name": "基隆新豐大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "基隆市仁愛區"},
        {"name": "基隆藍天旅宿", "price": "NT$ 1,700/晚起", "rating": "8.1", "address": "基隆市仁愛區"},
        {"name": "基隆文化旅館", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "基隆市中正區"},
        {"name": "基隆港都大飯店", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "基隆市中山區"},
        {"name": "基隆市中商旅", "price": "NT$ 1,800/晚起", "rating": "8.0", "address": "基隆市中山區"},
        {"name": "田寮河旁民宿", "price": "NT$ 1,900/晚起", "rating": "8.2", "address": "基隆市仁愛區田寮河"},
        {"name": "基隆外木山海景旅宿", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "基隆市安樂區外木山"},
        {"name": "基隆國際大飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "基隆市仁愛區忠一路"},
        {"name": "正濱漁港景觀民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "基隆市中正區正濱路"},
        {"name": "基隆老爺行旅", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "基隆市中山區中山一路"},
        {"name": "基隆濱海旅宿", "price": "NT$ 2,300/晚起", "rating": "8.2", "address": "基隆市中正區"},
        {"name": "基隆科技商旅", "price": "NT$ 2,100/晚起", "rating": "8.1", "address": "基隆市中山區"},
        {"name": "基隆夜市旁旅館", "price": "NT$ 1,400/晚起", "rating": "7.7", "address": "基隆市仁愛區愛三路"},
        {"name": "基隆晶英酒店", "price": "NT$ 5,500/晚起", "rating": "9.1", "address": "基隆市中正區北寧路"},
        {"name": "基隆精緻旅宿", "price": "NT$ 1,800/晚起", "rating": "8.0", "address": "基隆市"},
        {"name": "基隆灣景觀飯店", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "基隆市中山區"},
        {"name": "仙洞岩旁民宿", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "基隆市中山區仙洞里"},
        {"name": "瑞芳山海景旅宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "基隆市中正區"},
        {"name": "基隆旅遊服務中心旅館", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "基隆市仁愛區"},
    ],
    "新竹": [
        {"name": "新竹老爺行旅", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "新竹市東區"},
        {"name": "新竹豐邑大飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "新竹市北區"},
        {"name": "新竹國賓大飯店", "price": "NT$ 4,200/晚起", "rating": "8.9", "address": "新竹市中山路"},
        {"name": "新竹東方商旅", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "新竹市東區"},
        {"name": "新竹竹北商旅", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "新竹縣竹北市"},
        {"name": "新竹科學城商旅", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "新竹市東區"},
        {"name": "新竹風城大飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "新竹市中區"},
        {"name": "新竹城隍廟旁旅館", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "新竹市北區城隍廟旁"},
        {"name": "新竹承億文旅", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "新竹市"},
        {"name": "內灣山城民宿", "price": "NT$ 2,000/晚起", "rating": "8.4", "address": "新竹縣橫山鄉內灣村"},
        {"name": "北埔客家風情民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "新竹縣北埔鄉"},
        {"name": "新竹六福居商旅", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "新竹市"},
        {"name": "新竹喜來登大飯店", "price": "NT$ 5,000/晚起", "rating": "9.0", "address": "新竹市"},
        {"name": "竹北晶品城大飯店", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "新竹縣竹北市"},
        {"name": "新竹意境商旅", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "新竹市東區"},
        {"name": "尖石鄉山地民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "新竹縣尖石鄉"},
        {"name": "五峰清泉溫泉民宿", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "新竹縣五峰鄉清泉村"},
        {"name": "新竹亞緻飯店", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "新竹市"},
        {"name": "新竹商旅", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "新竹市"},
        {"name": "竹東鎮民宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "新竹縣竹東鎮"},
        {"name": "新豐海邊民宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "新竹縣新豐鄉"},
        {"name": "關西老街旅宿", "price": "NT$ 1,900/晚起", "rating": "8.3", "address": "新竹縣關西鎮"},
        {"name": "新竹千禧大飯店", "price": "NT$ 3,200/晚起", "rating": "8.5", "address": "新竹市"},
        {"name": "新竹寒舍艾美酒店", "price": "NT$ 6,500/晚起", "rating": "9.2", "address": "新竹市"},
        {"name": "竹北婚宴主題旅館", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "新竹縣竹北市"},
        {"name": "橫山丘民宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "新竹縣橫山鄉"},
        {"name": "新竹晶英酒店", "price": "NT$ 5,800/晚起", "rating": "9.1", "address": "新竹市"},
        {"name": "新竹南寮漁港旅宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "新竹市香山區南寮"},
        {"name": "湖口商旅", "price": "NT$ 1,300/晚起", "rating": "7.7", "address": "新竹縣湖口鄉"},
        {"name": "芎林鄉村民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "新竹縣芎林鄉"},
    ],
    "苗栗": [
        {"name": "苗栗南庄大飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "苗栗縣南庄鄉"},
        {"name": "泰安觀止溫泉會館", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "苗栗縣泰安鄉"},
        {"name": "泰安溫泉山莊", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "苗栗縣泰安鄉錦水村"},
        {"name": "苗栗三義木雕民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "苗栗縣三義鄉"},
        {"name": "向天湖民宿", "price": "NT$ 2,500/晚起", "rating": "8.6", "address": "苗栗縣南庄鄉向天湖"},
        {"name": "苗栗市商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "苗栗縣苗栗市"},
        {"name": "頭份商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "苗栗縣頭份市"},
        {"name": "竹南商旅", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "苗栗縣竹南鎮"},
        {"name": "通霄海景民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "苗栗縣通霄鎮"},
        {"name": "苑裡海邊旅宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "苗栗縣苑裡鎮"},
        {"name": "苗栗老旅行旅", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "苗栗縣苗栗市"},
        {"name": "後龍海岸民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "苗栗縣後龍鎮"},
        {"name": "大湖草莓民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "苗栗縣大湖鄉"},
        {"name": "獅潭風情民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "苗栗縣獅潭鄉"},
        {"name": "苗栗縣縣治旅館", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "苗栗縣苗栗市"},
        {"name": "卓蘭溪谷民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "苗栗縣卓蘭鎮"},
        {"name": "三灣老街旅宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "苗栗縣三灣鄉"},
        {"name": "苗栗豐邑飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "苗栗縣頭份市"},
        {"name": "峨眉湖畔民宿", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "苗栗縣峨眉鄉"},
        {"name": "造橋農莊民宿", "price": "NT$ 1,900/晚起", "rating": "8.2", "address": "苗栗縣造橋鄉"},
        {"name": "苗栗春天民宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "苗栗縣"},
        {"name": "雪霸國家公園山莊", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "苗栗縣泰安鄉"},
        {"name": "西湖渡假村", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "苗栗縣三義鄉"},
        {"name": "苗栗新城商旅", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "苗栗縣苗栗市"},
        {"name": "銅鑼工業區商旅", "price": "NT$ 1,300/晚起", "rating": "7.7", "address": "苗栗縣銅鑼鄉"},
        {"name": "公館老街旅宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "苗栗縣公館鄉"},
        {"name": "苗栗好客民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "苗栗縣"},
        {"name": "泰安清泉溫泉民宿", "price": "NT$ 3,200/晚起", "rating": "8.7", "address": "苗栗縣泰安鄉"},
        {"name": "苗栗縣農場民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "苗栗縣"},
        {"name": "苗栗文創旅宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "苗栗縣苗栗市"},
    ],
    "彰化": [
        {"name": "彰化廣豐大飯店", "price": "NT$ 2,500/晚起", "rating": "8.3", "address": "彰化縣彰化市"},
        {"name": "彰化商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "彰化縣彰化市"},
        {"name": "鹿港古鎮民宿", "price": "NT$ 2,200/晚起", "rating": "8.5", "address": "彰化縣鹿港鎮"},
        {"name": "彰化萬宇大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "彰化縣彰化市"},
        {"name": "員林商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "彰化縣員林市"},
        {"name": "田中鄉村民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "彰化縣田中鎮"},
        {"name": "溪湖糖廠旁旅館", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "彰化縣溪湖鎮"},
        {"name": "北斗商旅", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "彰化縣北斗鎮"},
        {"name": "彰化福華大飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "彰化縣彰化市"},
        {"name": "二林葡萄民宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "彰化縣二林鎮"},
        {"name": "和美商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "彰化縣和美鎮"},
        {"name": "彰化縣大村農莊民宿", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "彰化縣大村鄉"},
        {"name": "彰化大城濱海民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "彰化縣大城鄉"},
        {"name": "彰化老字號旅館", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "彰化縣彰化市"},
        {"name": "鹿港三日月商旅", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "彰化縣鹿港鎮"},
        {"name": "彰化竹塘民宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "彰化縣竹塘鄉"},
        {"name": "彰化伸港旅宿", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "彰化縣伸港鄉"},
        {"name": "芳苑王功漁港民宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "彰化縣芳苑鄉王功"},
        {"name": "彰化文化旅館", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "彰化縣彰化市"},
        {"name": "線西農村民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "彰化縣線西鄉"},
        {"name": "彰化風城大飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "彰化縣彰化市"},
        {"name": "鹿港老爺行旅", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "彰化縣鹿港鎮"},
        {"name": "彰化晶英酒店", "price": "NT$ 5,000/晚起", "rating": "9.0", "address": "彰化縣彰化市"},
        {"name": "彰化芬園山莊", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "彰化縣芬園鄉"},
        {"name": "秀水鄉村民宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "彰化縣秀水鄉"},
        {"name": "彰化縣花壇旅宿", "price": "NT$ 1,800/晚起", "rating": "8.0", "address": "彰化縣花壇鄉"},
        {"name": "彰化卦山商旅", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "彰化縣彰化市八卦山"},
        {"name": "彰化城市旅店", "price": "NT$ 1,900/晚起", "rating": "8.1", "address": "彰化縣彰化市"},
        {"name": "彰化縣精緻旅宿", "price": "NT$ 2,300/晚起", "rating": "8.2", "address": "彰化縣"},
        {"name": "彰化全國大飯店", "price": "NT$ 3,200/晚起", "rating": "8.5", "address": "彰化縣彰化市"},
    ],
    "南投": [
        {"name": "日月潭雲品溫泉酒店", "price": "NT$ 8,500/晚起", "rating": "9.4", "address": "南投縣魚池鄉中山路"},
        {"name": "日月潭涵碧樓", "price": "NT$ 12,000/晚起", "rating": "9.6", "address": "南投縣魚池鄉中興路142號"},
        {"name": "日月潭大淶閣飯店", "price": "NT$ 4,500/晚起", "rating": "8.8", "address": "南投縣魚池鄉中山路"},
        {"name": "清境老英格蘭莊園", "price": "NT$ 5,500/晚起", "rating": "9.0", "address": "南投縣仁愛鄉定遠新村30號"},
        {"name": "清境農場附近民宿", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "南投縣仁愛鄉"},
        {"name": "溪頭神木大飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "南投縣鹿谷鄉溪頭村"},
        {"name": "南投草屯商旅", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "南投縣草屯鎮"},
        {"name": "南投市商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "南投縣南投市"},
        {"name": "埔里酒鄉旅館", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "南投縣埔里鎮"},
        {"name": "集集小鎮民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "南投縣集集鎮"},
        {"name": "霧社高山民宿", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "南投縣仁愛鄉霧社"},
        {"name": "竹山天梯旁旅館", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "南投縣竹山鎮"},
        {"name": "惠蓀林場山莊", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "南投縣仁愛鄉"},
        {"name": "奧萬大楓葉山莊", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "南投縣仁愛鄉萬豐村"},
        {"name": "日月潭全國飯店", "price": "NT$ 5,200/晚起", "rating": "8.9", "address": "南投縣魚池鄉中山路"},
        {"name": "名間鄉茶香民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "南投縣名間鄉"},
        {"name": "信義鄉梅子民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "南投縣信義鄉"},
        {"name": "魚池鄉紅茶民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "南投縣魚池鄉"},
        {"name": "廬山溫泉民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "南投縣仁愛鄉廬山"},
        {"name": "水里商旅", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "南投縣水里鄉"},
        {"name": "玉山國家公園山莊", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "南投縣信義鄉"},
        {"name": "日月潭晶英酒店", "price": "NT$ 9,000/晚起", "rating": "9.5", "address": "南投縣魚池鄉中山路"},
        {"name": "清境青青草原旅館", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "南投縣仁愛鄉"},
        {"name": "南投縣鹿谷茶鄉民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "南投縣鹿谷鄉"},
        {"name": "國姓鄉咖啡民宿", "price": "NT$ 2,300/晚起", "rating": "8.3", "address": "南投縣國姓鄉"},
        {"name": "南投縣竹山旅宿", "price": "NT$ 1,900/晚起", "rating": "8.1", "address": "南投縣竹山鎮"},
        {"name": "南投大里農莊民宿", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "南投縣草屯鎮"},
        {"name": "日月潭觀景山莊", "price": "NT$ 6,000/晚起", "rating": "9.1", "address": "南投縣魚池鄉水社村"},
        {"name": "中寮鄉農村民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "南投縣中寮鄉"},
        {"name": "南投縣精緻渡假民宿", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "南投縣"},
    ],
    "雲林": [
        {"name": "雲林古坑大飯店", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "雲林縣古坑鄉"},
        {"name": "斗六商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "雲林縣斗六市"},
        {"name": "虎尾商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "雲林縣虎尾鎮"},
        {"name": "西螺老街民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "雲林縣西螺鎮"},
        {"name": "北港老街旅宿", "price": "NT$ 1,700/晚起", "rating": "8.1", "address": "雲林縣北港鎮"},
        {"name": "古坑咖啡民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "雲林縣古坑鄉"},
        {"name": "劍湖山世界渡假旅館", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "雲林縣古坑鄉中正路1號"},
        {"name": "草嶺石壁山莊", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "雲林縣古坑鄉草嶺村"},
        {"name": "雲林縣崙背旅宿", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "雲林縣崙背鄉"},
        {"name": "斗南商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "雲林縣斗南鎮"},
        {"name": "雲林縣土庫旅館", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "雲林縣土庫鎮"},
        {"name": "莿桐鄉農莊民宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "雲林縣莿桐鄉"},
        {"name": "雲林縣林內農舍民宿", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "雲林縣林內鄉"},
        {"name": "二崙農村民宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "雲林縣二崙鄉"},
        {"name": "東勢鄉田園民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "雲林縣東勢鄉"},
        {"name": "口湖濕地旁民宿", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "雲林縣口湖鄉"},
        {"name": "雲林大飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "雲林縣斗六市"},
        {"name": "四湖海岸民宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "雲林縣四湖鄉"},
        {"name": "水林鄉農業民宿", "price": "NT$ 1,500/晚起", "rating": "7.7", "address": "雲林縣水林鄉"},
        {"name": "台西海岸旅宿", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "雲林縣台西鄉"},
        {"name": "雲林承億文旅", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "雲林縣斗六市"},
        {"name": "古坑華山咖啡民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "雲林縣古坑鄉華山村"},
        {"name": "雲林旅遊大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "雲林縣斗六市"},
        {"name": "西螺河畔民宿", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "雲林縣西螺鎮"},
        {"name": "大埤鄉農莊旅宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "雲林縣大埤鄉"},
        {"name": "雲林老爺行旅", "price": "NT$ 4,000/晚起", "rating": "8.8", "address": "雲林縣斗六市"},
        {"name": "雲林縣麥寮旅館", "price": "NT$ 1,400/晚起", "rating": "7.7", "address": "雲林縣麥寮鄉"},
        {"name": "褒忠鄉田園旅館", "price": "NT$ 1,400/晚起", "rating": "7.7", "address": "雲林縣褒忠鄉"},
        {"name": "元長鄉農村民宿", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "雲林縣元長鄉"},
        {"name": "雲林縣精緻旅宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "雲林縣"},
    ],
    "嘉義": [
        {"name": "嘉義晶英酒店", "price": "NT$ 5,500/晚起", "rating": "9.2", "address": "嘉義市東區"},
        {"name": "嘉義商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "嘉義市東區"},
        {"name": "嘉義福華大飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "嘉義市中山路"},
        {"name": "阿里山山地農莊民宿", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "嘉義縣阿里山鄉"},
        {"name": "奮起湖民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "嘉義縣竹崎鄉中和村"},
        {"name": "嘉義文化路旁旅館", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "嘉義市東區文化路"},
        {"name": "嘉義老爺行旅", "price": "NT$ 4,200/晚起", "rating": "8.9", "address": "嘉義市西區"},
        {"name": "阿里山賓館", "price": "NT$ 6,000/晚起", "rating": "9.1", "address": "嘉義縣阿里山鄉"},
        {"name": "嘉義全國大飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "嘉義市東區"},
        {"name": "故宮南院附近大飯店", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "嘉義縣太保市"},
        {"name": "東石漁港旁民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "嘉義縣東石鄉"},
        {"name": "梅山梅子山莊", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "嘉義縣梅山鄉"},
        {"name": "達娜伊谷部落民宿", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "嘉義縣阿里山鄉山美村"},
        {"name": "嘉義縣布袋旅宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "嘉義縣布袋鎮"},
        {"name": "朴子市旅館", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "嘉義縣朴子市"},
        {"name": "大林鎮商旅", "price": "NT$ 1,400/晚起", "rating": "7.7", "address": "嘉義縣大林鎮"},
        {"name": "嘉義縣中埔鄉農莊民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "嘉義縣中埔鄉"},
        {"name": "嘉義承億文旅", "price": "NT$ 3,200/晚起", "rating": "8.7", "address": "嘉義市"},
        {"name": "番路鄉山莊民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "嘉義縣番路鄉"},
        {"name": "竹崎鄉農村民宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "嘉義縣竹崎鄉"},
        {"name": "嘉義縣新港旅宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "嘉義縣新港鄉"},
        {"name": "嘉義市文化旅館", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "嘉義市"},
        {"name": "阿里山二延平步道旁民宿", "price": "NT$ 3,500/晚起", "rating": "8.8", "address": "嘉義縣阿里山鄉"},
        {"name": "嘉義萬代福大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "嘉義市"},
        {"name": "嘉義縣精緻旅宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "嘉義縣"},
        {"name": "阿里山高山旅館", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "嘉義縣阿里山鄉"},
        {"name": "嘉義老旅行旅", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "嘉義市"},
        {"name": "嘉義縣水上旅宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "嘉義縣水上鄉"},
        {"name": "嘉義縣六腳旅館", "price": "NT$ 1,400/晚起", "rating": "7.7", "address": "嘉義縣六腳鄉"},
        {"name": "嘉義縣義竹鄉田園民宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "嘉義縣義竹鄉"},
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
        {"name": "台南嘉南旅館", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "台南市南區"},
        {"name": "台南安平旅宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "台南市安平區"},
        {"name": "台南關子嶺溫泉飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "台南市白河區關子嶺"},
        {"name": "台南時尚旅館", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台南市東區"},
        {"name": "台南七股鹽山旁民宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "台南市七股區"},
        {"name": "台南文創旅宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "台南市中西區神農街"},
        {"name": "台南漁光島民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "台南市安南區"},
        {"name": "台南麻豆文旦民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "台南市麻豆區"},
        {"name": "台南全國大飯店", "price": "NT$ 3,800/晚起", "rating": "8.6", "address": "台南市中西區"},
        {"name": "台南成大附近旅館", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "台南市東區大學路"},
        {"name": "台南鹽水區旅宿", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "台南市鹽水區"},
        {"name": "台南後壁菁寮民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台南市後壁區菁寮"},
        {"name": "台南赤崁旅宿", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "台南市中西區"},
        {"name": "台南希爾頓酒店", "price": "NT$ 6,500/晚起", "rating": "9.2", "address": "台南市中西區"},
        {"name": "台南仁德商旅", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "台南市仁德區"},
        {"name": "台南老街行旅", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "台南市中西區"},
        {"name": "台南官田區民宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "台南市官田區"},
        {"name": "台南縣精緻旅宿", "price": "NT$ 2,200/晚起", "rating": "8.2", "address": "台南市"},
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
        {"name": "高雄晶英酒店", "price": "NT$ 6,000/晚起", "rating": "9.2", "address": "高雄市苓雅區"},
        {"name": "高雄凱撒大飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "高雄市苓雅區"},
        {"name": "美濃客家民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "高雄市美濃區"},
        {"name": "高雄茂林山地旅館", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "高雄市茂林區"},
        {"name": "高雄六龜溫泉飯店", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "高雄市六龜區"},
        {"name": "高雄甲仙民宿", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "高雄市甲仙區"},
        {"name": "高雄那瑪夏山地旅館", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "高雄市那瑪夏區"},
        {"name": "高雄鳳山商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "高雄市鳳山區"},
        {"name": "高雄旗山老街旅宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "高雄市旗山區"},
        {"name": "高雄林園海岸民宿", "price": "NT$ 1,700/晚起", "rating": "8.1", "address": "高雄市林園區"},
        {"name": "高雄澄清湖旁飯店", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "高雄市鳥松區"},
        {"name": "高雄老爺行旅", "price": "NT$ 5,500/晚起", "rating": "9.1", "address": "高雄市前金區"},
        {"name": "高雄文化中心旅宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "高雄市苓雅區"},
        {"name": "高雄仁武商旅", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "高雄市仁武區"},
        {"name": "高雄橋頭旅宿", "price": "NT$ 1,400/晚起", "rating": "7.7", "address": "高雄市橋頭區"},
        {"name": "高雄岡山商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "高雄市岡山區"},
        {"name": "高雄大樹旅宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "高雄市大樹區"},
        {"name": "高雄燕巢商旅", "price": "NT$ 1,400/晚起", "rating": "7.8", "address": "高雄市燕巢區"},
    ],
    "屏東": [
        {"name": "墾丁悠活渡假村", "price": "NT$ 5,500/晚起", "rating": "9.0", "address": "屏東縣恆春鎮墾丁路"},
        {"name": "墾丁凱撒大飯店", "price": "NT$ 6,000/晚起", "rating": "9.1", "address": "屏東縣恆春鎮墾丁路6號"},
        {"name": "小琉球民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "屏東縣琉球鄉"},
        {"name": "東港漁港旁旅宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "屏東縣東港鎮"},
        {"name": "屏東市商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "屏東縣屏東市"},
        {"name": "恆春古城旁民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "屏東縣恆春鎮"},
        {"name": "墾丁夏都沙灘酒店", "price": "NT$ 7,500/晚起", "rating": "9.3", "address": "屏東縣恆春鎮墾丁路451號"},
        {"name": "霧台山地旅館", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "屏東縣霧台鄉"},
        {"name": "三地門排灣民宿", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "屏東縣三地門鄉"},
        {"name": "四重溪溫泉飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "屏東縣車城鄉溫泉村"},
        {"name": "恆春高哥大飯店", "price": "NT$ 4,200/晚起", "rating": "8.8", "address": "屏東縣恆春鎮"},
        {"name": "潮州鎮商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "屏東縣潮州鎮"},
        {"name": "南州商旅", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "屏東縣南州鄉"},
        {"name": "林邊鄉農村民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "屏東縣林邊鄉"},
        {"name": "佳冬旅宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "屏東縣佳冬鄉"},
        {"name": "枋寮海邊旅館", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "屏東縣枋寮鄉"},
        {"name": "春日鄉原民民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "屏東縣春日鄉"},
        {"name": "獅子鄉山地民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "屏東縣獅子鄉"},
        {"name": "牡丹鄉部落民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "屏東縣牡丹鄉"},
        {"name": "車城鄉海邊旅館", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "屏東縣車城鄉"},
        {"name": "滿州鄉旅宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "屏東縣滿州鄉"},
        {"name": "墾丁福容大飯店", "price": "NT$ 5,000/晚起", "rating": "8.9", "address": "屏東縣恆春鎮墾丁路"},
        {"name": "屏東老爺行旅", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "屏東縣屏東市"},
        {"name": "屏東縣竹田鄉農莊民宿", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "屏東縣竹田鄉"},
        {"name": "里港商旅", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "屏東縣里港鄉"},
        {"name": "九如鄉農村旅宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "屏東縣九如鄉"},
        {"name": "屏東縣精緻旅宿", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "屏東縣"},
        {"name": "墾丁大飯店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "屏東縣恆春鎮"},
        {"name": "屏東縣萬丹旅宿", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "屏東縣萬丹鄉"},
        {"name": "屏東縣新園旅館", "price": "NT$ 1,400/晚起", "rating": "7.7", "address": "屏東縣新園鄉"},
    ],
    "宜蘭": [
        {"name": "礁溪老爺酒店", "price": "NT$ 6,500/晚起", "rating": "9.3", "address": "宜蘭縣礁溪鄉五峰路"},
        {"name": "礁溪長榮鳳凰酒店", "price": "NT$ 5,800/晚起", "rating": "9.1", "address": "宜蘭縣礁溪鄉中山路二段"},
        {"name": "宜蘭傳藝中心附近民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "宜蘭縣五結鄉"},
        {"name": "羅東商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "宜蘭縣羅東鎮"},
        {"name": "宜蘭市商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "宜蘭縣宜蘭市"},
        {"name": "蘇澳冷泉旅館", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "宜蘭縣蘇澳鎮冷泉路"},
        {"name": "礁溪溫泉大飯店", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "宜蘭縣礁溪鄉"},
        {"name": "宜蘭縣頭城老街旅宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "宜蘭縣頭城鎮"},
        {"name": "棲蘭山莊", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "宜蘭縣大同鄉"},
        {"name": "太平山附近民宿", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "宜蘭縣大同鄉"},
        {"name": "宜蘭縣冬山鄉旅宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "宜蘭縣冬山鄉"},
        {"name": "宜蘭縣三星鄉農莊民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "宜蘭縣三星鄉"},
        {"name": "壯圍沙丘旅遊服務園區附近旅宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "宜蘭縣壯圍鄉"},
        {"name": "南方澳漁港民宿", "price": "NT$ 1,900/晚起", "rating": "8.2", "address": "宜蘭縣蘇澳鎮南方澳"},
        {"name": "礁溪林美石磐旁民宿", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "宜蘭縣礁溪鄉"},
        {"name": "宜蘭縣大同鄉高山民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "宜蘭縣大同鄉"},
        {"name": "五結鄉濕地旁旅宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "宜蘭縣五結鄉"},
        {"name": "宜蘭縣員山鄉農莊旅館", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "宜蘭縣員山鄉"},
        {"name": "宜蘭科技園區商旅", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "宜蘭縣宜蘭市"},
        {"name": "礁溪泰美溫泉公園旁旅館", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "宜蘭縣礁溪鄉"},
        {"name": "宜蘭羅東林業文化園區旁旅宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "宜蘭縣羅東鎮"},
        {"name": "宜蘭老爺行旅", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "宜蘭縣宜蘭市"},
        {"name": "礁溪心泉溫泉民宿", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "宜蘭縣礁溪鄉"},
        {"name": "宜蘭縣澳花部落民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "宜蘭縣南澳鄉"},
        {"name": "宜蘭縣南澳旅宿", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "宜蘭縣南澳鄉"},
        {"name": "宜蘭縣蘇澳商旅", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "宜蘭縣蘇澳鎮"},
        {"name": "宜蘭承億文旅", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "宜蘭縣宜蘭市"},
        {"name": "頭城濱海民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "宜蘭縣頭城鎮"},
        {"name": "礁溪品文旅", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "宜蘭縣礁溪鄉"},
        {"name": "宜蘭縣精緻旅宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "宜蘭縣"},
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
        {"name": "花蓮老爺行旅", "price": "NT$ 5,500/晚起", "rating": "9.0", "address": "花蓮市"},
        {"name": "太魯閣晶英酒店", "price": "NT$ 9,000/晚起", "rating": "9.5", "address": "花蓮縣秀林鄉天祥路"},
        {"name": "花蓮縣吉安旅宿", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "花蓮縣吉安鄉"},
        {"name": "花蓮縣新城旅館", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "花蓮縣新城鄉"},
        {"name": "花蓮七星潭旁民宿", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "花蓮縣新城鄉七星街"},
        {"name": "花蓮縣壽豐鄉農莊民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "花蓮縣壽豐鄉"},
        {"name": "花蓮縣光復鄉原民民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "花蓮縣光復鄉"},
        {"name": "花蓮縣豐濱鄉旅宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "花蓮縣豐濱鄉"},
        {"name": "花蓮縣玉里鎮商旅", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "花蓮縣玉里鎮"},
        {"name": "花蓮縣瑞穗鄉溫泉民宿", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "花蓮縣瑞穗鄉"},
        {"name": "花蓮縣富里鄉民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "花蓮縣富里鄉"},
        {"name": "花蓮縣鳳林鎮旅宿", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "花蓮縣鳳林鎮"},
        {"name": "花蓮縣秀林鄉山地民宿", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "花蓮縣秀林鄉"},
        {"name": "花蓮縣萬榮鄉旅宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "花蓮縣萬榮鄉"},
        {"name": "花蓮縣卓溪鄉山地旅館", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "花蓮縣卓溪鄉"},
        {"name": "花蓮縣精緻旅宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "花蓮縣"},
        {"name": "花蓮承億文旅", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "花蓮市"},
        {"name": "花蓮縣文創民宿", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "花蓮市中華路"},
    ],
    "台東": [
        {"name": "知本老爺酒店", "price": "NT$ 5,500/晚起", "rating": "9.1", "address": "台東縣卑南鄉溫泉村龍泉路"},
        {"name": "台東娜路彎大酒店", "price": "NT$ 4,200/晚起", "rating": "8.9", "address": "台東市中興路2段"},
        {"name": "台東知本中信溫泉酒店", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "台東縣卑南鄉溫泉村"},
        {"name": "台東池上逸饗園渡假飯店", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "台東縣池上鄉"},
        {"name": "台東市商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台東縣台東市"},
        {"name": "鹿野鄉民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "台東縣鹿野鄉"},
        {"name": "綠島民宿", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "台東縣綠島鄉"},
        {"name": "蘭嶼民宿", "price": "NT$ 2,500/晚起", "rating": "8.6", "address": "台東縣蘭嶼鄉"},
        {"name": "台東關山旅宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台東縣關山鎮"},
        {"name": "三仙台旁民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "台東縣成功鎮"},
        {"name": "台東縣成功鎮商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "台東縣成功鎮"},
        {"name": "池上稻田旁民宿", "price": "NT$ 3,500/晚起", "rating": "8.8", "address": "台東縣池上鄉"},
        {"name": "台東知本親水度假村", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "台東縣卑南鄉溫泉村"},
        {"name": "台東縣金峰鄉山地民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "台東縣金峰鄉"},
        {"name": "台東縣太麻里旅宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台東縣太麻里鄉"},
        {"name": "台東縣東河鄉旅館", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "台東縣東河鄉"},
        {"name": "台東縣延平鄉部落民宿", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "台東縣延平鄉"},
        {"name": "台東縣海端鄉高山民宿", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "台東縣海端鄉"},
        {"name": "台東縣長濱鄉濱海民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台東縣長濱鄉"},
        {"name": "台東縣達仁鄉部落旅宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "台東縣達仁鄉"},
        {"name": "鹿野高台民宿", "price": "NT$ 3,000/晚起", "rating": "8.7", "address": "台東縣鹿野鄉永安村高台路"},
        {"name": "台東縣卑南鄉旅館", "price": "NT$ 1,700/晚起", "rating": "8.0", "address": "台東縣卑南鄉"},
        {"name": "台東縣大武鄉旅宿", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "台東縣大武鄉"},
        {"name": "台東全國大飯店", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "台東縣台東市"},
        {"name": "台東承億文旅", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "台東縣台東市"},
        {"name": "台東縣精緻旅宿", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "台東縣"},
        {"name": "台東晶英酒店", "price": "NT$ 6,000/晚起", "rating": "9.2", "address": "台東縣台東市"},
        {"name": "台東老爺行旅", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "台東縣台東市"},
        {"name": "台東縣文化旅宿", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "台東縣台東市"},
        {"name": "台東縣都蘭旅宿", "price": "NT$ 2,800/晚起", "rating": "8.5", "address": "台東縣東河鄉都蘭村"},
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
        Target city (台北、台中、台南、高雄、花蓮).
    check_in : str
        Check-in date in ``YYYY-MM-DD`` format.
    check_out : str
        Check-out date in ``YYYY-MM-DD`` format.
    budget : str
        One of ``經濟``、``中等``、``豪華``.
    headless : bool
        Whether to run Chromium headlessly (default ``True``).
    max_items : int
        Maximum number of hotels to return (default ``5``).
    """

    def __init__(
        self,
        city: str,
        check_in: str = "",
        check_out: str = "",
        budget: str = "中等",
        headless: bool = True,
        max_items: int = 30,
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
