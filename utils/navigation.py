"""NavigationLinkGenerator – builds Google Maps navigation URLs.

Given a list of attraction names, this utility assembles a deep-link URL
that opens Google Maps with a complete multi-stop route so travellers can
navigate the full itinerary without manual copy-pasting.

URL format used
---------------
https://www.google.com/maps/dir/<stop1>/<stop2>/.../<stopN>
"""
from urllib.parse import quote


GOOGLE_MAPS_BASE = "https://www.google.com/maps/"
GOOGLE_MAPS_DIR  = "https://www.google.com/maps/dir/"


class NavigationLinkGenerator:
    """Generates a Google Maps complete-route link for a sequence of attractions.

    Parameters
    ----------
    attractions : list[str]
        Ordered list of place names (e.g. ``["台北101", "故宮博物院", "淡水老街"]``).
    """

    def __init__(self, attractions: list[str]):
        self.attractions = [a.strip() for a in attractions if a.strip()]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_full_route(self) -> str:
        """Return a single Google Maps URL covering all attractions in order.

        Uses the ``/maps/dir/`` format which renders a proper multi-stop
        route on Google Maps for the entire day's itinerary.
        """
        if not self.attractions:
            return GOOGLE_MAPS_BASE
        if len(self.attractions) == 1:
            return self._search_url(self.attractions[0])

        stops = "/".join(quote(a, safe="") for a in self.attractions)
        return f"{GOOGLE_MAPS_DIR}{stops}/"

    def generate_segment_links(self) -> list[dict[str, str]]:
        """Kept for backward compatibility – returns empty list.

        The application now shows only the complete route link.
        """
        return []

    def generate_place_link(self, place: str) -> str:
        """Return a Google Maps search URL for a single place."""
        return self._search_url(place)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _search_url(place: str) -> str:
        return f"{GOOGLE_MAPS_BASE}search/{quote(place, safe='')}"
