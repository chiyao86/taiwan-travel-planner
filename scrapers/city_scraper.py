"""CityScraper – scrapes attraction data from Taiwan city tourism portals.

Supported cities and their official tourism URLs:
    台北  → https://www.travel.taipei/
    新北  → https://newtaipei.travel/
    桃園  → https://travel.tycg.gov.tw/
    台中  → https://travel.taichung.gov.tw/
    台南  → https://www.twtainan.net/
    高雄  → https://khh.travel/
    基隆  → https://travel.klcg.gov.tw/
    新竹  → https://tourism.hccg.gov.tw/
    苗栗  → https://miaolitravel.net/
    彰化  → https://tourism.chcg.gov.tw/
    南投  → https://travel.nantou.gov.tw/
    雲林  → https://tour.yunlin.gov.tw/
    嘉義  → https://travel.chiayi.gov.tw/
    屏東  → https://pingtung.easytravel.com.tw/
    宜蘭  → https://www.taiwan.net.tw/
    花蓮  → https://tour-hualien.hl.gov.tw/
    台東  → https://tour.taitung.gov.tw/
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
        "card_selector": "div.tour-item, li.tour-item, div.card-item",
        "name_selector": "h3, h4, .item-title",
        "desc_selector": "p, .item-desc",
        "addr_selector": ".address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "桃園": {
        "url": "https://travel.tycg.gov.tw/zh-tw/travel/tourlist",
        "card_selector": "div.list-item, li.list-item, div.travel-item",
        "name_selector": "h3, h4, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
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
    "台南": {
        "url": "https://www.twtainan.net/zh-tw/attractions/",
        "card_selector": "div.item, li.spot-item",
        "name_selector": "h3, .spot-name",
        "desc_selector": "p, .spot-desc",
        "addr_selector": ".address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "高雄": {
        "url": "https://khh.travel/zh-tw/attractions/list/",
        "card_selector": "li.attraction-item, div.attraction-item",
        "name_selector": "h3",
        "desc_selector": "p.desc",
        "addr_selector": "p.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "基隆": {
        "url": "https://travel.klcg.gov.tw/SiteMap.aspx?n=8184",
        "card_selector": "div.scenic-item, li.scenic-item, div.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "新竹": {
        "url": "https://tourism.hccg.gov.tw/chtravel/app/travel/list?id=37",
        "card_selector": "div.item, li.travel-item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "苗栗": {
        "url": "https://miaolitravel.net/article.aspx?sno=03004313",
        "card_selector": "div.item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "彰化": {
        "url": "https://tourism.chcg.gov.tw/Attractions.aspx",
        "card_selector": "div.list-item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "南投": {
        "url": "https://travel.nantou.gov.tw/attractions/",
        "card_selector": "div.attractions-item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "雲林": {
        "url": "https://tour.yunlin.gov.tw/mainssl/modules/MySpace/BlogList.php?sn=yunlin&cn=ZC10350618",
        "card_selector": "div.item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "嘉義": {
        "url": "https://travel.chiayi.gov.tw/TravelInformation/C000005/1",
        "card_selector": "div.item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "屏東": {
        "url": "https://pingtung.easytravel.com.tw/scenic/",
        "card_selector": "div.scenic-item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "宜蘭": {
        "url": "https://www.taiwan.net.tw/m1.aspx?sNo=0000064&keyString=%e5%ae%9c%e8%98%ad%5e%5e%5e%5e0",
        "card_selector": "div.item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "花蓮": {
        "url": "https://tour-hualien.hl.gov.tw/TourList.aspx?n=109&sms=12302",
        "card_selector": "div.scenic-item, li.item",
        "name_selector": "h3.scenic-name, h3, .title",
        "desc_selector": "p.scenic-desc, p, .desc",
        "addr_selector": "span.scenic-addr, .address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "台東": {
        "url": "https://tour.taitung.gov.tw/zh-tw/attraction",
        "card_selector": "div.item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": ".address",
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
        {"name": "國立台灣博物館", "description": "台灣現存最古老的博物館，典藏自然史文物。", "address": "台北市中正區襄陽路2號"},
        {"name": "象山", "description": "俯瞰台北101及市景的熱門登山步道。", "address": "台北市信義區"},
        {"name": "迪化街", "description": "百年南北貨老街，年節前採購熱點。", "address": "台北市大同區迪化街一段"},
    ],
    "新北": [
        {"name": "九份老街", "description": "依山而建的山城老街，以茶館與夜景聞名。", "address": "新北市瑞芳區九份"},
        {"name": "平溪天燈", "description": "每年元宵節舉辦的天燈節，祈福氛圍濃厚。", "address": "新北市平溪區"},
        {"name": "淡水老街", "description": "百年歷史老街，夕陽美景著稱。", "address": "新北市淡水區中正路"},
        {"name": "三峽老街", "description": "台灣保存最完整的清代商業街道之一。", "address": "新北市三峽區民權街"},
        {"name": "烏來溫泉", "description": "泰雅族原住民聚落，溫泉與瀑布兼具。", "address": "新北市烏來區溫泉街"},
        {"name": "野柳地質公園", "description": "奇特海蝕地形，女王頭為著名地標。", "address": "新北市萬里區野柳里167-1號"},
        {"name": "十分瀑布", "description": "台版尼加拉瀑布，壯觀的簾幕型瀑布。", "address": "新北市平溪區十分里"},
        {"name": "金瓜石", "description": "日治時期黃金礦業遺址，黃金博物館值得一遊。", "address": "新北市瑞芳區金瓜石"},
        {"name": "石碇老街", "description": "依溪而建的老街，豆腐料理聞名。", "address": "新北市石碇區石碇老街"},
        {"name": "三芝淺水灣", "description": "北海岸著名海灘，夕陽景色迷人。", "address": "新北市三芝區淺水灣"},
        {"name": "板橋林家花園", "description": "清代豪門庭院，建築藝術瑰寶。", "address": "新北市板橋區西門街9號"},
        {"name": "深坑老街", "description": "以臭豆腐聞名的老街，建築保存完好。", "address": "新北市深坑區北深路三段"},
        {"name": "鶯歌陶瓷博物館", "description": "台灣陶瓷文化重鎮，老街與博物館並存。", "address": "新北市鶯歌區文化路200號"},
        {"name": "北投溫泉博物館", "description": "台灣唯一的溫泉博物館，日式建築典雅。", "address": "新北市北投區中山路2號"},
        {"name": "福隆海水浴場", "description": "東北角知名海灘，每年舉辦沙雕藝術節。", "address": "新北市貢寮區福隆里"},
    ],
    "桃園": [
        {"name": "桃園神社", "description": "全台保存最完整的日治時期神社建築。", "address": "桃園市桃園區成功路三段200號"},
        {"name": "石門水庫", "description": "台灣重要水庫，環境優美，烤肉活魚聞名。", "address": "桃園市龍潭區石門水庫"},
        {"name": "小人國主題樂園", "description": "以世界知名地標縮小模型著稱的主題公園。", "address": "桃園市龍潭區幸福路"},
        {"name": "慈湖陵寢", "description": "蔣中正陵寢及兩蔣文化園區，衛兵交接儀式吸睛。", "address": "桃園市大溪區復興路一段"},
        {"name": "大溪老街", "description": "保有日治時代商街風貌，豆干名產聞名。", "address": "桃園市大溪區中山路"},
        {"name": "拉拉山國家森林遊樂區", "description": "台灣最大的天然巨木群，神木莊嚴壯觀。", "address": "桃園市復興區拉拉山"},
        {"name": "角板山公園", "description": "蔣介石行館舊址，居高臨下俯瞰大漢溪。", "address": "桃園市復興區角板山"},
        {"name": "八德埤塘生態公園", "description": "台灣最大的埤塘生態公園，白鷺鷥群棲。", "address": "桃園市八德區大同路"},
        {"name": "桃園地景藝術節", "description": "每年舉辦的大型地景藝術展覽活動。", "address": "桃園市各處"},
        {"name": "龍潭大池", "description": "桃園知名賞荷景點，週邊步道怡人。", "address": "桃園市龍潭區龍潭大池"},
        {"name": "桃園蓮花季", "description": "每年夏季的蓮花盛典，農田花田美不勝收。", "address": "桃園市觀音區"},
        {"name": "富田花園農場", "description": "薰衣草田、向日葵田等多種花卉園區。", "address": "桃園市復興區"},
        {"name": "虎頭山公園", "description": "桃園市區最大的郊山公園，可俯瞰市景。", "address": "桃園市桃園區龍壽街"},
        {"name": "溪洲公園", "description": "中壢著名親水公園，夏季戲水熱點。", "address": "桃園市中壢區溪洲街"},
        {"name": "桃園青埔特區", "description": "機場捷運沿線新興商業區，IKEA與棒球場座落。", "address": "桃園市中壢區高鐵北路"},
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
        {"name": "合歡山", "description": "台灣高山公路最高點，冬季賞雪聖地。", "address": "台中市仁愛鄉合歡山"},
        {"name": "台中文創園區", "description": "舊酒廠改建的文創聚落，展覽常態舉辦。", "address": "台中市南區復興路三段362號"},
        {"name": "清境農場", "description": "高山牧場，青青草原與歐式建築聞名。", "address": "南投縣仁愛鄉大同村壽亭巷170號"},
        {"name": "霧峰林家宅園", "description": "清代台灣五大家族之一，古蹟群保存完整。", "address": "台中市霧峰區民生路42號"},
        {"name": "大甲鎮瀾宮", "description": "全台最重要的媽祖廟，每年遶境活動盛大。", "address": "台中市大甲區順天路158號"},
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
        {"name": "高雄85大樓", "description": "台灣第二高樓，高雄市天際線代表。", "address": "高雄市苓雅區自強三路1號"},
        {"name": "鳳山舊城", "description": "清代鳳山縣城遺址，為國定古蹟。", "address": "高雄市鳳山區"},
        {"name": "橋頭糖廠", "description": "台灣第一座現代化糖廠，冰品聞名。", "address": "高雄市橋頭區糖廠路24號"},
        {"name": "壽山國家自然公園", "description": "高雄市區登山勝地，台灣獼猴棲息地。", "address": "高雄市鼓山區壽山路"},
        {"name": "衛武營國家藝術文化中心", "description": "全球最大管風琴所在地，南台灣表演藝術聖地。", "address": "高雄市鳳山區三多一路1號"},
    ],
    "基隆": [
        {"name": "和平島地質公園", "description": "奇岩怪石景觀，珊瑚礁潮間帶生態豐富。", "address": "基隆市中正區平一路360號"},
        {"name": "基隆廟口夜市", "description": "基隆最著名的夜市，小吃文化聞名。", "address": "基隆市仁愛區愛三路"},
        {"name": "中正公園", "description": "白色觀世音雕像俯瞰基隆港，景色壯觀。", "address": "基隆市中正區中正路"},
        {"name": "基隆港", "description": "台灣第一大商業港，郵輪進出熱點。", "address": "基隆市中正區港西街5號"},
        {"name": "獅球嶺砲台", "description": "清代砲台遺址，俯瞰基隆市景。", "address": "基隆市中山區獅球嶺砲台"},
        {"name": "八斗子漁港", "description": "北台灣重要漁港，海鮮料理豐富。", "address": "基隆市中正區八斗子漁港"},
        {"name": "望幽谷", "description": "碧海藍天的秘境，步道悠然怡人。", "address": "基隆市中正區望幽谷"},
        {"name": "正濱漁港", "description": "彩色漁港建築，咖啡館文青聚集地。", "address": "基隆市中正區正濱漁港"},
        {"name": "基隆燈塔", "description": "台灣重要航行標誌，位於基隆港口。", "address": "基隆市中正區平一路360號"},
        {"name": "潮境公園", "description": "八斗子漁港旁的海濱公園，海風宜人。", "address": "基隆市中正區北寧路369巷"},
        {"name": "情人湖", "description": "基隆市郊的山中小湖，自然生態豐富。", "address": "基隆市安樂區情人湖路"},
        {"name": "仙洞巖", "description": "天然岩洞寺廟，奇特地質景觀。", "address": "基隆市中山區仙洞街50號"},
        {"name": "碧砂漁港", "description": "漁貨直銷中心，海鮮餐廳林立。", "address": "基隆市中正區碧砂漁港"},
        {"name": "虎仔山燈節", "description": "每年中秋節前後的元宵燈節活動地點。", "address": "基隆市仁愛區虎仔山"},
        {"name": "獅頭山步道", "description": "基隆市區登山步道，可俯瞰基隆港全景。", "address": "基隆市中山區獅頭山"},
    ],
    "新竹": [
        {"name": "新竹城隍廟", "description": "全台最著名的城隍廟，廟口美食聞名全台。", "address": "新竹市北區中山路75號"},
        {"name": "新竹公園", "description": "新竹市最大公園，動物園和孔廟相鄰。", "address": "新竹市東區東大路一段88號"},
        {"name": "玻璃工藝博物館", "description": "全台唯一玻璃工藝專業博物館。", "address": "新竹市東區東大路一段2號"},
        {"name": "新竹縣立文化局", "description": "新竹文化中心，展覽活動豐富。", "address": "新竹市東區東大路二段17號"},
        {"name": "關西老街", "description": "客家族群聚居的百年老街，豆干聞名。", "address": "新竹縣關西鎮中山路"},
        {"name": "內灣老街", "description": "山中小火車終點站，客家野薑花粿聞名。", "address": "新竹縣橫山鄉內灣老街"},
        {"name": "新竹漁港", "description": "海鮮料理集中地，米粉與貢丸同樣有名。", "address": "新竹市北區漁港路"},
        {"name": "司馬庫斯", "description": "泰雅族部落，台灣最壯觀的巨木群落之一。", "address": "新竹縣尖石鄉司馬庫斯"},
        {"name": "薰衣草森林", "description": "以薰衣草田為主題的浪漫休閒農場。", "address": "新竹縣尖石鄉新樂村"},
        {"name": "五峰清泉溫泉", "description": "山中溫泉勝地，張學良故居在此。", "address": "新竹縣五峰鄉清泉村"},
        {"name": "新埔義民廟", "description": "台灣最重要的客家信仰中心，義民祭盛大。", "address": "新竹縣新埔鎮義民路三段360號"},
        {"name": "峨眉湖（大埔水庫）", "description": "湖光山色，彌勒大佛慈顏常駐。", "address": "新竹縣峨眉鄉峨眉湖"},
        {"name": "新竹17公里海岸線", "description": "濱海自行車道，候鳥生態豐富。", "address": "新竹市濱海路"},
        {"name": "新竹東門城", "description": "清代竹塹城遺址，台灣現存最完整的城樓之一。", "address": "新竹市東區中正路"},
        {"name": "北埔老街", "description": "客家文化重鎮，慈天宮與茶文化聞名。", "address": "新竹縣北埔鄉北埔老街"},
    ],
    "苗栗": [
        {"name": "三義木雕博物館", "description": "展示三義木雕藝術的主題博物館。", "address": "苗栗縣三義鄉廣盛村廣聲新城88號"},
        {"name": "苗栗勝興車站", "description": "台灣鐵路最高點老車站，懷舊氣息濃厚。", "address": "苗栗縣三義鄉勝興村14號"},
        {"name": "龍騰斷橋", "description": "日治時代紅磚拱橋，1935年地震後成廢墟美景。", "address": "苗栗縣三義鄉龍騰村"},
        {"name": "南庄老街", "description": "客家與原住民文化交融的山城老街。", "address": "苗栗縣南庄鄉南庄老街"},
        {"name": "獅頭山風景區", "description": "著名宗教聖地，廟宇群沿山壁而建。", "address": "苗栗縣南庄鄉獅山村"},
        {"name": "飛牛牧場", "description": "全台知名牧場，乳品新鮮美味。", "address": "苗栗縣通霄鎮南和里飛牛牧場"},
        {"name": "通霄神社", "description": "全台保存最完整的日治時期神社之一。", "address": "苗栗縣通霄鎮通霄神社"},
        {"name": "泰安溫泉", "description": "苗栗最著名的碳酸氫鈉美人湯。", "address": "苗栗縣泰安鄉泰安溫泉"},
        {"name": "苗栗客家文化園區", "description": "展現台灣客家族群文化的主題公園。", "address": "苗栗縣銅鑼鄉九湖村銅科南路6號"},
        {"name": "舊山線鐵道自行車", "description": "在廢棄鐵路上騎乘，穿越隧道橋梁。", "address": "苗栗縣三義鄉舊山線鐵道"},
        {"name": "象鼻部落", "description": "泰雅族原住民聚落，梅花盛開時最美。", "address": "苗栗縣泰安鄉象鼻村"},
        {"name": "苑裡老街", "description": "保有早期農業社區風貌，藺草編織聞名。", "address": "苗栗縣苑裡鎮苑裡老街"},
        {"name": "明德水庫", "description": "後龍溪支流上的水庫，環境優美清幽。", "address": "苗栗縣頭屋鄉明德村"},
        {"name": "西湖渡假村", "description": "螢火蟲生態觀賞及休閒農場。", "address": "苗栗縣三灣鄉西湖村西湖渡假村"},
        {"name": "大湖草莓季", "description": "台灣最有名的草莓產地，冬春採果體驗。", "address": "苗栗縣大湖鄉"},
    ],
    "彰化": [
        {"name": "彰化八卦山大佛", "description": "台灣最具代表性的大佛像，高達22公尺。", "address": "彰化市八卦山風景區"},
        {"name": "鹿港老街", "description": "清代台灣第二大城，文化古蹟最密集的老街。", "address": "彰化縣鹿港鎮中山路"},
        {"name": "鹿港龍山寺", "description": "全台最完整的清代廟宇建築群。", "address": "彰化縣鹿港鎮金門街81號"},
        {"name": "溪湖糖廠", "description": "五分車體驗，製糖產業文化保存地。", "address": "彰化縣溪湖鎮彰水路二段762號"},
        {"name": "田尾公路花園", "description": "台灣最大的公路花卉市集，四季花卉競豔。", "address": "彰化縣田尾鄉公路花園"},
        {"name": "扇形車庫", "description": "全亞洲唯一仍在運作的扇形鐵路車庫。", "address": "彰化市彰美路一段1號"},
        {"name": "二林酒莊", "description": "台灣葡萄酒重鎮，葡萄採摘體驗聞名。", "address": "彰化縣二林鎮二林酒莊"},
        {"name": "北斗奠安宮", "description": "全台最大的媽祖廟之一，香火鼎盛。", "address": "彰化縣北斗鎮斗中路111號"},
        {"name": "彰化縣文化局", "description": "彰化文化中心，常態性展覽豐富。", "address": "彰化市卦山路4號"},
        {"name": "王功漁港", "description": "西部沿海著名漁港，蚵仔料理聞名。", "address": "彰化縣芳苑鄉王功漁港"},
        {"name": "大村葡萄產區", "description": "彰化知名葡萄故鄉，夏季採果體驗熱門。", "address": "彰化縣大村鄉"},
        {"name": "員林百果山", "description": "各種水果種植，農業體驗豐富。", "address": "彰化縣員林市百果山"},
        {"name": "芬園寶藏寺", "description": "主祀觀世音菩薩，廟貌莊嚴宏偉。", "address": "彰化縣芬園鄉彰南路三段270號"},
        {"name": "鹿港民俗文物館", "description": "清代古宅改建，展示傳統民俗文物。", "address": "彰化縣鹿港鎮中山路152號"},
        {"name": "彰化孔廟", "description": "台灣少數仍定期舉辦釋奠禮的孔廟。", "address": "彰化市孔門路30號"},
    ],
    "南投": [
        {"name": "日月潭", "description": "台灣最大淡水湖，山光水色名列台灣八景。", "address": "南投縣魚池鄉水社村"},
        {"name": "溪頭自然教育園區", "description": "大學實驗林，千年神木與竹林步道著稱。", "address": "南投縣鹿谷鄉森林路10號"},
        {"name": "清境農場", "description": "高山牧場，歐式風情與青青草原著稱。", "address": "南投縣仁愛鄉大同村壽亭巷170號"},
        {"name": "合歡山", "description": "台灣賞雪最熱門景點，高山公路必訪。", "address": "南投縣仁愛鄉合歡山"},
        {"name": "竹山紫南宮", "description": "全台最靈驗的土地公廟，香火鼎盛。", "address": "南投縣竹山鎮社寮里大公街40號"},
        {"name": "奧萬大國家森林遊樂區", "description": "台灣賞楓最著名景點，秋季火紅楓葉壯觀。", "address": "南投縣仁愛鄉松林村"},
        {"name": "埔里酒廠", "description": "紹興酒故鄉，酒廠文化園區可免費參觀。", "address": "南投縣埔里鎮中山路三段219號"},
        {"name": "九族文化村", "description": "台灣原住民族文化主題樂園。", "address": "南投縣魚池鄉大林村心星路45號"},
        {"name": "草屯工藝文化園區", "description": "台灣工藝研究發展中心所在地。", "address": "南投縣草屯鎮中正路573號"},
        {"name": "鹿谷凍頂茶區", "description": "凍頂烏龍茶故鄉，茶園景觀優美。", "address": "南投縣鹿谷鄉凍頂巷"},
        {"name": "神農部落（布農族）", "description": "布農族原住民聚落，射耳祭文化體驗。", "address": "南投縣信義鄉神農部落"},
        {"name": "杉林溪森林生態度假園區", "description": "高山森林度假村，杜鵑花季最美。", "address": "南投縣竹山鎮大鞍里杉林溪路"},
        {"name": "惠蓀林場", "description": "中興大學實習林場，步道豐富自然優美。", "address": "南投縣仁愛鄉互助村"},
        {"name": "魚池紅茶產區", "description": "台灣紅茶故鄉，日月潭紅茶獨特甘醇。", "address": "南投縣魚池鄉"},
        {"name": "集集綠色隧道", "description": "樟樹成蔭的火車鐵道旁林蔭步道。", "address": "南投縣集集鎮集集街"},
    ],
    "雲林": [
        {"name": "劍湖山世界", "description": "雲林縣最知名的主題遊樂園。", "address": "雲林縣古坑鄉坑口村1號"},
        {"name": "北港朝天宮", "description": "全台最著名的媽祖廟，每年遶境香火最盛。", "address": "雲林縣北港鎮中山路178號"},
        {"name": "虎尾糖廠", "description": "台灣最後一家製糖工廠，五分車保存良好。", "address": "雲林縣虎尾鎮廉使里光復路1號"},
        {"name": "古坑咖啡山", "description": "台灣咖啡產地，台灣咖啡節聞名。", "address": "雲林縣古坑鄉草嶺村"},
        {"name": "西螺老街", "description": "保有完整日治時代巴洛克風格建築群。", "address": "雲林縣西螺鎮太和路"},
        {"name": "草嶺風景區", "description": "雲林最著名山岳景點，石壁、峭壁、瀑布美景。", "address": "雲林縣古坑鄉草嶺村"},
        {"name": "口湖成龍濕地", "description": "海岸濕地生態，候鳥棲息地豐富。", "address": "雲林縣口湖鄉成龍村"},
        {"name": "雲林故事館", "description": "老建築改建的布袋戲文化展館。", "address": "雲林縣斗六市府文路22號"},
        {"name": "麥寮六輕工業區", "description": "台灣最大石化工業園區，特色觀光景點。", "address": "雲林縣麥寮鄉台塑工業園區"},
        {"name": "土庫順天宮", "description": "雲林著名媽祖廟，每年廟會熱鬧非凡。", "address": "雲林縣土庫鎮中正路"},
        {"name": "虎尾布袋戲館", "description": "以布袋戲為主題的文化展館，珍貴戲偶典藏豐富。", "address": "雲林縣虎尾鎮林森路一段498號"},
        {"name": "四湖鄉台子村", "description": "古早味農村聚落，傳統農業景觀保存完好。", "address": "雲林縣四湖鄉台子村"},
        {"name": "元長鄉花生文化館", "description": "台灣花生故鄉，花生製品種類豐富。", "address": "雲林縣元長鄉"},
        {"name": "雲林科技大學", "description": "雲林知名大學校園，創意設計聞名。", "address": "雲林縣斗六市大學路三段123號"},
        {"name": "林內茄苳老樹", "description": "台灣最大的茄苳老樹群，生態景觀獨特。", "address": "雲林縣林內鄉"},
    ],
    "嘉義": [
        {"name": "阿里山國家風景區", "description": "台灣最著名的高山景區，日出、雲海、神木聞名。", "address": "嘉義縣阿里山鄉"},
        {"name": "阿里山小火車", "description": "世界三大高山鐵路之一，穿越森林登上高山。", "address": "嘉義市北門站"},
        {"name": "嘉義公園", "description": "市區最大公園，射日塔可眺望市景。", "address": "嘉義市東區公園街42號"},
        {"name": "文化路夜市", "description": "嘉義最大夜市，火雞肉飯為必吃名物。", "address": "嘉義市東區文化路"},
        {"name": "嘉義縣表演藝術中心", "description": "南部重要表演藝術場館，節目豐富多元。", "address": "嘉義縣太保市祥和二路東段3號"},
        {"name": "觸口自然教育中心", "description": "阿里山入口的自然生態教育場所。", "address": "嘉義縣番路鄉"},
        {"name": "奮起湖老街", "description": "阿里山鐵路中站，便當文化聞名全台。", "address": "嘉義縣竹崎鄉奮起湖"},
        {"name": "太平老街", "description": "具有歷史風貌的山城小鎮老街。", "address": "嘉義縣大林鎮"},
        {"name": "達邦部落（鄒族）", "description": "鄒族原住民聚落，戰祭文化特色。", "address": "嘉義縣阿里山鄉達邦村"},
        {"name": "嘉義市立博物館", "description": "展示嘉義地區歷史文化的綜合博物館。", "address": "嘉義市西區忠義路1號"},
        {"name": "嘉義舊監獄", "description": "日治時期遺留的監獄建築，已轉型文化景點。", "address": "嘉義市東區維新路140號"},
        {"name": "布袋好美里濕地", "description": "沿海濕地生態保護區，黑面琵鷺棲息地。", "address": "嘉義縣布袋鎮好美里"},
        {"name": "塗溝鰲鼓濕地", "description": "東亞最大海埔地生態保護區，候鳥天堂。", "address": "嘉義縣東石鄉鰲鼓濕地"},
        {"name": "民雄大士爺廟", "description": "全台最著名的鬼王廟，鬼月活動盛大。", "address": "嘉義縣民雄鄉中樂村三角仔"},
        {"name": "水上南靖糖廠", "description": "日治時期製糖廠遺址，園區保存良好。", "address": "嘉義縣水上鄉"},
    ],
    "屏東": [
        {"name": "墾丁國家公園", "description": "台灣第一座國家公園，珊瑚礁生態著稱。", "address": "屏東縣恆春鎮墾丁路"},
        {"name": "恆春老街", "description": "四季如夏的半島城市，古城牆完好保存。", "address": "屏東縣恆春鎮中山路"},
        {"name": "國立海洋生物博物館", "description": "台灣最大水族館，白鯨館特別吸睛。", "address": "屏東縣車城鄉後灣村後灣路2號"},
        {"name": "琉球嶼（小琉球）", "description": "珊瑚礁小島，浮潛與海龜共游體驗絕佳。", "address": "屏東縣琉球鄉"},
        {"name": "三地門鄉排灣族文化", "description": "排灣族原住民聚落，石板屋建築獨特。", "address": "屏東縣三地門鄉三地村"},
        {"name": "鵝鑾鼻燈塔", "description": "台灣最南端的燈塔，守護海峽過往船隻。", "address": "屏東縣恆春鎮燈塔路90號"},
        {"name": "霧台石板屋部落", "description": "魯凱族最美的傳統石板屋聚落。", "address": "屏東縣霧台鄉霧台村"},
        {"name": "東港三寶（黑鮪魚、油魚子、櫻花蝦）", "description": "東港漁港美食，黑鮪魚季吸引全台遊客。", "address": "屏東縣東港鎮"},
        {"name": "四重溪溫泉", "description": "台灣四大溫泉之一，清代就已開發。", "address": "屏東縣車城鄉溫泉村"},
        {"name": "大鵬灣國家風景區", "description": "台灣最大封閉性潟湖，水上活動豐富。", "address": "屏東縣東港鎮大鵬灣"},
        {"name": "屏東市夜市", "description": "屏東市區最熱鬧的夜市，小吃多元豐富。", "address": "屏東市廣東路"},
        {"name": "旭海草原", "description": "台東屏東交界的原始草原，景色壯闊。", "address": "屏東縣牡丹鄉旭海村"},
        {"name": "萬年溪親水公園", "description": "屏東市區親水步道，生態豐富宜人。", "address": "屏東市萬年溪"},
        {"name": "高士部落（排灣族）", "description": "傳統排灣族聚落，文化保存良好。", "address": "屏東縣牡丹鄉高士村"},
        {"name": "里德橋", "description": "屏東縣老舊吊橋，兩側竹林景色優美。", "address": "屏東縣春日鄉士文村"},
    ],
    "宜蘭": [
        {"name": "太平山國家森林遊樂區", "description": "台灣原始森林保護區，檜木林與翠峰湖著稱。", "address": "宜蘭縣大同鄉太平山"},
        {"name": "羅東夜市", "description": "宜蘭最著名的夜市，羊肉爐與糕渣為必吃。", "address": "宜蘭縣羅東鎮中正北路"},
        {"name": "礁溪溫泉", "description": "台灣平地溫泉，交通便捷，泡湯文化盛行。", "address": "宜蘭縣礁溪鄉礁溪路"},
        {"name": "冬山河親水公園", "description": "宜蘭地標性公園，每年世界童玩節於此舉辦。", "address": "宜蘭縣冬山鄉冬山路150巷"},
        {"name": "蘇澳冷泉", "description": "全台罕見的碳酸冷泉，泡湯體驗特殊。", "address": "宜蘭縣蘇澳鎮冷泉路"},
        {"name": "龜山島", "description": "宜蘭外海的火山島，登島賞鯨豚活動熱門。", "address": "宜蘭縣頭城鎮龜山島"},
        {"name": "宜蘭設治紀念館", "description": "日治時期廳長宿舍，宜蘭歷史展示。", "address": "宜蘭市林森路2號"},
        {"name": "頭城老街", "description": "宜蘭第一街，清代商業文化保存良好。", "address": "宜蘭縣頭城鎮和平街"},
        {"name": "傳藝中心（國立傳統藝術中心）", "description": "全台最完整的傳統藝術文化主題園區。", "address": "宜蘭縣五結鄉五濱路二段201號"},
        {"name": "三星蔥蒜產區", "description": "台灣三星蔥故鄉，農業體驗人氣旺。", "address": "宜蘭縣三星鄉"},
        {"name": "噶瑪蘭族文化館", "description": "噶瑪蘭族平埔原住民文化保存地。", "address": "宜蘭縣壯圍鄉"},
        {"name": "員山生態園區", "description": "台灣最大的蝴蝶保育與生態展示園區。", "address": "宜蘭縣員山鄉惠深路"},
        {"name": "棲蘭森林遊樂區", "description": "千年神木群，馬告神木園保存最完整。", "address": "宜蘭縣大同鄉棲蘭村"},
        {"name": "南方澳漁港", "description": "台灣三大漁港之一，鯖魚料理聞名。", "address": "宜蘭縣蘇澳鎮南正里"},
        {"name": "蘭陽博物館", "description": "以宜蘭地質地形為建築意象，館藏豐富。", "address": "宜蘭縣頭城鎮青雲路三段750號"},
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
        {"name": "秀姑巒溪泛舟", "description": "台灣最著名的激流泛舟路線，驚險刺激。", "address": "花蓮縣瑞穗鄉泛舟起點"},
        {"name": "花蓮港", "description": "東部最大港口，港邊夜景與海鮮料理聞名。", "address": "花蓮市海濱路"},
        {"name": "遠雄海洋公園", "description": "台灣東部最大的海洋主題樂園。", "address": "花蓮縣壽豐鄉鹽寮村福德180號"},
        {"name": "光復糖廠", "description": "東台灣糖廠遺址，冰品遠近馳名。", "address": "花蓮縣光復鄉糖廠街19號"},
        {"name": "阿美族民俗中心", "description": "阿美族文化保存與展示中心。", "address": "花蓮縣吉安鄉南濱路一段"},
    ],
    "台東": [
        {"name": "知本溫泉", "description": "台東最著名的溫泉區，水質優良適合泡湯。", "address": "台東縣卑南鄉知本溫泉路"},
        {"name": "三仙台", "description": "珊瑚礁小島，跨海步橋景色壯觀。", "address": "台東縣成功鎮三仙台路"},
        {"name": "台東森林公園", "description": "台東市近郊最大的生態公園，琵琶湖美景。", "address": "台東市中興路四段"},
        {"name": "蘭嶼島（達悟族）", "description": "太平洋黑潮中的火山島，飛魚文化獨特。", "address": "台東縣蘭嶼鄉"},
        {"name": "綠島", "description": "珊瑚礁生態豐富，朝日溫泉為世界奇景。", "address": "台東縣綠島鄉"},
        {"name": "池上鄉稻田", "description": "台灣最美稻田景觀，伯朗大道秋收金黃。", "address": "台東縣池上鄉伯朗大道"},
        {"name": "都蘭部落（阿美族）", "description": "阿美族部落藝術聚落，創意文化著稱。", "address": "台東縣東河鄉都蘭村"},
        {"name": "台東卑南文化公園", "description": "台灣史前最大聚落遺址，史前博物館相鄰。", "address": "台東市康樂路一段300號"},
        {"name": "鹿野高台熱氣球", "description": "台灣熱氣球飛行聚地，每年夏季嘉年華。", "address": "台東縣鹿野鄉高台"},
        {"name": "小野柳地質公園", "description": "海蝕平台及奇岩怪石，台東版野柳。", "address": "台東市志航路一段"},
        {"name": "成功漁港", "description": "台東著名漁港，旗魚生魚片聞名全台。", "address": "台東縣成功鎮成功港"},
        {"name": "利吉月世界", "description": "惡地地形景觀，如月球表面般奇特壯觀。", "address": "台東縣卑南鄉利吉村"},
        {"name": "多良車站", "description": "台灣最美麗的廢棄車站，面向太平洋。", "address": "台東縣太麻里鄉多良村"},
        {"name": "關山親水公園", "description": "縱谷最美的環鎮自行車道，農田景觀優美。", "address": "台東縣關山鎮關山親水公園"},
        {"name": "太麻里金針山", "description": "每年夏秋的金針花海，山頂視野遼闊。", "address": "台東縣太麻里鄉金針山"},
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
        One of 台北、新北、桃園、台中、台南、高雄、基隆、新竹、苗栗、彰化、
        南投、雲林、嘉義、屏東、宜蘭、花蓮、台東.
    headless : bool
        Whether to launch Chromium in headless mode (default ``True``).
    max_items : int
        Maximum number of attractions to return (default ``15``).
    """

    def __init__(self, city: str, headless: bool = True, max_items: int = 15):
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

