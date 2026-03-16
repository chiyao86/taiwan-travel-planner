"""Abstract base class for all scrapers."""
import abc
import asyncio
import random
from dataclasses import dataclass, field
from typing import Any


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.3; rv:123.0) Gecko/20100101 Firefox/123.0",
]


@dataclass
class Attraction:
    """Represents a tourist attraction."""

    name: str
    description: str = ""
    address: str = ""
    city: str = ""
    category: str = ""
    image_url: str = ""
    source_url: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class Hotel:
    """Represents a hotel listing."""

    name: str
    price: str = ""
    rating: str = ""
    address: str = ""
    city: str = ""
    image_url: str = ""
    source_url: str = ""
    extra: dict = field(default_factory=dict)


class BaseScraper(abc.ABC):
    """Abstract base class that defines the scraping interface.

    All concrete scrapers must implement the ``fetch`` coroutine which
    returns a list of structured data objects scraped from a target URL.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.user_agent = random.choice(USER_AGENTS)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def fetch(self, **kwargs) -> list[Any]:
        """Fetch data from the target source.

        Must be implemented by every concrete subclass.

        Returns
        -------
        list[Any]
            A list of structured data objects (e.g. :class:`Attraction`
            or :class:`Hotel`).
        """

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def random_delay(min_sec: float = 1.0, max_sec: float = 3.5) -> None:
        """Sleep for a random duration to mimic human behaviour."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    def random_user_agent() -> str:
        """Return a randomly chosen User-Agent string."""
        return random.choice(USER_AGENTS)
