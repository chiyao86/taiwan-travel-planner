"""CityScraper – scrapes attraction data from Taiwan city tourism portals.

Supported cities and their official tourism URLs:
    台北  → https://www.travel.taipei/zh-tw/attraction/all-regions
    新北  → https://newtaipei.travel/zh-tw/tour/list
    桃園  → https://travel.tycg.gov.tw/zh-tw/travel/tourlist
    台中  → https://travel.taichung.gov.tw/zh-tw/Attractions/List
    基隆  → https://travel.klcg.gov.tw/
    新竹  → https://tourism.hccg.gov.tw/
    苗栗  → https://miaolitravel.net/
    彰化  → https://tourism.chcg.gov.tw/
    南投  → https://travel.nantou.gov.tw/attractions/
    雲林  → https://tour.yunlin.gov.tw/
    嘉義  → https://travel.chiayi.gov.tw/
    台南  → https://www.twtainan.net/zh-tw/attractions/
    屏東  → https://pingtung.easytravel.com.tw/scenic/
    宜蘭  → https://www.taiwan.net.tw/
    花蓮  → https://tour-hualien.hl.gov.tw/
    台東  → https://tour.taitung.gov.tw/zh-tw/attraction
    高雄  → https://khh.travel/zh-tw/attractions/list/
"""
import asyncio
import random
from typing import Any

from playwright.async_api import async_playwright, Page

try:
    from playwright_stealth import stealth_async
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False

from .base_scraper import BaseScraper, Attraction


