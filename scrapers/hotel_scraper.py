"""HotelScraper – scrapes hotel listings from Booking.com.

Employs multiple anti-bot measures:
* ``playwright-stealth`` to hide automation fingerprints
* Random User-Agent rotation
* Random scroll and mouse-move delays mimicking human behaviour
* Falls back to curated static hotel data when live scraping fails.
* Paginates through up to ``max_pages`` result pages to collect enough items.
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
BOOKING_RESULTS_PER_PAGE = 25  # Booking.com shows 25 results per page

BOOKING_CITY_NAMES: dict[str, str] = {
    "台北": "Taipei, Taiwan",
    "台中": "Taichung, Taiwan",
    "台南": "Tainan, Taiwan",
    "高雄": "Kaohsiung, Taiwan",
    "花蓮": "Hualien, Taiwan",
}

# Fallback hotel data – at least 10 entries per city so the app always has
# enough results even when live scraping is blocked.
FALLBACK_HOTELS: dict[str, list[dict]] = {
    "台北": [
        {"name": "台北君悅大飯店", "price": "NT$ 6,800/晚起", "rating": "9.0", "address": "台北市信義區松壽路2號"},
        {"name": "W台北", "price": "NT$ 7,200/晚起", "rating": "9.2", "address": "台北市信義區忠孝東路五段10號"},
        {"name": "台北喜來登大飯店", "price": "NT$ 5,500/晚起", "rating": "8.8", "address": "台北市中正區忠孝東路一段12號"},
        {"name": "台北美侖大飯店", "price": "NT$ 3,800/晚起", "rating": "8.5", "address": "台北市中山區民族東路"},
        {"name": "西門町商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台北市萬華區西寧南路"},
        {"name": "寒舍艾麗酒店", "price": "NT$ 8,500/晚起", "rating": "9.3", "address": "台北市信義區松壽路18號"},
        {"name": "台北文華東方酒店", "price": "NT$ 12,000/晚起", "rating": "9.5", "address": "台北市松山區敦化北路166號"},
        {"name": "馥敦飯店南京館", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "台北市中山區南京東路二段166號"},
        {"name": "首都大飯店", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "台北市中山區林森北路63號"},
        {"name": "台北福容大飯店京站", "price": "NT$ 3,500/晚起", "rating": "8.7", "address": "台北市大同區承德路一段1號"},
        {"name": "北投麗禧溫泉酒店", "price": "NT$ 9,000/晚起", "rating": "9.4", "address": "台北市北投區幽雅路21號"},
        {"name": "大倉久和大飯店", "price": "NT$ 10,500/晚起", "rating": "9.6", "address": "台北市中山區南京東路一段9號"},
    ],
    "台中": [
        {"name": "日月千禧酒店", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "台中市西屯區市政北一路"},
        {"name": "台中金典酒店", "price": "NT$ 3,800/晚起", "rating": "8.7", "address": "台中市西區館前路"},
        {"name": "台中長榮桂冠酒店", "price": "NT$ 5,000/晚起", "rating": "8.9", "address": "台中市西屯區台灣大道二段"},
        {"name": "逢甲商旅", "price": "NT$ 1,600/晚起", "rating": "8.3", "address": "台中市西屯區逢甲路"},
        {"name": "台中萬楓酒店", "price": "NT$ 3,200/晚起", "rating": "8.8", "address": "台中市西屯區台灣大道三段301號"},
        {"name": "台中亞緻大飯店", "price": "NT$ 4,200/晚起", "rating": "9.1", "address": "台中市西屯區惠來路二段111號"},
        {"name": "台中福容大飯店", "price": "NT$ 3,000/晚起", "rating": "8.6", "address": "台中市南屯區公益路二段51號"},
        {"name": "台中全國大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "台中市西區館前路41號"},
        {"name": "悅華大飯店", "price": "NT$ 2,500/晚起", "rating": "8.5", "address": "台中市北區學士路98號"},
        {"name": "永豐棧酒店", "price": "NT$ 3,600/晚起", "rating": "8.8", "address": "台中市南屯區文心南二路6號"},
        {"name": "台中葉綠宿旅館", "price": "NT$ 1,400/晚起", "rating": "8.1", "address": "台中市西屯區逢甲路169號"},
        {"name": "清新溫泉飯店", "price": "NT$ 2,000/晚起", "rating": "8.3", "address": "台中市大里區東榮路33號"},
    ],
    "台南": [
        {"name": "台南晶英酒店", "price": "NT$ 5,500/晚起", "rating": "9.3", "address": "台南市中西區西門路一段89號"},
        {"name": "台南大員皇冠假日酒店", "price": "NT$ 4,200/晚起", "rating": "8.8", "address": "台南市安平區州平路1號"},
        {"name": "台南富信大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "台南市中西區公園路21號"},
        {"name": "台南永豐棧酒店", "price": "NT$ 3,200/晚起", "rating": "8.6", "address": "台南市南區西門路四段687號"},
        {"name": "香格里拉台南遠東國際大飯店", "price": "NT$ 5,800/晚起", "rating": "9.2", "address": "台南市東區大學路西段89號"},
        {"name": "台南老爺行旅", "price": "NT$ 4,500/晚起", "rating": "9.0", "address": "台南市北區成功路45號"},
        {"name": "台南維悅酒店", "price": "NT$ 3,500/晚起", "rating": "8.9", "address": "台南市中西區民族路二段79號"},
        {"name": "夏都沙灘旅館", "price": "NT$ 6,000/晚起", "rating": "9.1", "address": "台南市安平區光州路38號"},
        {"name": "大億麗緻酒店", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "台南市南區健康路一段100號"},
        {"name": "台南桂田喜來登酒店", "price": "NT$ 4,000/晚起", "rating": "8.7", "address": "台南市中西區西門路一段288號"},
        {"name": "和逸飯店台南西門館", "price": "NT$ 2,200/晚起", "rating": "8.5", "address": "台南市中西區西門路二段65號"},
        {"name": "台南商旅", "price": "NT$ 1,800/晚起", "rating": "8.2", "address": "台南市中西區民生路一段"},
    ],
    "高雄": [
        {"name": "高雄漢來大飯店", "price": "NT$ 4,800/晚起", "rating": "9.0", "address": "高雄市前金區成功一路266號"},
        {"name": "高雄國賓大飯店", "price": "NT$ 3,500/晚起", "rating": "8.6", "address": "高雄市前金區民生二路202號"},
        {"name": "高雄福華大飯店", "price": "NT$ 3,200/晚起", "rating": "8.5", "address": "高雄市苓雅區四維三路167號"},
        {"name": "駁二艾尼斯旅店", "price": "NT$ 1,800/晚起", "rating": "8.7", "address": "高雄市鹽埕區大勇路101號"},
        {"name": "寒軒國際大飯店", "price": "NT$ 3,800/晚起", "rating": "8.9", "address": "高雄市苓雅區四維四路33號"},
        {"name": "高雄金典酒店", "price": "NT$ 4,200/晚起", "rating": "9.1", "address": "高雄市苓雅區自強三路1號"},
        {"name": "義大天悅飯店", "price": "NT$ 5,500/晚起", "rating": "9.2", "address": "高雄市大樹區學城路一段1之2號"},
        {"name": "高雄長谷大飯店", "price": "NT$ 2,800/晚起", "rating": "8.4", "address": "高雄市新興區長谷路"},
        {"name": "高雄圓山大飯店", "price": "NT$ 3,600/晚起", "rating": "8.8", "address": "高雄市左營區蓮海路105號"},
        {"name": "承億文旅高雄駁二", "price": "NT$ 2,500/晚起", "rating": "8.9", "address": "高雄市鹽埕區大義街2號"},
        {"name": "高雄85大樓君鴻國際酒店", "price": "NT$ 4,000/晚起", "rating": "8.7", "address": "高雄市苓雅區自強三路1號"},
        {"name": "夢時代尊爵大飯店", "price": "NT$ 2,200/晚起", "rating": "8.3", "address": "高雄市前鎮區中華五路789號"},
    ],
    "花蓮": [
        {"name": "花蓮理想大地度假村", "price": "NT$ 6,500/晚起", "rating": "9.1", "address": "花蓮縣壽豐鄉理想路1號"},
        {"name": "花蓮翰品酒店", "price": "NT$ 3,800/晚起", "rating": "8.8", "address": "花蓮市國聯一路51號"},
        {"name": "花蓮美侖大飯店", "price": "NT$ 4,200/晚起", "rating": "8.7", "address": "花蓮市林森路1號"},
        {"name": "花蓮統帥大飯店", "price": "NT$ 2,500/晚起", "rating": "8.3", "address": "花蓮市中山路2號"},
        {"name": "老爺行旅花蓮", "price": "NT$ 5,000/晚起", "rating": "9.2", "address": "花蓮市國聯一路40號"},
        {"name": "花蓮亞士都飯店", "price": "NT$ 3,000/晚起", "rating": "8.5", "address": "花蓮市中正路215號"},
        {"name": "花蓮煙波大飯店太魯閣館", "price": "NT$ 4,500/晚起", "rating": "8.9", "address": "花蓮縣秀林鄉崇德村"},
        {"name": "花蓮遠雄悅來大飯店", "price": "NT$ 7,000/晚起", "rating": "9.3", "address": "花蓮縣壽豐鄉鹽寮村福德180號"},
        {"name": "美麗信花園酒店", "price": "NT$ 3,500/晚起", "rating": "8.8", "address": "花蓮市中美路88號"},
        {"name": "花蓮福容大飯店", "price": "NT$ 2,800/晚起", "rating": "8.6", "address": "花蓮市海岸路51號"},
        {"name": "花蓮馥麗溫泉大飯店", "price": "NT$ 3,200/晚起", "rating": "8.7", "address": "花蓮縣吉安鄉南昌路一段125號"},
        {"name": "知卡宣森林溫泉會館", "price": "NT$ 2,200/晚起", "rating": "8.4", "address": "花蓮市知卡宣林蔭大道"},
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
        Maximum number of hotels to return (default ``10``).
    max_pages : int
        Maximum number of Booking.com result pages to paginate through
        (default ``10``).  Each page holds up to 25 results.
    """

    def __init__(
        self,
        city: str,
        check_in: str = "",
        check_out: str = "",
        budget: str = "中等",
        headless: bool = True,
        max_items: int = 10,
        max_pages: int = 10,
    ):
        super().__init__(headless=headless)
        self.city = city
        self.check_in = check_in
        self.check_out = check_out
        self.budget = budget
        self.max_items = max_items
        self.max_pages = max_pages

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

    def _build_url(self, offset: int = 0) -> str:
        """Construct the Booking.com search URL for the given page offset."""
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
        if offset > 0:
            params += f"&offset={offset}"
        return BOOKING_BASE + params

    async def _scrape(self) -> list[Hotel]:
        """Launch stealth browser and scrape Booking.com results across pages."""
        hotels: list[Hotel] = []

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
                for page_num in range(self.max_pages):
                    if len(hotels) >= self.max_items:
                        break

                    offset = page_num * BOOKING_RESULTS_PER_PAGE
                    url = self._build_url(offset=offset)

                    await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                    await self.random_delay(2.5, 5.0)
                    await self._human_scroll(page)
                    await self.random_delay(1.0, 2.0)

                    found_on_page = 0
                    # Try multiple selector strategies for resilience
                    for selector in [
                        "div[data-testid='property-card']",
                        "div.sr_property_block",
                        "div.hotel_itm_inner",
                    ]:
                        cards = await page.query_selector_all(selector)
                        if cards:
                            for card in cards:
                                if len(hotels) >= self.max_items:
                                    break
                                hotel = await self._parse_card(card)
                                if hotel:
                                    hotels.append(hotel)
                                    found_on_page += 1
                            break

                    # Stop paginating if no results were found on this page
                    if found_on_page == 0:
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
