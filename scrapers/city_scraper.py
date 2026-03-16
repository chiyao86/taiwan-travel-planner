"""CityScraper – scrapes attraction data from Taiwan city tourism portals.

Supported cities and their official tourism URLs:
    台北  → https://www.travel.taipei/
    台中  → https://travel.taichung.gov.tw/
    台南  → https://www.tainan.com.tw/
    高雄  → https://khh.travel/
    花蓮  → https://tour.hl.gov.tw/
"""
import asyncio
import logging
import random
from typing import Any

from playwright.async_api import async_playwright, Page

try:
    from playwright_stealth import stealth_async
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False

from .base_scraper import BaseScraper, Attraction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-city configuration: URL + CSS selectors (best-effort selectors that
# target stable landmark elements on each site; graceful fallback on failure)
# ---------------------------------------------------------------------------
CITY_CONFIG: dict[str, dict] = {
    "台北": {
        "url": "https://www.travel.taipei/zh-tw/attraction/lists/page/1",
        "extra_pages": [
            "https://www.travel.taipei/zh-tw/attraction/lists/page/2",
            "https://www.travel.taipei/zh-tw/attraction/lists/page/3",
        ],
        "card_selector": "li.list-card-item",
        "name_selector": "h3.card-title",
        "desc_selector": "p.card-text",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "台中": {
        "url": "https://travel.taichung.gov.tw/zh-tw/Attractions/List",
        "extra_pages": [
            "https://travel.taichung.gov.tw/zh-tw/Attractions/List?page=2",
        ],
        "card_selector": "div.list-wrap ul li",
        "name_selector": "h3",
        "desc_selector": "p",
        "addr_selector": "span.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "台南": {
        "url": "https://www.tainan.com.tw/tainan/scenery.asp",
        "extra_pages": [],
        "card_selector": "div.item",
        "name_selector": "div.item-title",
        "desc_selector": "div.item-desc",
        "addr_selector": "div.item-addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "高雄": {
        "url": "https://khh.travel/zh-tw/Attractions/List",
        "extra_pages": [
            "https://khh.travel/zh-tw/Attractions/List?page=2",
        ],
        "card_selector": "li.attraction-item",
        "name_selector": "h3",
        "desc_selector": "p.desc",
        "addr_selector": "p.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "花蓮": {
        "url": "https://tour.hl.gov.tw/zh-tw/Attractions/Index",
        "extra_pages": [
            "https://tour.hl.gov.tw/zh-tw/Attractions/Index?page=2",
        ],
        "card_selector": "div.scenic-item",
        "name_selector": "h3.scenic-name",
        "desc_selector": "p.scenic-desc",
        "addr_selector": "span.scenic-addr",
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
        {"name": "北投溫泉", "description": "溫泉博物館與特色湯屋，市區泡湯首選。", "address": "台北市北投區中山路"},
        {"name": "台北植物園", "description": "市區內的自然生態寶庫，荷花池四季美麗。", "address": "台北市中正區南海路53號"},
        {"name": "華山1914文創園區", "description": "舊酒廠轉型的文創聚落，展覽活動豐富。", "address": "台北市中正區八德路一段1號"},
        {"name": "松山文創園區", "description": "日式老菸廠改造，文創品牌與設計展覽聚集。", "address": "台北市信義區光復南路133號"},
        {"name": "迪化街", "description": "百年老街，年貨大街與中藥布莊林立。", "address": "台北市大同區迪化街一段"},
        {"name": "貓空纜車", "description": "俯瞰台北盆地的空中纜車，終點站有茶園餐廳。", "address": "台北市文山區指南路三段38巷33號"},
        {"name": "象山步道", "description": "台北最受歡迎的城市健行步道，可俯瞰101夜景。", "address": "台北市信義區信義路五段150巷"},
        {"name": "台北市立美術館", "description": "台灣最重要的現代藝術館，展覽多元精彩。", "address": "台北市中山區中山北路三段181號"},
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
        {"name": "大坑風景區", "description": "台中近郊登山健行聖地，步道難易程度分明。", "address": "台中市北屯區大坑"},
        {"name": "台中文學館", "description": "前台中市役所改建，展覽台中文學發展史。", "address": "台中市西區樂群街38號"},
        {"name": "審計新村", "description": "舊宿舍活化為文創市集，假日人潮絡繹不絕。", "address": "台中市西區民生路368巷"},
        {"name": "大甲鎮瀾宮", "description": "全台最負盛名的媽祖廟，每年進香遶境盛況空前。", "address": "台中市大甲區順天路158號"},
        {"name": "后豐鐵馬道", "description": "廢棄鐵路改建的自行車道，穿越峽谷橋梁景色壯觀。", "address": "台中市豐原區后豐鐵馬道"},
        {"name": "霧峰林家花園", "description": "台灣保存最完整的傳統漢式宅第，清代建築精華。", "address": "台中市霧峰區民生路42號"},
        {"name": "中台灣農業博覽會", "description": "台中大型農業主題展覽，四季皆有主題花卉展出。", "address": "台中市后里區"},
        {"name": "台中港", "description": "台灣第二大港，港區觀光購物中心及海鮮市場。", "address": "台中市梧棲區台中港"},
        {"name": "台中州廳", "description": "日治時代巴洛克建築，台中地標性歷史建物。", "address": "台中市西區民權路99號"},
        {"name": "第二市場", "description": "百年傳統市場，台中最道地的早餐美食聚集。", "address": "台中市中區三民路二段87號"},
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
        {"name": "林百貨", "description": "日治時代歷史建築，現為文創選物店。", "address": "台南市中西區忠義路二段63號"},
        {"name": "台南市美術館", "description": "府城最重要的當代美術展覽空間，建築設計別具一格。", "address": "台南市中西區南門路37號"},
        {"name": "鄭成功文物館", "description": "記錄鄭成功開台史蹟的專題展覽館。", "address": "台南市中西區開山路152號"},
        {"name": "烏山頭水庫", "description": "嘉南大圳的樞紐，珊瑚潭湖光如詩如畫。", "address": "台南市官田區嘉南里67號"},
        {"name": "南鯤鯓代天府", "description": "全台規模最大的王爺廟，香火鼎盛。", "address": "台南市北門區鯤江里976號"},
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
        {"name": "高雄港", "description": "台灣最大國際商港，港景夜色壯觀。", "address": "高雄市鹽埕區北斗街1號"},
        {"name": "春天藝術節", "description": "高雄年度最大戶外藝術節，在衛武營舉辦。", "address": "高雄市鳳山區樹德里"},
        {"name": "衛武營國家藝術文化中心", "description": "全球最大管風琴所在地，世界級演藝廳。", "address": "高雄市鳳山區三多一路1號"},
        {"name": "壽山國家自然公園", "description": "市區內的自然森林，台灣獼猴棲地。", "address": "高雄市鼓山區壽山路"},
        {"name": "光榮碼頭", "description": "高雄新灣岸圈的核心，觀光遊艇與夜市聚集。", "address": "高雄市苓雅區新光路1號"},
        {"name": "左營眷村文化園區", "description": "海軍眷村活化，眷村文化保存完整。", "address": "高雄市左營區龜山里"},
        {"name": "大東文化藝術中心", "description": "鳳山最重要的文化展演空間，建築設計前衛。", "address": "高雄市鳳山區光遠路161號"},
        {"name": "橋頭糖廠", "description": "台灣第一座現代化糖廠，日式宿舍群保存良好。", "address": "高雄市橋頭區糖廠路24號"},
        {"name": "高雄市立歷史博物館", "description": "高雄在地歷史文物典藏，日治市役所古蹟。", "address": "高雄市鹽埕區中正四路272號"},
        {"name": "鳳儀書院", "description": "鳳山最古老的文教場所，清代書院修復展覽。", "address": "高雄市鳳山區鳳明街62號"},
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
        {"name": "砂卡礑步道", "description": "太魯閣內著名溪谷步道，碧藍溪水令人驚艷。", "address": "花蓮縣秀林鄉富世村"},
        {"name": "布洛灣台地", "description": "太魯閣峽谷中的原住民文化展示區。", "address": "花蓮縣秀林鄉"},
        {"name": "花蓮吉安慶豐夜市", "description": "在地人最愛的夜市，台灣小吃與原住民料理兼備。", "address": "花蓮縣吉安鄉"},
        {"name": "玉里神社", "description": "日治時期保存最完整的神社遺址之一。", "address": "花蓮縣玉里鎮中山路三段"},
        {"name": "光復糖廠", "description": "日治製糖廠，冰品馳名，蒸汽火車可乘坐。", "address": "花蓮縣光復鄉大進村糖廠街19號"},
        {"name": "花蓮海洋公園", "description": "海洋主題樂園，海豚表演與水上活動豐富。", "address": "花蓮縣壽豐鄉鹽寮村鹽寮43-1號"},
        {"name": "賞鯨豚", "description": "花蓮外海鯨豚種類豐富，全年皆有賞鯨行程。", "address": "花蓮縣花蓮市花蓮港"},
        {"name": "翡翠谷", "description": "太魯閣溪谷絕景，碧綠潭水與大理石地形交輝。", "address": "花蓮縣秀林鄉天祥路"},
        {"name": "林田山林業文化園區", "description": "伐木業歷史保存，日式木造建築群完整呈現。", "address": "花蓮縣鳳林鎮森榮里林森路"},
        {"name": "奇萊山", "description": "台灣百岳之一，以霧氣神秘著稱。", "address": "花蓮縣秀林鄉"},
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
        One of 台北、台中、台南、高雄、花蓮.
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
        """Launch browser and scrape the target page(s)."""
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

            urls_to_scrape = [config["url"]] + config.get("extra_pages", [])

            try:
                for url in urls_to_scrape:
                    if len(attractions) >= self.max_items:
                        break
                    try:
                        await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                        await self.random_delay(2.0, 4.0)
                        await self._human_scroll(page)
                        await self.random_delay(1.0, 2.0)

                        cards = await page.query_selector_all(config["card_selector"])
                        remaining = self.max_items - len(attractions)
                        for card in cards[:remaining]:
                            attraction = await self._parse_card(page, card, config)
                            if attraction:
                                attractions.append(attraction)
                    except Exception as exc:
                        logger.debug("Failed to scrape page %s: %s", url, exc)
                        continue
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
        except Exception as exc:
            logger.debug("Failed to parse attraction card: %s", exc)
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

