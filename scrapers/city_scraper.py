"""CityScraper – scrapes attraction data from Taiwan city tourism portals.

Supported cities and their official tourism URLs:
    台北  → https://www.travel.taipei/
    新北  → https://newtaipei.travel/
    桃園  → https://travel.tycg.gov.tw/
    台中  → https://travel.taichung.gov.tw/
    基隆  → https://travel.klcg.gov.tw/
    新竹  → https://tourism.hccg.gov.tw/
    苗栗  → https://miaolitravel.net/
    彰化  → https://tourism.chcg.gov.tw/
    南投  → https://travel.nantou.gov.tw/
    雲林  → https://tour.yunlin.gov.tw/
    嘉義  → https://travel.chiayi.gov.tw/
    台南  → https://www.twtainan.net/
    高雄  → https://khh.travel/
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
        "card_selector": "div.tour-item",
        "name_selector": "h3",
        "desc_selector": "p.desc",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "桃園": {
        "url": "https://travel.tycg.gov.tw/zh-tw/travel/tourlist",
        "card_selector": "div.item-block",
        "name_selector": "h3",
        "desc_selector": "p",
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
        "card_selector": "div.scenic-item, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "新竹": {
        "url": "https://tourism.hccg.gov.tw/chtravel/app/travel/list?id=37",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "苗栗": {
        "url": "https://miaolitravel.net/article.aspx?sno=03004313",
        "card_selector": "div.item-block, li.list-item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "彰化": {
        "url": "https://tourism.chcg.gov.tw/Attractions.aspx",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "南投": {
        "url": "https://travel.nantou.gov.tw/attractions/",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "雲林": {
        "url": "https://tour.yunlin.gov.tw/mainssl/modules/MySpace/BlogList.php?sn=yunlin&cn=ZC10350618",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "嘉義": {
        "url": "https://travel.chiayi.gov.tw/TravelInformation/C000005/1",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "台南": {
        "url": "https://www.twtainan.net/zh-tw/attractions/",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "高雄": {
        "url": "https://khh.travel/zh-tw/attractions/list/",
        "card_selector": "li.attraction-item, div.item-block",
        "name_selector": "h3",
        "desc_selector": "p.desc, p",
        "addr_selector": "p.address, span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "屏東": {
        "url": "https://pingtung.easytravel.com.tw/scenic/",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "宜蘭": {
        "url": "https://www.taiwan.net.tw/m1.aspx?sNo=0000064&keyString=%e5%ae%9c%e8%98%ad%5e%5e%5e%5e0",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "花蓮": {
        "url": "https://tour-hualien.hl.gov.tw/TourList.aspx?n=109&sms=12302",
        "card_selector": "div.scenic-item, li.item",
        "name_selector": "h3.scenic-name, h3, .title",
        "desc_selector": "p.scenic-desc, p, .desc",
        "addr_selector": "span.scenic-addr, span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "台東": {
        "url": "https://tour.taitung.gov.tw/zh-tw/attraction",
        "card_selector": "div.item-block, li.item",
        "name_selector": "h3, .title",
        "desc_selector": "p, .desc",
        "addr_selector": "span.address, .addr",
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
        {"name": "九份老街", "description": "山城老街，充滿懷舊氣息，電影《悲情城市》取景地。", "address": "新北市瑞芳區九份"},
        {"name": "淡水老街", "description": "百年歷史老街，阿給與魚丸湯是必嚐美食。", "address": "新北市淡水區中正路"},
        {"name": "十分瀑布", "description": "台灣最寬瀑布，有「台灣尼加拉」之稱。", "address": "新北市平溪區十分里"},
        {"name": "平溪天燈", "description": "每年元宵節舉辦的天燈節，是全球知名的祈福儀式。", "address": "新北市平溪區"},
        {"name": "烏來溫泉", "description": "台北近郊最著名的溫泉區，碳酸氫鈉泉質優良。", "address": "新北市烏來區"},
        {"name": "野柳地質公園", "description": "奇特岩石地貌，女王頭是最著名的地標。", "address": "新北市萬里區野柳里167-1號"},
        {"name": "三峽老街", "description": "保存完整的清代紅磚老街，三角湧文化協進會見證歷史。", "address": "新北市三峽區民權街"},
        {"name": "金瓜石黃金博物館", "description": "日治時代採金遺址改建，展示黃金採礦歷史。", "address": "新北市瑞芳區金瓜石金光路8號"},
        {"name": "鶯歌陶瓷老街", "description": "台灣陶瓷重鎮，老街上窯燒作品琳瑯滿目。", "address": "新北市鶯歌區文化路"},
        {"name": "福隆海水浴場", "description": "東北角最著名的沙灘，每年舉辦福隆國際沙雕藝術季。", "address": "新北市貢寮區福隆里"},
    ],
    "桃園": [
        {"name": "桃園大溪老街", "description": "保存完整的巴洛克式建築老街，豆干聞名全台。", "address": "桃園市大溪區和平路"},
        {"name": "慈湖", "description": "蔣中正陵寢所在地，湖光山色如詩如畫。", "address": "桃園市大溪區埔頂路一段"},
        {"name": "角板山行館", "description": "日治時期遺留的山地行館，俯瞰大漢溪河谷。", "address": "桃園市復興區中正路"},
        {"name": "小烏來天空步道", "description": "懸掛於峽谷上的透明玻璃步道，景色壯觀。", "address": "桃園市復興區"},
        {"name": "拉拉山自然保護區", "description": "台灣最大的檜木保護區，千年神木林立。", "address": "桃園市復興區華陵里"},
        {"name": "石門水庫", "description": "台灣最大水庫之一，大壩工程宏偉壯觀。", "address": "桃園市龍潭區石門"},
        {"name": "八德埤塘生態公園", "description": "埤塘生態豐富，自行車道環繞，適合悠閒漫遊。", "address": "桃園市八德區"},
        {"name": "桃園蓮花季", "description": "每年夏季舉辦的蓮花季，百種蓮花齊放。", "address": "桃園市觀音區"},
        {"name": "龍潭大池", "description": "龍潭最具代表性的人工湖，環湖步道迷人。", "address": "桃園市龍潭區龍潭里"},
        {"name": "虎頭山環保公園", "description": "市區內的森林公園，提供市民休憩好去處。", "address": "桃園市桃園區虎頭山"},
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
        {"name": "基隆廟口夜市", "description": "台灣最著名的夜市之一，海鮮小吃聞名全台。", "address": "基隆市仁愛區愛三路"},
        {"name": "基隆嶼", "description": "基隆外海的小島，可搭船登島，海景絕佳。", "address": "基隆市中正區基隆嶼"},
        {"name": "和平島地質公園", "description": "豆腐岩、蕈狀岩等奇特地質地貌景觀。", "address": "基隆市中正區平一路360號"},
        {"name": "正濱漁港彩色屋", "description": "繽紛彩色建築倒映在漁港水面，是IG熱門打卡點。", "address": "基隆市中正區正濱路"},
        {"name": "仙洞巖", "description": "天然海蝕洞穴，供奉神佛，岩洞幽深神秘。", "address": "基隆市中山區仙洞里"},
        {"name": "碧砂漁港", "description": "基隆最大漁港，漁獲新鮮，海鮮餐廳林立。", "address": "基隆市中正區碧砂漁港"},
        {"name": "二沙灣砲台", "description": "清代海防砲台遺址，俯瞰基隆港。", "address": "基隆市中正區壽山路"},
        {"name": "八斗子漁港", "description": "傍晚看夕陽、觀看漁船返航，景色宜人。", "address": "基隆市中正區八斗子"},
        {"name": "海科館", "description": "國立海洋科技博物館，以海洋科學為主題。", "address": "基隆市中正區北寧路367號"},
        {"name": "外木山海岸", "description": "基隆北側的海岸線，景色壯闊，適合散步。", "address": "基隆市安樂區外木山"},
    ],
    "新竹": [
        {"name": "新竹城隍廟", "description": "台灣最靈驗的城隍廟之一，廟前小吃舉世聞名。", "address": "新竹市北區中山路75號"},
        {"name": "新竹動物園", "description": "台灣現存最古老的動物園，建於日治時代。", "address": "新竹市東區動物園路"},
        {"name": "十七公里海岸線", "description": "新竹沿海風景線，風車海景令人心曠神怡。", "address": "新竹市香山區"},
        {"name": "新竹玻璃工藝博物館", "description": "展示新竹玻璃工藝發展史與精品創作。", "address": "新竹市東區東大路一段2號"},
        {"name": "新竹孔廟", "description": "建於清代的孔廟，為新竹市定古蹟。", "address": "新竹市北區學府路路底"},
        {"name": "內灣老街", "description": "山城小鎮，野薑花粽是必吃特產。", "address": "新竹縣橫山鄉內灣村"},
        {"name": "北埔老街", "description": "客家文化保存地，擂茶體驗是一大特色。", "address": "新竹縣北埔鄉廟前路"},
        {"name": "清華大學", "description": "台灣頂尖學府，梅園與人工湖景色優美。", "address": "新竹市東區光復路二段101號"},
        {"name": "新埔柿餅", "description": "全台最大柿餅產地，秋季橙色柿田美不勝收。", "address": "新竹縣新埔鎮"},
        {"name": "尖石原鄉", "description": "泰雅族原住民文化保存地，山岳景色壯麗。", "address": "新竹縣尖石鄉"},
    ],
    "苗栗": [
        {"name": "三義木雕街", "description": "台灣木雕重鎮，街道上雕刻藝品琳瑯滿目。", "address": "苗栗縣三義鄉水美街"},
        {"name": "勝興車站", "description": "台灣最高的鐵路車站，舊山線遺址充滿懷舊氣息。", "address": "苗栗縣三義鄉勝興村"},
        {"name": "龍騰斷橋", "description": "日治時代鐵橋遺跡，百年斷橋在大地震後成觀光景點。", "address": "苗栗縣三義鄉龍騰村"},
        {"name": "南庄老街", "description": "客家山城老街，賽夏族文化與自然景觀兼備。", "address": "苗栗縣南庄鄉東村"},
        {"name": "向天湖", "description": "賽夏族聖地，湖光山色如詩如畫。", "address": "苗栗縣南庄鄉向天湖"},
        {"name": "雪霸國家公園", "description": "高山冰河地貌，雪山是台灣第二高峰。", "address": "苗栗縣泰安鄉"},
        {"name": "泰安溫泉", "description": "台灣最純淨的碳酸氫鈉溫泉，美人湯稱譽已久。", "address": "苗栗縣泰安鄉錦水村"},
        {"name": "貓狸山公園", "description": "苗栗市區的都市森林，城隍廟祭典熱鬧非凡。", "address": "苗栗縣苗栗市"},
        {"name": "通霄神社", "description": "日治時代神社遺址，登高可俯瞰通霄市區。", "address": "苗栗縣通霄鎮虎頭山"},
        {"name": "苑裡藺草文化館", "description": "展示苑裡帽蓆編織技藝，藺草工藝為國家文化資產。", "address": "苗栗縣苑裡鎮山腳里磁磚路99號"},
    ],
    "彰化": [
        {"name": "彰化八卦山大佛", "description": "台灣最著名的大佛之一，高11.5公尺，可俯瞰彰化平原。", "address": "彰化縣彰化市八卦山"},
        {"name": "鹿港老街", "description": "保存最完整的清代街道，台灣傳統建築典範。", "address": "彰化縣鹿港鎮中山路"},
        {"name": "鹿港龍山寺", "description": "台灣保存最完整的古廟之一，清代建築精華。", "address": "彰化縣鹿港鎮金門街81號"},
        {"name": "溪湖糖廠", "description": "全台唯一仍在運轉的糖廠，五分車冰棒超人氣。", "address": "彰化縣溪湖鎮彰水路二段1號"},
        {"name": "田中蜈蚣陣", "description": "台灣傳統民俗活動，百腳蜈蚣陣威武壯觀。", "address": "彰化縣田中鎮"},
        {"name": "彰化扇形車庫", "description": "全台唯一扇形機關車庫，台鐵歷史文物珍貴。", "address": "彰化縣彰化市彰美路一段1號"},
        {"name": "花壇白沙坑燈節", "description": "彰化元宵燈節盛典，遶境文武百陣傳承百年。", "address": "彰化縣花壇鄉"},
        {"name": "二林葡萄", "description": "台灣葡萄主產地，夏季可至果園採果體驗。", "address": "彰化縣二林鎮"},
        {"name": "王功漁港", "description": "彰化著名漁港，夕陽與蚵仔是兩大特色。", "address": "彰化縣芳苑鄉王功村"},
        {"name": "大村葡萄觀光農園", "description": "葡萄觀光果園群聚，採果體驗最受遊客歡迎。", "address": "彰化縣大村鄉"},
    ],
    "南投": [
        {"name": "日月潭", "description": "台灣最著名的高山湖泊，湖光山色如詩如畫。", "address": "南投縣魚池鄉水社村"},
        {"name": "清境農場", "description": "高山牧場，歐洲風情建築，青青草原壯觀。", "address": "南投縣仁愛鄉定遠新村"},
        {"name": "奧萬大國家森林遊樂區", "description": "台灣楓葉最美景點，秋季楓紅如火如荼。", "address": "南投縣仁愛鄉萬豐村"},
        {"name": "溪頭自然教育園區", "description": "國立台灣大學實驗林，神木、竹林景觀迷人。", "address": "南投縣鹿谷鄉森林路"},
        {"name": "集集小鎮", "description": "台灣最迷人的小火車之鄉，綠色隧道最著名。", "address": "南投縣集集鎮民生路"},
        {"name": "埔里酒廠", "description": "台灣酒廠重鎮，紹興酒與米酒聞名全台。", "address": "南投縣埔里鎮中山路三段219號"},
        {"name": "霧社事件紀念公園", "description": "1930年原住民抗日史跡，賽德克族精神象徵。", "address": "南投縣仁愛鄉霧社"},
        {"name": "惠蓀林場", "description": "中興大學實驗林場，森林浴與河谷景色絕佳。", "address": "南投縣仁愛鄉萬豐村"},
        {"name": "玉山國家公園", "description": "台灣最高峰，海拔3952公尺，東北亞第一高峰。", "address": "南投縣信義鄉"},
        {"name": "竹山天梯", "description": "全台最長的天空步道，懸掛於百公尺深谷上。", "address": "南投縣竹山鎮"},
    ],
    "雲林": [
        {"name": "劍湖山世界", "description": "雲林最著名的主題樂園，刺激遊樂設施吸引全家。", "address": "雲林縣古坑鄉中正路1號"},
        {"name": "北港朝天宮", "description": "全台香火最旺的媽祖廟之一，進香盛況空前。", "address": "雲林縣北港鎮中山路178號"},
        {"name": "古坑咖啡", "description": "台灣本土咖啡發源地，咖啡農場觀光體驗豐富。", "address": "雲林縣古坑鄉"},
        {"name": "虎尾糖廠", "description": "日治時期糖廠遺址，糖業文化保存完整。", "address": "雲林縣虎尾鎮民主路95號"},
        {"name": "斗六太平老街", "description": "雲林縣城老街，日治時期巴洛克建築群保存完整。", "address": "雲林縣斗六市太平路"},
        {"name": "草嶺石壁風景區", "description": "雲林最著名的高山風景區，奇岩地貌壯觀。", "address": "雲林縣古坑鄉草嶺村"},
        {"name": "西螺大橋", "description": "竣工時為東亞最長橋樑，跨越濁水溪連接二縣。", "address": "雲林縣西螺鎮"},
        {"name": "口湖牛挑灣濕地", "description": "海岸濕地，黑面琵鷺等候鳥棲息勝地。", "address": "雲林縣口湖鄉"},
        {"name": "麥寮六輕石化區", "description": "台灣最大工業區，可參觀工廠內部管線奇景。", "address": "雲林縣麥寮鄉"},
        {"name": "二崙農村生活館", "description": "展示雲林農村傳統生活文化，稻草藝術節有名。", "address": "雲林縣二崙鄉"},
    ],
    "嘉義": [
        {"name": "阿里山國家森林遊樂區", "description": "台灣最著名的高山景區，雲海、日出、神木三大奇景。", "address": "嘉義縣阿里山鄉"},
        {"name": "嘉義市文化路夜市", "description": "嘉義最熱鬧的夜市，雞肉飯為必嚐美食。", "address": "嘉義市東區文化路"},
        {"name": "奮起湖", "description": "阿里山鐵路中途站，老街與便當聞名全台。", "address": "嘉義縣竹崎鄉中和村"},
        {"name": "嘉義公園", "description": "嘉義市歷史最悠久的公園，孔廟與射日塔並列其中。", "address": "嘉義市東區公園街"},
        {"name": "布袋好美里濕地", "description": "候鳥棲息的重要濕地，生態多樣豐富。", "address": "嘉義縣布袋鎮好美里"},
        {"name": "達娜伊谷生態公園", "description": "鄒族部落的生態保育聖地，溪流魚類豐富。", "address": "嘉義縣阿里山鄉山美村"},
        {"name": "故宮南院", "description": "故宮博物院嘉義分院，展示亞洲文物與藝術。", "address": "嘉義縣太保市故宮大道888號"},
        {"name": "東石漁港", "description": "嘉義著名漁港，蚵仔與海鮮料理聞名全台。", "address": "嘉義縣東石鄉"},
        {"name": "梅山太平老街", "description": "客家山城老街，梅子產品與茶葉是特色。", "address": "嘉義縣梅山鄉太平村"},
        {"name": "朴子配天宮", "description": "嘉義著名媽祖廟，每年進香活動熱鬧非凡。", "address": "嘉義縣朴子市開元路118號"},
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
    ],
    "屏東": [
        {"name": "墾丁國家公園", "description": "台灣最南端的國家公園，海灘、珊瑚礁、熱帶植物豐富。", "address": "屏東縣恆春鎮墾丁路"},
        {"name": "墾丁大街", "description": "台灣最熱鬧的觀光夜市，各式小吃與紀念品琳瑯滿目。", "address": "屏東縣恆春鎮墾丁路"},
        {"name": "國立海洋生物博物館", "description": "台灣規模最大的海洋博物館，館內設有海底隧道。", "address": "屏東縣車城鄉後灣村後灣路2號"},
        {"name": "琉球嶼（小琉球）", "description": "台灣唯一的珊瑚礁島，海龜與海洋生態豐富。", "address": "屏東縣琉球鄉"},
        {"name": "恆春古城", "description": "台灣保存最完整的四座城門，清代城牆完整呈現。", "address": "屏東縣恆春鎮"},
        {"name": "東港漁港", "description": "黑鮪魚的重要集散地，每年黑鮪魚文化觀光季盛況空前。", "address": "屏東縣東港鎮"},
        {"name": "霧台原鄉", "description": "魯凱族部落，石板屋建築與原住民藝術聞名。", "address": "屏東縣霧台鄉"},
        {"name": "三地門鄉", "description": "排灣族文化集散地，玻璃藝術與琉璃珠工藝聞名全台。", "address": "屏東縣三地門鄉"},
        {"name": "四重溪溫泉", "description": "台灣四大溫泉之一，碳酸氫鈉泉質優良。", "address": "屏東縣車城鄉溫泉村"},
        {"name": "佳樂水風景區", "description": "東部海岸奇特侵蝕地貌，礁岩海景壯觀。", "address": "屏東縣滿州鄉"},
    ],
    "宜蘭": [
        {"name": "太平山國家森林遊樂區", "description": "神木、霧林、翠峰湖是三大必遊景點。", "address": "宜蘭縣大同鄉"},
        {"name": "礁溪溫泉", "description": "距台北最近的溫泉鄉，碳酸氫鈉泉質優良。", "address": "宜蘭縣礁溪鄉"},
        {"name": "羅東夜市", "description": "宜蘭最著名的夜市，蒜味肉羹等小吃遠近馳名。", "address": "宜蘭縣羅東鎮公正路"},
        {"name": "冬山河親水公園", "description": "童玩節發源地，人工沙灘與水上設施豐富。", "address": "宜蘭縣五結鄉"},
        {"name": "蘇澳冷泉", "description": "全台唯一的碳酸冷泉，天然碳酸水堪稱奇蹟。", "address": "宜蘭縣蘇澳鎮冷泉路"},
        {"name": "龜山島", "description": "宜蘭海域的神秘島嶼，可搭船賞鯨及觀賞奇特地形。", "address": "宜蘭縣頭城鎮龜山島"},
        {"name": "宜蘭傳藝中心", "description": "台灣傳統藝術保存基地，傳統技藝表演精彩。", "address": "宜蘭縣五結鄉五濱路二段201號"},
        {"name": "棲蘭森林遊樂區", "description": "天然檜木保育聖地，萬歲神木展示台灣樹木之美。", "address": "宜蘭縣大同鄉"},
        {"name": "馬告生態公園", "description": "位於棲蘭山之中，有豐富的動植物生態景觀。", "address": "宜蘭縣大同鄉"},
        {"name": "頭城搶孤", "description": "宜蘭最著名的傳統民俗活動，搶孤比賽驚心動魄。", "address": "宜蘭縣頭城鎮"},
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
        {"name": "知本溫泉", "description": "台東著名溫泉區，溫泉水質優良，景色秀麗。", "address": "台東縣卑南鄉溫泉村"},
        {"name": "小野柳地質奇景", "description": "台東北端奇特的海蝕地形，被稱為台東版野柳，奇岩巨石造型多變。", "address": "台東縣台東市富岡里"},
        {"name": "台東森林公園", "description": "琵琶湖與活水湖優美，單車道環繞湖光山色。", "address": "台東市博愛路"},
        {"name": "小野柳風景區", "description": "海蝕地貌奇特，豆腐岩與蕈狀岩為一大特色。", "address": "台東縣台東市富岡路"},
        {"name": "三仙台風景區", "description": "以八拱跨海步橋為地標，珊瑚礁海岸壯觀。", "address": "台東縣成功鎮三仙里基翬路74號"},
        {"name": "金樽漁港", "description": "台東著名漁港，海鮮新鮮，港灣風景如畫。", "address": "台東縣東河鄉金樽村"},
        {"name": "池上稻田", "description": "台灣最美麗的稻田景觀，金色稻浪震撼人心。", "address": "台東縣池上鄉"},
        {"name": "鹿野高台", "description": "台灣飛行傘聖地，每年熱氣球節吸引眾多遊客。", "address": "台東縣鹿野鄉永安村高台路"},
        {"name": "綠島", "description": "珊瑚礁生態豐富，潮間帶與夜光藻令人驚豔。", "address": "台東縣綠島鄉"},
        {"name": "蘭嶼", "description": "達悟族文化聖地，飛魚文化與特色拼板舟聞名。", "address": "台東縣蘭嶼鄉"},
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
        One of 台北、新北、桃園、台中、基隆、新竹、苗栗、彰化、南投、雲林、嘉義、台南、高雄、屏東、宜蘭、花蓮、台東.
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