# ---------------------------------------------------------------------------
# Per-city configuration: URL + CSS selectors (best-effort selectors that
# target stable landmark elements on each site; graceful fallback on failure)
# ---------------------------------------------------------------------------
CITY_CONFIG: dict[str, dict] = {
    "台北": {
        "url": "https://www.travel.taipei/zh-tw/attraction/all-regions?page=1",
        "card_selector": "li.list-card-item",
        "name_selector": "h3.card-title",
        "desc_selector": "p.card-text",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "新北": {
        "url": "https://newtaipei.travel/zh-tw/tour/list?sortby=hits",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p.desc",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "桃園": {
        "url": "https://travel.tycg.gov.tw/zh-tw/travel/tourlist",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p.desc",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "台中": {
        "url": "https://travel.taichung.gov.tw/zh-tw/Attractions/List",
        "card_selector": "div.list-wrap ul li",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "基隆": {
        "url": "https://travel.klcg.gov.tw/SiteMap.aspx?n=8184",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "新竹": {
        "url": "https://tourism.hccg.gov.tw/chtravel/app/travel/list?id=37",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "苗栗": {
        "url": "https://miaolitravel.net/article.aspx?sno=03004313",
        "card_selector": "div.item",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "彰化": {
        "url": "https://tourism.chcg.gov.tw/Attractions.aspx",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "南投": {
        "url": "https://travel.nantou.gov.tw/attractions/",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "雲林": {
        "url": "https://tour.yunlin.gov.tw/mainssl/modules/MySpace/BlogList.php?sn=yunlin&cn=ZC10350618",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "嘉義": {
        "url": "https://travel.chiayi.gov.tw/TravelInformation/C000005/1",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "台南": {
        "url": "https://www.twtainan.net/zh-tw/attractions/",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p.desc",
        "addr_selector": "p.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "屏東": {
        "url": "https://pingtung.easytravel.com.tw/scenic/",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "宜蘭": {
        # URL: keyString=宜蘭^^^^ (the encoded query parameter filters for Yilan attractions)
        "url": "https://www.taiwan.net.tw/m1.aspx?sNo=0000064&keyString=%e5%ae%9c%e8%98%ad%5e%5e%5e%5e0",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "花蓮": {
        "url": "https://tour-hualien.hl.gov.tw/TourList.aspx?n=109&sms=12302",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "台東": {
        "url": "https://tour.taitung.gov.tw/zh-tw/attraction",
        "card_selector": "div.item-card",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "高雄": {
        "url": "https://khh.travel/zh-tw/attractions/list/",
        "card_selector": "li.attraction-item",
        "name_selector": "h3",
        "desc_selector": "p.desc",
        "addr_selector": "p.address",
        "img_selector": "img",
        "link_selector": "a",
    },
}

# Fallback attractions when live scraping is unavailable
FALLBACK_ATTRACTIONS: dict[str, list[dict]] = {
    "台北": [
        {"name": "台北101", "description": "世界知名地標，觀景台可俯瞰全台北市。", "address": "台北市信義區信義路五段7號"},
        {"name": "故宮博物院", "description": "收藏中華文物精品，藏品超過70萬件。", "address": "台北市士林區至善路二段221號"},
        {"name": "淡水老街", "description": "百年歷史老街，充滿文化與美食。", "address": "新北市淡水區中正路"},
        {"name": "九份老街", "description": "山城老街，電影《悲情城市》取景地。", "address": "新北市瑞芳區九份"},
        {"name": "士林夜市", "description": "台北最大夜市，美食種類豐富多元。", "address": "台北市士林區基河路"},
        {"name": "西門町", "description": "年輕人聚集的流行文化聖地。", "address": "台北市萬華區西門町"},
        {"name": "陽明山國家公園", "description": "火山地形景觀，春季賞花勝地。", "address": "台北市士林區陽明山"},
        {"name": "大安森林公園", "description": "台北市中心最大的都市公園，四季皆美。", "address": "台北市大安區新生南路二段1號"},
        {"name": "中正紀念堂", "description": "宏偉國家級紀念建築，廣場定時有衛兵交接典禮。", "address": "台北市中正區中山南路21號"},
        {"name": "饒河街夜市", "description": "台北知名夜市之一，胡椒餅為必吃名物。", "address": "台北市松山區饒河街"},
        {"name": "龍山寺", "description": "台灣香火最鼎盛的廟宇之一，清代古廟。", "address": "台北市萬華區廣州街211號"},
        {"name": "台北動物園", "description": "亞洲最大的市立動物園，貓熊館最受歡迎。", "address": "台北市文山區新光路二段30號"},
    ],
    "新北": [
        {"name": "淡水老街", "description": "百年歷史老街，充滿文化與美食，夕陽美景著名。", "address": "新北市淡水區中正路"},
        {"name": "九份老街", "description": "山城老街，電影《悲情城市》取景地，夜晚燈籠如夢如幻。", "address": "新北市瑞芳區九份"},
        {"name": "平溪天燈", "description": "平溪放天燈是台灣最具代表性的傳統民俗活動之一。", "address": "新北市平溪區"},
        {"name": "烏來溫泉", "description": "鄰近台北的天然溫泉區，原住民泰雅族文化聚落。", "address": "新北市烏來區"},
        {"name": "野柳地質公園", "description": "奇岩怪石，女王頭為最著名的地質奇景。", "address": "新北市萬里區野柳里167-1號"},
        {"name": "三峽老街", "description": "保存完好的巴洛克式建築老街，祖師廟雕刻精美。", "address": "新北市三峽區民權街"},
        {"name": "鶯歌陶瓷老街", "description": "台灣陶瓷重鎮，陶瓷博物館與陶藝工坊林立。", "address": "新北市鶯歌區文化路"},
        {"name": "新店碧潭", "description": "山光水色，吊橋與划船為主要遊憩活動。", "address": "新北市新店區碧潭路"},
        {"name": "板橋435藝文特區", "description": "舊農業試驗所改造的文創藝術園區，常設藝文活動。", "address": "新北市板橋區館前東路2號"},
        {"name": "深坑老街", "description": "以豆腐料理聞名，老街保有清代閩南式街屋。", "address": "新北市深坑區深坑老街"},
        {"name": "金瓜石黃金博物館", "description": "日治時期金礦遺址，四連棟展示台灣採金歷史。", "address": "新北市瑞芳區金瓜石金光路8號"},
        {"name": "八里左岸", "description": "淡水河畔的自行車道，風景優美、咖啡廳林立。", "address": "新北市八里區"},
    ],
    "桃園": [
        {"name": "大溪老街", "description": "清代商業重鎮，巴洛克式街屋建築保存完整。", "address": "桃園市大溪區中山路"},
        {"name": "慈湖", "description": "蔣中正陵寢所在地，周邊有兩蔣文化園區。", "address": "桃園市大溪區埋石路65號"},
        {"name": "石門水庫", "description": "台灣重要的水利工程，兼具休閒遊憩功能。", "address": "桃園市龍潭區石門"},
        {"name": "拉拉山自然保護區", "description": "台灣最大的神木群聚地，千年紅檜震撼人心。", "address": "桃園市復興區"},
        {"name": "北橫公路", "description": "穿越中央山脈的公路，沿途山景壯麗。", "address": "桃園市復興區北橫公路"},
        {"name": "桃園燈會", "description": "每年元宵節舉辦的大型燈會活動，吸引大批遊客。", "address": "桃園市各區"},
        {"name": "觀音蓮花園區", "description": "夏季荷花盛開，是北台灣著名的賞蓮景點。", "address": "桃園市觀音區草漯里"},
        {"name": "角板山公園", "description": "俯瞰大漢溪的山頂公園，日本天皇行館遺址。", "address": "桃園市復興區角板山"},
        {"name": "龍潭大池", "description": "客家文化重鎮，湖光山色、步道環繞。", "address": "桃園市龍潭區龍潭大池"},
        {"name": "小人國主題樂園", "description": "以台灣及世界知名建築縮小模型為主題的遊樂園。", "address": "桃園市龍潭區中豐路"},
    ],
    "台中": [
        {"name": "彩虹村", "description": "充滿色彩的彩繪村落，藝術氛圍濃厚。", "address": "台中市南屯區春安路56巷"},
        {"name": "逢甲夜市", "description": "台灣規模最大的夜市之一。", "address": "台中市西屯區文華路"},
        {"name": "高美濕地", "description": "夕陽美景著名，風力發電機為特色。", "address": "台中市清水區高美濕地"},
        {"name": "台中國家歌劇院", "description": "世界級建築，文化藝術殿堂。", "address": "台中市西屯區惠來路二段101號"},
        {"name": "東海大學", "description": "路思義教堂為台灣現代建築代表作。", "address": "台中市西屯區台灣大道四段1727號"},
        {"name": "宮原眼科", "description": "老建築改造的文創甜點名店。", "address": "台中市中區中山路20號"},
        {"name": "台中自然科學博物館", "description": "台灣規模最大的科學博物館，太空劇場最受歡迎。", "address": "台中市北區館前路1號"},
        {"name": "台中公園", "description": "市中心老公園，湖心亭倒影是台中經典意象。", "address": "台中市北區公園路37號"},
        {"name": "武陵農場", "description": "台灣最美的高山農場，春季櫻花祭盛況空前。", "address": "台中市和平區武陵路3號"},
        {"name": "新社花海", "description": "每年秋冬舉辦的大型花卉節，花田壯觀。", "address": "台中市新社區中興嶺街一段"},
    ],
    "基隆": [
        {"name": "廟口夜市", "description": "全台最負盛名的夜市之一，天婦羅、鼎邊趖是必吃名物。", "address": "基隆市仁愛區愛三路"},
        {"name": "和平島公園", "description": "奇特的海蝕地形，海水浴場與地質奇景聞名。", "address": "基隆市中正區平一路360號"},
        {"name": "正濱漁港", "description": "彩色漁村倒映水面，是IG熱門打卡景點。", "address": "基隆市中正區中正路"},
        {"name": "基隆嶼", "description": "基隆港外海的孤島，浮潛、登島是熱門活動。", "address": "基隆市中正區基隆嶼"},
        {"name": "八斗子漁港", "description": "新鮮海產聞名，基隆外木山海景步道起點。", "address": "基隆市中正區八斗路"},
        {"name": "二沙灣砲台", "description": "清代海防遺址，俯瞰基隆港全景。", "address": "基隆市中正區中正路三段"},
        {"name": "潮境公園", "description": "廢棄垃圾場改造的生態公園，鋼雕藝術遍布海岸。", "address": "基隆市中正區北寧路369號"},
        {"name": "基隆港", "description": "台灣北部重要國際商港，港景壯觀、郵輪停靠地。", "address": "基隆市仁愛區忠一路1號"},
        {"name": "仙洞巖", "description": "天然海蝕洞改建的岩洞廟宇，鐘乳石奇觀。", "address": "基隆市中山區仙洞巷42號"},
        {"name": "大武崙砲台", "description": "日治時期砲台遺址，俯瞰協和電廠與基隆海灣。", "address": "基隆市安樂區"},
    ],
    "新竹": [
        {"name": "新竹城隍廟", "description": "清代古廟，廟前小吃街是新竹美食的代名詞。", "address": "新竹市北區中山路75號"},
        {"name": "新竹公園", "description": "百年歷史老公園，日治時代孔廟與動物園所在地。", "address": "新竹市東區東大路二段"},
        {"name": "十七公里海岸線", "description": "沿岸風景秀麗，南寮漁港、海天一線是亮點。", "address": "新竹市香山區濱海路"},
        {"name": "玻璃工藝博物館", "description": "新竹玻璃產業發展歷史展示，玻璃藝術品精美絕倫。", "address": "新竹市東區東大路一段2號"},
        {"name": "尖石鄉", "description": "泰雅族原住民文化，秀巒溫泉與司馬庫斯神木群聞名。", "address": "新竹縣尖石鄉"},
        {"name": "新竹動物園", "description": "全台最老動物園之一，保留日治時代建築。", "address": "新竹市東區食品路192號"},
        {"name": "合興車站", "description": "全台唯一可讓遊客親自拉下號誌的車站，愛情故事著名。", "address": "新竹縣峨眉鄉合興村"},
        {"name": "五峰清泉溫泉", "description": "張學良故居所在地，山區泉質清澈的溫泉鄉。", "address": "新竹縣五峰鄉清泉村"},
        {"name": "北埔老街", "description": "客家文化保存完整的山城老街，擂茶是特色體驗。", "address": "新竹縣北埔鄉廟前街"},
        {"name": "內灣老街", "description": "日治時期林業小鎮，野薑花粽是必嚐美食。", "address": "新竹縣橫山鄉內灣村"},
    ],
    "苗栗": [
        {"name": "三義木雕街", "description": "台灣木雕工藝重鎮，木雕博物館與工藝品店林立。", "address": "苗栗縣三義鄉廣盛村"},
        {"name": "勝興車站", "description": "台灣海拔最高的舊火車站，日式建築保存完整。", "address": "苗栗縣三義鄉勝興村"},
        {"name": "苗栗客家文化園區", "description": "展示客家文化與生活的綜合性園區。", "address": "苗栗縣銅鑼鄉銅鑼村192號"},
        {"name": "泰安溫泉", "description": "苗栗山中的天然碳酸氫鈉溫泉，泉質溫潤。", "address": "苗栗縣泰安鄉錦水村"},
        {"name": "明德水庫", "description": "湖光山色，遊船與釣魚是主要活動。", "address": "苗栗縣頭屋鄉明德村"},
        {"name": "獅頭山風景區", "description": "閩南廟宇與禪寺依山而建，宗教與自然融合的景點。", "address": "苗栗縣南庄鄉獅山村"},
        {"name": "南庄老街", "description": "賽夏族與客家文化交融的山城老街。", "address": "苗栗縣南庄鄉東村"},
        {"name": "卓蘭觀光果園", "description": "苗栗水果之鄉，採果體驗與鮮果直售聞名。", "address": "苗栗縣卓蘭鎮"},
        {"name": "通霄神社", "description": "日治時代遺址，台灣少數保存較完整的神社。", "address": "苗栗縣通霄鎮虎頭山"},
        {"name": "大湖酒莊", "description": "苗栗大湖草莓聞名全台，草莓酒釀與體驗農場備受歡迎。", "address": "苗栗縣大湖鄉"},
    ],
    "彰化": [
        {"name": "彰化大佛", "description": "彰化地標，八卦山大佛高達22公尺，俯瞰彰化市區。", "address": "彰化市卦山路19號"},
        {"name": "鹿港老街", "description": "清代商業重鎮，保存閩南式街屋，文物豐富。", "address": "彰化縣鹿港鎮中山路"},
        {"name": "鹿港龍山寺", "description": "清代古廟，台灣三大龍山寺之一，藝術價值極高。", "address": "彰化縣鹿港鎮龍山街100號"},
        {"name": "溪湖糖廠", "description": "日治時期製糖廠，五分車復駛為觀光吸引力。", "address": "彰化縣溪湖鎮彰水路二段"},
        {"name": "彰化扇形車庫", "description": "全台唯一、全球罕見的扇形車庫，台鐵維修基地。", "address": "彰化市彰美路一段1號"},
        {"name": "田中央生態農莊", "description": "有機農業體驗，稻田藝術季聞名全台。", "address": "彰化縣田中鎮"},
        {"name": "北斗就業服務站", "description": "清代古城遺址，奠安宮彌勒大佛聞名。", "address": "彰化縣北斗鎮"},
        {"name": "二林葡萄生態農業區", "description": "彰化葡萄酒鄉，採果體驗與葡萄酒品嚐深受歡迎。", "address": "彰化縣二林鎮"},
        {"name": "花壇台灣民俗村", "description": "重現清代台灣傳統建築與民俗的主題園區。", "address": "彰化縣花壇鄉"},
        {"name": "王功漁港", "description": "彰化最大漁港，夕陽景觀迷人、海鮮料理豐富。", "address": "彰化縣芳苑鄉王功村"},
    ],
    "南投": [
        {"name": "日月潭", "description": "台灣最大內陸湖泊，山光水色、四季皆美。", "address": "南投縣魚池鄉水社村"},
        {"name": "溪頭自然教育園區", "description": "台大實驗林，神木、竹林與高山步道聞名。", "address": "南投縣鹿谷鄉內湖村溪頭路"},
        {"name": "清境農場", "description": "高山牧場，歐式建築與綿羊秀享譽全台。", "address": "南投縣仁愛鄉大同村境新巷168號"},
        {"name": "集集小鎮", "description": "古老的鐵道車站與保存完好的綠色隧道。", "address": "南投縣集集鎮民生路"},
        {"name": "竹山天梯", "description": "全台最長的人行吊橋，橫跨濁水溪溪谷。", "address": "南投縣竹山鎮"},
        {"name": "埔里紙教堂", "description": "921地震後由日本重建的紙管教堂，象徵重生。", "address": "南投縣埔里鎮桃米里桃米路"},
        {"name": "九族文化村", "description": "原住民族文化主題樂園，九大族群文物展示與表演。", "address": "南投縣魚池鄉大林村"},
        {"name": "惠蓀林場", "description": "台大實驗林場，原始森林與高山步道探索。", "address": "南投縣仁愛鄉"},
        {"name": "奧萬大國家森林遊樂區", "description": "台灣最大楓香林，秋季賞楓勝地。", "address": "南投縣仁愛鄉萬豐村"},
        {"name": "玉山國家公園", "description": "台灣最高峰，高山生態與壯闊山景震撼人心。", "address": "南投縣信義鄉東埔村"},
    ],
    "雲林": [
        {"name": "北港朝天宮", "description": "全台最著名的媽祖廟，每年進香活動盛況空前。", "address": "雲林縣北港鎮中山路178號"},
        {"name": "劍湖山世界", "description": "雲林最大主題遊樂園，雲霄飛車刺激著名。", "address": "雲林縣古坑鄉棋盤村1號"},
        {"name": "古坑咖啡", "description": "台灣咖啡發源地，台灣咖啡節每年吸引大批遊客。", "address": "雲林縣古坑鄉"},
        {"name": "西螺老街", "description": "清代歷史老街，醬油文化與巴洛克式建築聞名。", "address": "雲林縣西螺鎮延平路"},
        {"name": "虎尾布袋戲館", "description": "布袋戲發源地，台灣偶戲文化博物館。", "address": "雲林縣虎尾鎮林森路一段498號"},
        {"name": "成龍溼地", "description": "台灣最大的人工溼地，候鳥棲息生態豐富。", "address": "雲林縣口湖鄉成龍村"},
        {"name": "麥寮拱範宮", "description": "台灣媽祖廟中規模最大之一，宗教文化中心。", "address": "雲林縣麥寮鄉中正路26號"},
        {"name": "林內紫斑蝶保護區", "description": "每年春季數百萬隻紫斑蝶北遷奇景。", "address": "雲林縣林內鄉"},
        {"name": "口湖金湖休閒農業區", "description": "台灣蚵仔養殖重鎮，漁村生態與鮮蚵料理聞名。", "address": "雲林縣口湖鄉"},
        {"name": "斗六太平老街", "description": "清代街屋保存完整，日治時期木造建築有特色。", "address": "雲林縣斗六市太平路"},
    ],
    "嘉義": [
        {"name": "阿里山國家風景區", "description": "台灣最著名高山景區，雲海、神木、森林鐵路舉世聞名。", "address": "嘉義縣阿里山鄉"},
        {"name": "奮起湖老街", "description": "阿里山鐵路中途站，日式老街與便當聞名全台。", "address": "嘉義縣竹崎鄉中和村"},
        {"name": "嘉義公園", "description": "嘉義市最大公園，射日塔可鳥瞰全市。", "address": "嘉義市東區公園街42號"},
        {"name": "嘉義城隍廟", "description": "清代古廟，廟前小吃街是嘉義美食集散地。", "address": "嘉義市東區吳鳳北路168號"},
        {"name": "文化路夜市", "description": "嘉義最熱鬧的夜市，雞肉飯與火雞肉飯聞名。", "address": "嘉義市東區文化路"},
        {"name": "嘉義布袋漁港", "description": "嘉義最大漁港，海鮮市場與夕陽美景著名。", "address": "嘉義縣布袋鎮"},
        {"name": "故宮南院", "description": "亞洲藝術文化博物館，融合東方建築美學。", "address": "嘉義縣太保市故宮大道888號"},
        {"name": "梅山公園", "description": "茶鄉梅山，太平老街與梅樹景觀吸引遊客。", "address": "嘉義縣梅山鄉梅山公園"},
        {"name": "鰲鼓濕地森林園區", "description": "全台面積最大的人工林，候鳥天堂。", "address": "嘉義縣東石鄉鰲鼓村"},
        {"name": "北回歸線太陽館", "description": "嘉義水上北回歸線標誌，天文科學展示館。", "address": "嘉義縣水上鄉"},
    ],
    "台南": [
        {"name": "赤崁樓", "description": "荷蘭殖民時期建築，台南代表性古蹟。", "address": "台南市中西區民族路二段212號"},
        {"name": "安平古堡", "description": "荷蘭人在台灣建造的第一座城堡。", "address": "台南市安平區國勝路82號"},
        {"name": "台南孔廟", "description": "全台最早的孔廟，「全台首學」。", "address": "台南市中西區南門路2號"},
        {"name": "花園夜市", "description": "台灣最大夜市，週末假日熱鬧非凡。", "address": "台南市北區海安路三段533號"},
        {"name": "億載金城", "description": "清代砲台遺址，融合西式砲台建築。", "address": "台南市安平區光州路3號"},
        {"name": "鹽水蜂炮", "description": "每年元宵節舉辦的知名煙火盛典。", "address": "台南市鹽水區"},
        {"name": "安平樹屋", "description": "百年老榕樹與倉庫共生的神秘景點。", "address": "台南市安平區古堡街108號"},
        {"name": "神農街", "description": "台南最具文藝氣息的老街，夜晚特別迷人。", "address": "台南市中西區神農街"},
        {"name": "奇美博物館", "description": "收藏豐富的私立博物館，希臘神殿外觀壯觀。", "address": "台南市仁德區文華路二段66號"},
        {"name": "台江國家公園", "description": "黑面琵鷺保育地，生態豐富的濕地公園。", "address": "台南市安南區"},
        {"name": "七股鹽山", "description": "台灣傳統製鹽產業文化保存地，鹽山是地標。", "address": "台南市七股區鹽埕里66號"},
        {"name": "山上花園水道博物館", "description": "日治時代自來水廠改建，全台最美工業遺址之一。", "address": "台南市山上區山上里1號"},
        {"name": "關子嶺溫泉", "description": "台灣著名泥漿溫泉，泡湯兼賞夜景。", "address": "台南市白河區關子嶺"},
        {"name": "永康糖廠", "description": "日治時期製糖廠，冰品聞名、園區懷舊。", "address": "台南市永康區中山南路601號"},
        {"name": "國華街", "description": "台南最熱鬧的美食街，小吃林立、香氣四溢。", "address": "台南市中西區國華街"},
    ],
    "屏東": [
        {"name": "墾丁國家公園", "description": "台灣第一座國家公園，珊瑚礁海岸與熱帶植被聞名全球。", "address": "屏東縣恆春鎮"},
        {"name": "大鵬灣國家風景區", "description": "台灣最大的潟湖，水上活動與帆船體驗絕佳。", "address": "屏東縣東港鎮大鵬灣"},
        {"name": "東港鮪魚季", "description": "每年秋季舉辦的黑鮪魚文化觀光季，現切黑鮪魚聞名。", "address": "屏東縣東港鎮"},
        {"name": "恆春古城", "description": "清代四門城牆保存完整，全台少見的古城遺址。", "address": "屏東縣恆春鎮中山路"},
        {"name": "小琉球", "description": "台灣唯一的珊瑚礁島嶼，浮潛生態豐富、海龜常見。", "address": "屏東縣琉球鄉"},
        {"name": "三地門原住民文化園區", "description": "排灣族與魯凱族文化展示，原住民藝術品聞名。", "address": "屏東縣三地門鄉"},
        {"name": "霧台鄉魯凱族聚落", "description": "海拔最高的石板屋部落，百合花與石雕文化著名。", "address": "屏東縣霧台鄉"},
        {"name": "墾丁大街", "description": "墾丁最熱鬧的商圈，夜市文化與海洋活動集中地。", "address": "屏東縣恆春鎮墾丁路"},
        {"name": "四重溪溫泉", "description": "台灣四大溫泉之一，碳酸氫鈉泉，日治時代即知名。", "address": "屏東縣車城鄉四重溪"},
        {"name": "來義鄉排灣族文化", "description": "排灣族最大聚落，傳統祭典與百步蛇圖騰文化著名。", "address": "屏東縣來義鄉"},
    ],
    "宜蘭": [
        {"name": "礁溪溫泉", "description": "台灣難得的平地溫泉，泉質透明，距台北車程僅1小時。", "address": "宜蘭縣礁溪鄉"},
        {"name": "羅東夜市", "description": "宜蘭最大夜市，三星蔥餅、卜肉等在地小吃聞名。", "address": "宜蘭縣羅東鎮公園路"},
        {"name": "太平山國家森林遊樂區", "description": "高山森林鐵路、蹦蹦車與翠峰湖為重要景觀。", "address": "宜蘭縣大同鄉太平山"},
        {"name": "龜山島", "description": "蘭陽平原外海的火山島，賞鯨、牛奶海與龜尾湖著名。", "address": "宜蘭縣頭城鎮龜山島"},
        {"name": "冬山河親水公園", "description": "國際競技標準的泛舟場地，花博及各大節慶舉辦地。", "address": "宜蘭縣冬山鄉冬山河"},
        {"name": "蘭陽博物館", "description": "融合地質景觀的博物館建築，展示蘭陽平原人文歷史。", "address": "宜蘭縣頭城鎮青雲路三段750號"},
        {"name": "頭城老街", "description": "蘭陽平原最早開墾的聚落，清代街屋保存較完整。", "address": "宜蘭縣頭城鎮和平街"},
        {"name": "羅東林業文化園區", "description": "日治時期伐木業遺址，儲木池與蒸汽火車展示。", "address": "宜蘭縣羅東鎮中正北路118號"},
        {"name": "中興文創園區", "description": "舊造紙廠改造的文創基地，紙博物館與藝文展演空間。", "address": "宜蘭市造紙路1號"},
        {"name": "南方澳漁港", "description": "宜蘭最大漁港，南安宮鯖魚祭與新鮮海產聞名。", "address": "宜蘭縣蘇澳鎮南方澳"},
    ],
    "花蓮": [
        {"name": "太魯閣國家公園", "description": "台灣最著名的峽谷景觀，世界級自然奇景。", "address": "花蓮縣秀林鄉"},
        {"name": "七星潭", "description": "弧形海灣，月牙形礫石海灘。", "address": "花蓮縣新城鄉七星街"},
        {"name": "鯉魚潭", "description": "台灣東部最大內陸湖泊，景色秀麗。", "address": "花蓮縣壽豐鄉池南村"},
        {"name": "花蓮文創園區", "description": "舊酒廠改造，藝文展覽常設於此。", "address": "花蓮市中華路144號"},
        {"name": "壽豐鄉雲山水", "description": "夢幻湖景，自然生態豐富。", "address": "花蓮縣壽豐鄉"},
        {"name": "花蓮石雕博物館", "description": "展示各國石雕藝術的主題博物館。", "address": "花蓮市海岸路108號"},
        {"name": "東大門夜市", "description": "花蓮最大夜市，原住民風味美食齊聚。", "address": "花蓮市國聯一路與自強路口"},
        {"name": "慶修院", "description": "日治時期保留的日式真言宗寺院。", "address": "花蓮縣吉安鄉中興路345-1號"},
        {"name": "瑞穗溫泉", "description": "碳酸氫鈉泉，素有「美人湯」之稱。", "address": "花蓮縣瑞穗鄉溫泉路"},
        {"name": "富里鄉六十石山", "description": "「東台灣的金針花海」，每年夏秋盛開。", "address": "花蓮縣富里鄉竹田村"},
    ],
    "台東": [
        {"name": "知本溫泉", "description": "台東最著名的溫泉區，硫磺泉質豐富，溫泉飯店林立。", "address": "台東縣卑南鄉溫泉村"},
        {"name": "綠島", "description": "以朝日溫泉聞名，珊瑚礁海域是台灣浮潛聖地。", "address": "台東縣綠島鄉"},
        {"name": "蘭嶼", "description": "達悟族原住民文化，拼板舟、地下屋與飛魚季舉世聞名。", "address": "台東縣蘭嶼鄉"},
        {"name": "池上鄉稻田", "description": "台灣最美稻田，金城武樹、伯朗大道吸引無數遊客。", "address": "台東縣池上鄉"},
        {"name": "太麻里金針山", "description": "每年夏秋金針花海遍野，日出景色壯觀迷人。", "address": "台東縣太麻里鄉金針山"},
        {"name": "台東森林公園", "description": "琵琶湖與活水湖環繞，海岸林步道優美。", "address": "台東市森林公園路"},
        {"name": "卑南文化公園", "description": "台灣規模最大的史前遺址，卑南族文物展示館。", "address": "台東市文化公園路200號"},
        {"name": "東河橋步道", "description": "秀姑巒溪出海口，泛舟與溪谷景觀吸引遊客。", "address": "台東縣東河鄉"},
        {"name": "鹿野高台", "description": "台灣熱氣球嘉年華舉辦地，俯瞰花東縱谷無敵美景。", "address": "台東縣鹿野鄉高台路"},
        {"name": "富岡漁港", "description": "綠島與蘭嶼的交通起點，新鮮旗魚聞名。", "address": "台東市富岡里"},
    ],
    "高雄": [
        {"name": "蓮池潭", "description": "龍虎塔為標誌，民間信仰聖地。", "address": "高雄市左營區蓮池潭"},
        {"name": "旗津海岸公園", "description": "離島風情，沙灘與海鮮聞名。", "address": "高雄市旗津區旗津三路"},
        {"name": "駁二藝術特區", "description": "舊倉庫改造的文創藝術園區。", "address": "高雄市鹽埕區大勇路1號"},
        {"name": "六合夜市", "description": "高雄最著名的夜市，海鮮料理豐富。", "address": "高雄市新興區六合二路"},
        {"name": "西子灣", "description": "夕陽美景著名，中山大學校園內。", "address": "高雄市鼓山區蓮海路"},
        {"name": "愛河", "description": "高雄浪漫地標，兩岸景色優美。", "address": "高雄市苓雅區七賢三路"},
        {"name": "美濃客家文化園區", "description": "展現客家文化與油紙傘工藝的特色景點。", "address": "高雄市美濃區民族路49巷11號"},
        {"name": "佛光山", "description": "台灣最大佛教聖地，大佛高達36公尺。", "address": "高雄市大樹區興田路153號"},
        {"name": "高雄市立美術館", "description": "南台灣最重要的現代美術館，館藏豐富。", "address": "高雄市鼓山區美術館路80號"},
        {"name": "茂林國家風景區", "description": "紫蝶幽谷，每年紫斑蝶遷徙奇景。", "address": "高雄市茂林區"},
    ],
}


class CityScraper(BaseScraper):
    """Scrapes tourist attraction data from Taiwan city tourism websites.

    Uses Playwright (async) to handle JavaScript-rendered pages.
    Integrates ``playwright-stealth`` when available to reduce bot-detection.
    Falls back to curated static data when live scraping fails.

    Parameters
    ----------
    city : str
        One of 台北、新北、桃園、台中、基隆、新竹、苗栗、彰化、南投、雲林、
        嘉義、台南、屏東、宜蘭、花蓮、台東、高雄.
    headless : bool
        Whether to launch Chromium in headless mode (default ``True``).
    max_items : int
        Maximum number of attractions to return (default ``10``).
    """

    def __init__(self, city: str, headless: bool = True, max_items: int = 10):
        super().__init__(headless=headless)
        self.city = city
        self.max_items = max_items

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch(self, **kwargs) -> list[Attraction]:
        """Fetch attractions for ``self.city``.

        Attempts live scraping first; falls back to static data on failure.
        """
        config = CITY_CONFIG.get(self.city)
        if config is None:
            return self._fallback_attractions()

        try:
            attractions = await self._scrape(config)
            if not attractions:
                attractions = self._fallback_attractions()
            return attractions[: self.max_items]
        except Exception:
            return self._fallback_attractions()[: self.max_items]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _scrape(self, config: dict) -> list[Attraction]:
        """Launch browser and scrape the target page."""
        attractions: list[Attraction] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1280, "height": 800},
                locale="zh-TW",
            )
            page = await context.new_page()

            if _STEALTH_AVAILABLE:
                await stealth_async(page)

            try:
                await page.goto(config["url"], timeout=30_000, wait_until="domcontentloaded")
                await self.random_delay(2.0, 4.0)
                await self._human_scroll(page)
                await self.random_delay(1.0, 2.0)

                cards = await page.query_selector_all(config["card_selector"])
                for card in cards[: self.max_items]:
                    attraction = await self._parse_card(page, card, config)
                    if attraction:
                        attractions.append(attraction)
            finally:
                await context.close()
                await browser.close()

        return attractions

    @staticmethod
    async def _human_scroll(page: Page) -> None:
        """Simulate human-like scrolling behaviour."""
        for _ in range(random.randint(3, 6)):
            scroll_amount = random.randint(300, 700)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.4, 1.0))

    async def _parse_card(
        self, page: Page, card: Any, config: dict
    ) -> Attraction | None:
        """Extract a single :class:`Attraction` from a card element."""
        try:
            name_el = await card.query_selector(config["name_selector"])
            name = (await name_el.inner_text()).strip() if name_el else ""
            if not name:
                return None

            desc_el = await card.query_selector(config["desc_selector"])
            description = (await desc_el.inner_text()).strip() if desc_el else ""

            addr_el = await card.query_selector(config["addr_selector"])
            address = (await addr_el.inner_text()).strip() if addr_el else ""

            img_el = await card.query_selector(config["img_selector"])
            image_url = ""
            if img_el:
                image_url = (await img_el.get_attribute("src")) or (
                    await img_el.get_attribute("data-src")
                ) or ""

            link_el = await card.query_selector(config["link_selector"])
            source_url = ""
            if link_el:
                href = await link_el.get_attribute("href") or ""
                source_url = href if href.startswith("http") else config["url"]

            return Attraction(
                name=name,
                description=description,
                address=address,
                city=self.city,
                image_url=image_url,
                source_url=source_url,
            )
        except Exception:
            return None

    def _fallback_attractions(self) -> list[Attraction]:
        """Return curated static attractions when live scraping fails."""
        data = FALLBACK_ATTRACTIONS.get(self.city, [])
        return [
            Attraction(
                name=item["name"],
                description=item["description"],
                address=item.get("address", ""),
                city=self.city,
            )
            for item in data
        ]

