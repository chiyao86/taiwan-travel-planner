"""CityScraper – scrapes attraction data from Taiwan city tourism portals.

Supported cities and their official tourism URLs:
    台北  → https://www.travel.taipei/
    台中  → https://travel.taichung.gov.tw/
    台南  → https://www.tainan.com.tw/
    高雄  → https://khh.travel/
    花蓮  → https://tour.hl.gov.tw/
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
        "url": "https://www.travel.taipei/zh-tw/attraction/lists/page/1",
        "card_selector": "li.list-card-item",
        "name_selector": "h3.card-title",
        "desc_selector": "p.card-text",
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
    "台南": {
        "url": "https://www.tainan.com.tw/tainan/scenery.asp",
        "card_selector": "div.item",
        "name_selector": "div.item-title",
        "desc_selector": "div.item-desc",
        "addr_selector": "div.item-addr",
        "img_selector": "img",
        "link_selector": "a",
    },
    "高雄": {
        "url": "https://khh.travel/zh-tw/Attractions/List",
        "card_selector": "li.attraction-item",
        "name_selector": "h3",
        "desc_selector": "p.desc",
        "addr_selector": "p.address",
        "img_selector": "img",
        "link_selector": "a",
    },
    "花蓮": {
        "url": "https://tour.hl.gov.tw/zh-tw/Attractions/Index",
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

