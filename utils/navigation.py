"""NavigationLinkGenerator – builds Google Maps navigation URLs.

Given a list of attraction names, this utility assembles deep-link URLs
that open Google Maps with pre-populated origin / destination fields so
travellers can navigate between sights without manual copy-pasting.

URL format used
---------------
https://www.google.com/maps/dir/?api=1&origin=<A>&destination=<B>&waypoints=<C>|<D>
"""
from urllib.parse import quote


GOOGLE_MAPS_BASE = "https://www.google.com/maps/"
GOOGLE_MAPS_DIR = "https://www.google.com/maps/dir/"


class NavigationLinkGenerator:
    """Generates Google Maps navigation links for a sequence of attractions.

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

        The first element is the *origin*, the last is the *destination* and
        everything in between becomes *waypoints*.
        """
        if not self.attractions:
            return GOOGLE_MAPS_BASE
        if len(self.attractions) == 1:
            return self._search_url(self.attractions[0])

        origin = quote(self.attractions[0])
        destination = quote(self.attractions[-1])
        params = f"?api=1&origin={origin}&destination={destination}"

        if len(self.attractions) > 2:
            waypoints = "|".join(quote(a) for a in self.attractions[1:-1])
            params += f"&waypoints={waypoints}"

        return GOOGLE_MAPS_DIR + params

    def generate_segment_links(self) -> list[dict[str, str]]:
        """Return a list of point-to-point navigation links.

        Each element is a ``dict`` with keys:
        * ``"label"`` – human-readable segment name (e.g. ``"台北101 → 故宮博物院"``).
        * ``"url"``   – Google Maps navigation URL for that segment.
        """
        if len(self.attractions) < 2:
            return []

        segments = []
        for i in range(len(self.attractions) - 1):
            origin = self.attractions[i]
            destination = self.attractions[i + 1]
            url = (
                f"{GOOGLE_MAPS_DIR}?api=1"
                f"&origin={quote(origin)}"
                f"&destination={quote(destination)}"
            )
            segments.append({"label": f"{origin} → {destination}", "url": url})
        return segments

    def generate_place_link(self, place: str) -> str:
        """Return a Google Maps search URL for a single place."""
        return self._search_url(place)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _search_url(place: str) -> str:
        return f"{GOOGLE_MAPS_BASE}search/?api=1&query={quote(place)}"
