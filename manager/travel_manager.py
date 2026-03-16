"""TravelManager – orchestrates scrapers, AI planner and navigation utilities.

Follows the Controller pattern: it owns the workflow and delegates to
specialised components (CityScraper, HotelScraper, TravelPlanner,
NavigationLinkGenerator) without coupling them to each other.
"""
import asyncio
import datetime
from dataclasses import dataclass, field
from typing import Any

from scrapers.city_scraper import CityScraper
from scrapers.hotel_scraper import HotelScraper
from scrapers.base_scraper import Attraction, Hotel
from ai.travel_planner import TravelPlanner
from utils.navigation import NavigationLinkGenerator


@dataclass
class TravelPlan:
    """Result object returned by :class:`TravelManager`."""

    city: str
    days: int
    budget: str
    preferences: list[str]
    attractions: list[Attraction] = field(default_factory=list)
    hotels: list[Hotel] = field(default_factory=list)
    itinerary_markdown: str = ""
    full_route_url: str = ""
    segment_links: list[dict[str, str]] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    )


class TravelManager:
    """Coordinates all components to produce a complete travel plan.

    Parameters
    ----------
    groq_api_key : str, optional
        Groq API key for AI itinerary generation.  Uses the
        ``GROQ_API_KEY`` environment variable as fallback.
    headless : bool
        Whether to run scrapers in headless mode (default ``True``).
    max_attractions : int
        Maximum attractions to fetch per city (default ``8``).
    max_hotels : int
        Maximum hotels to fetch (default ``5``).
    """

    def __init__(
        self,
        groq_api_key: str = "",
        headless: bool = True,
        max_attractions: int = 8,
        max_hotels: int = 10,
    ):
        self.groq_api_key = groq_api_key
        self.headless = headless
        self.max_attractions = max_attractions
        self.max_hotels = max_hotels

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_plan(
        self,
        city: str,
        days: int,
        budget: str = "中等",
        preferences: list[str] | None = None,
        check_in: str = "",
        check_out: str = "",
    ) -> TravelPlan:
        """Synchronously produce a :class:`TravelPlan`.

        This is the main entry-point for the Streamlit UI.  It wraps the
        async implementation so callers do not need to manage event loops.
        """
        return asyncio.run(
            self._create_plan_async(
                city=city,
                days=days,
                budget=budget,
                preferences=preferences or [],
                check_in=check_in,
                check_out=check_out,
            )
        )

    # ------------------------------------------------------------------
    # Private async implementation
    # ------------------------------------------------------------------

    async def _create_plan_async(
        self,
        city: str,
        days: int,
        budget: str,
        preferences: list[str],
        check_in: str,
        check_out: str,
    ) -> TravelPlan:
        """Run scrapers concurrently, then generate itinerary."""
        # 1. Scrape attractions and hotels concurrently
        city_scraper = CityScraper(city=city, headless=self.headless, max_items=self.max_attractions)
        hotel_scraper = HotelScraper(
            city=city,
            check_in=check_in,
            check_out=check_out,
            budget=budget,
            headless=self.headless,
            max_items=self.max_hotels,
        )

        attractions, hotels = await asyncio.gather(
            city_scraper.fetch(),
            hotel_scraper.fetch(),
        )

        # 2. Generate AI itinerary
        planner = TravelPlanner(api_key=self.groq_api_key)
        itinerary = planner.generate_itinerary(
            city=city,
            days=days,
            attractions=attractions,
            hotels=hotels,
            budget=budget,
            preferences=preferences,
        )

        # 3. Build navigation links
        attraction_names = [a.name for a in attractions]
        nav = NavigationLinkGenerator(attraction_names)
        full_route_url = nav.generate_full_route()
        segment_links = nav.generate_segment_links()

        return TravelPlan(
            city=city,
            days=days,
            budget=budget,
            preferences=preferences,
            attractions=attractions,
            hotels=hotels,
            itinerary_markdown=itinerary,
            full_route_url=full_route_url,
            segment_links=segment_links,
        )
