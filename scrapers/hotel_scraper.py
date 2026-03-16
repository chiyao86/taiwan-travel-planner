"""HotelScraper – scrapes hotel listings from Booking.com.

Employs multiple anti-bot measures:
* ``playwright-stealth`` to hide automation fingerprints
* Random User-Agent rotation
* Random scroll and mouse-move delays mimicking human behaviour
* Falls back to curated static hotel data when live scraping fails.
"""
import asyncio
import random
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
    "屏東": "Pingtung, Taiwan",
    "宜蘭": "Yilan, Taiwan",
    "花蓮": "Hualien, Taiwan",
    "台東": "Taitung, Taiwan",
    "高雄": "Kaohsiung, Taiwan",
}

# Fallback hotel data (used when live scraping is blocked / unavailable)
FALLBACK_HOTELS: dict[str, list[dict]] = {
    "台北": [
        {"name": "台北君悅大飯店", "price": "NT$ 6,800/晚起", "rating": "9.0", "address": "台北市信義區松壽路2號"},
        {"name": "W台北", "price": "NT$ 7,200/晚起", "rating": "9.2", "address": "台北市信義區忠孝東路五段10號"},
        {"name": "台北喜來登大飯店", "price": "NT$ 5,500/晚起", "rating": "8.8", "address": "台北市中正區忠孝東路一段12號"},
        {"name": "台北美侖大飯店", "price": "NT$ 3,800/晚起", "rating": "8.5", "address": "台北市中山區民族東路"},
        {"name": "西門町商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台北市萬華區西寧南路"},
    ],
    "新北": [
        {"name": "淡水福容大飯店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "新北市淡水區中正路257號"},
        {"name": "板橋凱撒大飯店", "price": "NT$ 4,200/晚起", "rating": "8.9", "address": "新北市板橋區縣民大道二段8號"},
        {"name": "烏來馥蘭朵溫泉度假酒店", "price": "NT$ 5,500/晚起", "rating": "9.1", "address": "新北市烏來區烏來街45號"},
        {"name": "九份山城旅棧", "price": "NT$ 2,200/晚起", "rating": "8.6", "address": "新北市瑞芳區輕便路"},
        {"name": "三重商務旅館", "price": "NT$ 1,500/晚起", "rating": "8.0", "address": "新北市三重區"},
    ],
    "桃園": [
        {"name": "桃園大溪威斯汀度假酒店", "price": "NT$ 6,500/晚起", "rating": "9.2", "address": "桃園市大溪區員林路一段"},
        {"name": "諾富特桃園機場飯店", "price": "NT$ 4,800/晚起", "rating": "8.8", "address": "桃園市大園區航站南路"},
        {"name": "桃園中正日航國際酒店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "桃園市中壢區中正路"},
        {"name": "石門水庫山林渡假樂園", "price": "NT$ 2,800/晚起", "rating": "8.3", "address": "桃園市龍潭區石門"},
        {"name": "平鎮商旅", "price": "NT$ 1,600/晚起", "rating": "7.9", "address": "桃園市平鎮區"},
    ],
    "台中": [
        {"name": "日月千禧酒店", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "台中市西屯區市政北一路"},
        {"name": "台中金典酒店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "台中市西區館前路"},
        {"name": "台中長榮桂冠酒店", "price": "NT$ 5,000/晚起", "rating": "8.9", "address": "台中市西屯區台灣大道二段"},
        {"name": "逢甲商旅", "price": "NT$ 1,600/晚起", "rating": "8.3", "address": "台中市西屯區逢甲路"},
    ],
    "基隆": [
        {"name": "基隆長榮桂冠酒店", "price": "NT$ 3,200/晚起", "rating": "8.8", "address": "基隆市中正區中正路"},
        {"name": "基隆港灣旅館", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "基隆市仁愛區忠一路"},
        {"name": "基隆商務飯店", "price": "NT$ 1,500/晚起", "rating": "7.8", "address": "基隆市信義區"},
        {"name": "海洋廣場旅館", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "基隆市中正區"},
    ],
    "新竹": [
        {"name": "新竹老爺大酒店", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "新竹市東區中華路二段188號"},
        {"name": "新竹喜來登大飯店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "新竹市東區中正路"},
        {"name": "竹湖山莊", "price": "NT$ 2,500/晚起", "rating": "8.4", "address": "新竹縣橫山鄉"},
        {"name": "尖石山之雲民宿", "price": "NT$ 2,800/晚起", "rating": "8.8", "address": "新竹縣尖石鄉"},
    ],
    "苗栗": [
        {"name": "苗栗泰安溫泉飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "苗栗縣泰安鄉錦水村"},
        {"name": "三義木雕民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "苗栗縣三義鄉"},
        {"name": "南庄老街客棧", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "苗栗縣南庄鄉"},
        {"name": "大湖草莓農場民宿", "price": "NT$ 2,200/晚起", "rating": "8.5", "address": "苗栗縣大湖鄉"},
    ],
    "彰化": [
        {"name": "彰化長榮飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "彰化市中山路二段"},
        {"name": "鹿港民宿老宅", "price": "NT$ 1,800/晚起", "rating": "8.7", "address": "彰化縣鹿港鎮"},
        {"name": "彰化商旅", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "彰化市中正路"},
        {"name": "王功漁港民宿", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "彰化縣芳苑鄉王功村"},
    ],
    "南投": [
        {"name": "日月潭涵碧樓", "price": "NT$ 12,000/晚起", "rating": "9.5", "address": "南投縣魚池鄉中山路142號"},
        {"name": "日月潭雲品溫泉酒店", "price": "NT$ 7,500/晚起", "rating": "9.2", "address": "南投縣魚池鄉中山路101號"},
        {"name": "清境農場觀山景觀民宿", "price": "NT$ 3,500/晚起", "rating": "8.8", "address": "南投縣仁愛鄉大同村"},
        {"name": "溪頭明山森林會館", "price": "NT$ 4,200/晚起", "rating": "8.6", "address": "南投縣鹿谷鄉內湖村"},
        {"name": "集集民宿", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "南投縣集集鎮"},
    ],
    "雲林": [
        {"name": "劍湖山王子大飯店", "price": "NT$ 3,200/晚起", "rating": "8.5", "address": "雲林縣古坑鄉棋盤村"},
        {"name": "北港民宿", "price": "NT$ 1,500/晚起", "rating": "7.9", "address": "雲林縣北港鎮"},
        {"name": "古坑咖啡民宿", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "雲林縣古坑鄉"},
        {"name": "斗六商旅", "price": "NT$ 1,600/晚起", "rating": "8.0", "address": "雲林縣斗六市"},
    ],
    "嘉義": [
        {"name": "阿里山賓館", "price": "NT$ 5,500/晚起", "rating": "8.9", "address": "嘉義縣阿里山鄉中正村"},
        {"name": "嘉義耐斯王子大飯店", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "嘉義市西區世賢路二段"},
        {"name": "嘉義商旅", "price": "NT$ 1,800/晚起", "rating": "8.1", "address": "嘉義市東區"},
        {"name": "故宮南院周邊民宿", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "嘉義縣太保市"},
    ],
    "台南": [
        {"name": "台南晶英酒店", "price": "NT$ 5,500/晚起", "rating": "9.3", "address": "台南市中西區西門路一段"},
        {"name": "台南大員皇冠假日酒店", "price": "NT$ 4,200/晚起", "rating": "8.8", "address": "台南市安平區"},
        {"name": "台南富信大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "台南市中西區公園路"},
        {"name": "台南永豐棧酒店", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "台南市南區西門路四段"},
    ],
    "屏東": [
        {"name": "墾丁福華渡假飯店", "price": "NT$ 5,800/晚起", "rating": "9.0", "address": "屏東縣恆春鎮墾丁路2號"},
        {"name": "凱撒大飯店墾丁", "price": "NT$ 4,500/晚起", "rating": "8.8", "address": "屏東縣恆春鎮墾丁路6號"},
        {"name": "小琉球民宿", "price": "NT$ 2,200/晚起", "rating": "8.5", "address": "屏東縣琉球鄉"},
        {"name": "東港海鮮飯店", "price": "NT$ 2,000/晚起", "rating": "8.2", "address": "屏東縣東港鎮"},
        {"name": "四重溪溫泉山莊", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "屏東縣車城鄉四重溪"},
    ],
    "宜蘭": [
        {"name": "礁溪長榮鳳凰酒店", "price": "NT$ 5,200/晚起", "rating": "9.1", "address": "宜蘭縣礁溪鄉健康路"},
        {"name": "礁溪老爺酒店", "price": "NT$ 6,800/晚起", "rating": "9.3", "address": "宜蘭縣礁溪鄉五峰路69號"},
        {"name": "太平山翠峰湖山屋", "price": "NT$ 3,200/晚起", "rating": "8.7", "address": "宜蘭縣大同鄉"},
        {"name": "羅東商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "宜蘭縣羅東鎮"},
        {"name": "蘇澳冷泉民宿", "price": "NT$ 2,000/晚起", "rating": "8.4", "address": "宜蘭縣蘇澳鎮"},
    ],
    "花蓮": [
        {"name": "花蓮理想大地度假村", "price": "NT$ 6,500/晚起", "rating": "9.1", "address": "花蓮縣壽豐鄉理想路1號"},
        {"name": "花蓮翰品酒店", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "花蓮市國聯一路51號"},
        {"name": "花蓮美侖大飯店", "price": "NT$ 4,200/晚起", "rating": "8.7", "address": "花蓮市林森路1號"},
        {"name": "花蓮統帥大飯店", "price": "NT$ 2,500/晚起", "rating": "8.3", "address": "花蓮市中山路2號"},
    ],
    "台東": [
        {"name": "知本老爺大酒店", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "台東縣卑南鄉溫泉村"},
        {"name": "台東娜路彎大酒店", "price": "NT$ 5,200/晚起", "rating": "8.9", "address": "台東市中興路一段"},
        {"name": "綠島朝日溫泉民宿", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "台東縣綠島鄉"},
        {"name": "蘭嶼原住民民宿", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "台東縣蘭嶼鄉"},
        {"name": "池上牧野渡假村", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "台東縣池上鄉"},
    ],
    "高雄": [
        {"name": "高雄漢來大飯店", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "高雄市前金區成功一路"},
        {"name": "高雄國賓大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "高雄市前金區民生二路"},
        {"name": "高雄福華大飯店", "price": "NT$ 3,200/晚起", "rating": "8.5", "address": "高雄市苓雅區四維三路"},
        {"name": "駁二艾尼斯旅店", "price": "NT$ 1,800/晚起", "rating": "8.7", "address": "高雄市鹽埕區"},
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
        Target city (台北、新北、桃園、台中、基隆、新竹、苗栗、彰化、南投、
        雲林、嘉義、台南、屏東、宜蘭、花蓮、台東、高雄).
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
        max_items: int = 5,
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
                        address=item.get("address", ""),
                        city=self.city,
                    )
                )
        return results
