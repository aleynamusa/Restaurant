"""Put leads on the map.

OpenStreetMap leads already carry coordinates. Everything else (permit notices, news, CSV) is
geocoded by address through Nominatim (OpenStreetMap's public geocoder, max 1 request/second,
see https://operations.osmfoundation.org/policies/nominatim/). When that fails or is switched
off, the lead is placed at its city centre and the map marks it as approximate.

Coordinates are stored on the lead, so each address is looked up once across all runs.
"""
from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlencode

from .http import Fetcher
from .models import Lead, normalize

log = logging.getLogger(__name__)

# Rough city centres, used when an address can't be geocoded.
CITY_CENTRES: dict[str, tuple[float, float]] = {
    "amsterdam": (52.3728, 4.8936), "rotterdam": (51.9225, 4.4792), "den haag": (52.0705, 4.3007),
    "s gravenhage": (52.0705, 4.3007), "the hague": (52.0705, 4.3007), "utrecht": (52.0907, 5.1214),
    "eindhoven": (51.4416, 5.4697), "groningen": (53.2194, 6.5665), "tilburg": (51.5555, 5.0913),
    "almere": (52.3508, 5.2647), "breda": (51.5719, 4.7683), "nijmegen": (51.8126, 5.8372),
    "apeldoorn": (52.2112, 5.9699), "haarlem": (52.3874, 4.6462), "arnhem": (51.9851, 5.8987),
    "enschede": (52.2215, 6.8937), "amersfoort": (52.1561, 5.3878), "zaanstad": (52.4389, 4.8258),
    "s hertogenbosch": (51.6978, 5.3037), "den bosch": (51.6978, 5.3037), "haarlemmermeer": (52.3030, 4.6889),
    "zwolle": (52.5168, 6.0830), "leiden": (52.1601, 4.4970), "maastricht": (50.8514, 5.6910),
    "dordrecht": (51.8133, 4.6901), "zoetermeer": (52.0575, 4.4931), "ede": (52.0402, 5.6649),
    "leeuwarden": (53.2012, 5.7999), "alkmaar": (52.6324, 4.7534), "delft": (52.0116, 4.3571),
    "deventer": (52.2550, 6.1639), "venlo": (51.3704, 6.1724), "hilversum": (52.2292, 5.1669),
    "heerlen": (50.8882, 5.9795), "amstelveen": (52.3114, 4.8701), "roosendaal": (51.5308, 4.4653),
    "oss": (51.7650, 5.5181), "schiedam": (51.9192, 4.3886), "helmond": (51.4793, 5.6570),
    "gouda": (52.0115, 4.7105), "purmerend": (52.5050, 4.9597), "middelburg": (51.4988, 3.6136),
    "wageningen": (51.9692, 5.6654), "assen": (52.9925, 6.5649), "lelystad": (52.5185, 5.4714),
    "hoorn": (52.6424, 5.0597), "vlaardingen": (51.9122, 4.3419), "zeist": (52.0907, 5.2333),
    "emmen": (52.7858, 6.8976), "hengelo": (52.2659, 6.7931), "bergen op zoom": (51.4950, 4.2911),
}


class Geocoder:
    def __init__(self, cfg: dict, fetcher: Fetcher, seed: dict[str, list[float]] | None = None):
        g = cfg["geocode"]
        self.enabled = g["enabled"]
        self.endpoint = g["endpoint"]
        self.max_lookups = g["max_lookups"]
        self.fetcher = fetcher
        self.seed = {normalize(k): v for k, v in (seed or {}).items()}  # demo: known addresses, no network
        self.lookups = 0
        self._last = 0.0

    def locate(self, lead: Lead) -> None:
        if lead.lat is not None and lead.geo_precision in ("exact", "address"):
            return
        if lead.address and lead.city:
            hit = self.seed.get(normalize(f"{lead.address}, {lead.city}")) or self._nominatim(lead)
            if hit:
                lead.lat, lead.lon, lead.geo_precision = hit[0], hit[1], "address"
                return
        if lead.lat is None:
            centre = CITY_CENTRES.get(normalize(lead.city))
            if centre:
                lead.lat, lead.lon, lead.geo_precision = centre[0], centre[1], "city"

    def _nominatim(self, lead: Lead) -> tuple[float, float] | None:
        if not self.enabled or self.lookups >= self.max_lookups:
            return None
        wait = 1.05 - (time.monotonic() - self._last)
        if wait > 0 and self.fetcher.fixtures is None:
            time.sleep(wait)
        self._last = time.monotonic()
        self.lookups += 1
        params = {"street": lead.address, "city": lead.city, "country": "Netherlands",
                  "format": "jsonv2", "limit": 1}
        if lead.postcode:
            params["postalcode"] = lead.postcode
        body = self.fetcher.get(f"{self.endpoint}?{urlencode(params)}")
        try:
            rows = json.loads(body) if body else []
            return (float(rows[0]["lat"]), float(rows[0]["lon"])) if rows else None
        except (ValueError, KeyError, IndexError, TypeError):
            log.debug("geocode: unexpected response for %s", lead.address)
            return None
