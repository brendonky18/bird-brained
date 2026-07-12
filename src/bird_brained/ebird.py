import calendar
import csv
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from io import StringIO
from pathlib import Path
from time import sleep
from typing import NamedTuple
from typing import Self
from urllib.parse import parse_qs
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .data import BirdInfo


class Region(NamedTuple):
    """Corresponds to a location, region, or major region as defined by ebird.org"""

    code: str
    proper_name: str


class MajorRegion(Region, Enum):
    """The major regions used by ebird.org"""

    WORLD = ("world", "World")
    WESTERN_HEMISPHERE = ("wh", "Western Hemisphere")
    NORTH_AMERICA = ("na", "North America")
    CENTRAL_AMERICA = ("ca", "Central America")
    WEST_INDIES = ("caribbean", "West Indies")
    CARIBBEAN = ("caribbean2", "Caribbean")
    USA_LOWER_48 = ("lower48", "USA Lower 48")
    ABA_AREA = ("aba", "ABA Area")
    ABA_CONTINENTAL = ("abac", "ABA Continental")
    AOU_AREA = ("aou", "AOU Area")
    LATIN_AMERICA_AND_CARIBBEAN = ("latam", "Latin America and Caribbean")
    SOUTH_AMERICA = ("sa", "South America")
    EASTERN_HEMISPHERE = ("eh", "Eastern Hemisphere")
    AFRICA = ("africa", "Africa")
    AFRICA_ABA = ("af", "Africa ABA")
    SOUTHERN_AFRICA = ("saf", "Southern Africa")
    EURASIA = ("es", "Eurasia")
    WESTERN_PALEARTIC = ("wp", "Western Palearctic")
    EUROPE = ("eu", "Europe")
    ASIA = ("as", "Asia")
    MIDDLE_EAST = ("me", "Middle East")
    OSME_REGION = ("osme", "OSME Region")
    AUSTRALASIA = ("aue", "Australasia")
    AUSTRALASIA_ABA = ("au", "Australasia ABA")
    AUSTRALASIA_AND_TERRITORIES = ("aut", "Australasia and Territories")
    SOUTH_POLAR = ("sp", "South Polar")
    ATLANTIC_AND_ARCTIC_OCEANS = ("ao", "Atlantic/Arctic Oceans")
    INDIAN_OCEAN = ("io", "Indian Ocean")
    PACIFIC_OCEAN = ("po", "Pacific Ocean")
    ISLAND_OF_HISPANIOLA = ("islandhisp", "Island of Hispaniola")
    ISLAND_OF_NEW_GUINEA = ("islandng", "Island of New Guinea")
    ISLAND_OF_BORNEO = ("islandborneo", "Island of Borneo")
    MALAYSIA_BORNEO = ("myborneo", "Malaysia (Borneo)")
    MALAYSIA_PENINSULA = ("mypeninsula", "Malaysia (Peninsula)")
    MAINLAND_PORTUGAL = ("mainlandpt", "Mainland Portugal")


@dataclass
class BirdListQuery:
    """Creates a filter for a bird list"""

    region: Region = MajorRegion.WORLD
    year: int | None = None
    month: int | None = None
    day: int | None = None
    _time: str = "life"

    def __post_init__(self):
        if self.day is not None and self.month is None:
            raise ValueError("Cannot specify day without month")

        args = {"r": self.region.code}

        if self.year is None:
            args["time"] = "life"
        else:
            args["year"] = str(self.year)
            args["time"] = "year"

        if self.month is not None:
            args["time"] = "month"
            args["m"] = str(self.month)

        if self.day is not None:
            args["time"] = "day"
            args["d"] = str(self.day)

        self._args = args
        self._time = args["time"]

    def get_args(self) -> dict[str, str]:
        return self._args

    @property
    def is_current(self) -> bool:
        """Returns True if the query is for the current day, month or year"""
        today = date.today()
        if self._time == "life":
            return False
        elif self._time == "year":
            return self.year == today.year
        elif self._time == "month":
            return self.year == today.year and self.month == today.month
        elif self._time == "day":
            return (
                self.year == today.year
                and self.month == today.month
                and self.day == today.day
            )
        else:
            raise ValueError(f"{self._time}: unknown query time value")

    def __str__(self) -> str:
        s = ""
        if self._time == "life":
            s = "All-time"
        elif self._time == "year":
            s = f"{self.year}"
        elif self._time == "month":
            assert isinstance(self.month, int)
            s = f"{calendar.month_name[self.month]}{(' ' + str(self.year)) if self.year else ''}"
        elif self._time == "day":
            assert isinstance(self.day, int)
            assert isinstance(self.month, int)
            s = f"{calendar.month_name[self.month]} {self.day}{(' ' + str(self.year)) if self.year else ''}"
        else:
            raise ValueError("Time is not set")

        s += f" ({self.region.proper_name})"
        return s

    @classmethod
    def last_n_months(
        cls,
        n_months: int,
        cur_month: int = date.today().month,
        cur_year: int = date.today().year,
        region: Region = MajorRegion.WORLD,
    ) -> list[Self]:
        """Gets the list of birds sighted in the previous n months of the provided date"""

        if not 1 <= cur_month <= 12:
            raise ValueError("cur_month must be between 1 and 12")

        if n_months < 1:
            raise ValueError("Number of months must be greater than 1")

        # instead of doing each month, we can just query for the list from the current year
        # plus the remaining months from the previous year
        queries = []

        # get list for the previous current year
        while cur_month <= n_months:
            # for i in range(cur_month):
            #     queries.append(cls(year=cur_year, month=cur_month - i, region=region))
            queries.append(cls(year=cur_year, month=None, region=region))
            cur_year -= 1
            n_months = n_months - cur_month
            cur_month = 12

        # get the list for the remaining months that don't make a whole year
        for i in range(n_months):
            queries.append(cls(year=cur_year, month=cur_month - i, region=region))

        return queries


class EBirdSession(requests.Session):
    """Starts a session that is authenticated to ebird.org"""

    _url: str = "https://ebird.org/home"
    _api_key: str

    def __init__(self, username: str, password: str, cache: Path | None = None) -> None:
        super().__init__()
        self.username = username
        self.password = password
        self.cache = cache

        if cache is not None:
            cache.mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> Self:
        super().__enter__()
        # get session info
        response = self.get(self._url, params={"forceLogin": "true"})
        response.raise_for_status()

        # parse the login page to get the execution value
        soup = BeautifulSoup(response.text, "html.parser")
        login_input = soup.find("input", attrs={"type": "hidden", "name": "execution"})
        assert login_input is not None, "Login input not found"
        csrf_token = str(login_input["value"])
        login_data = {
            "execution": csrf_token,
            "username": self.username,
            "password": self.password,
            "_eventId": "submit",
        }

        # send login request
        response = self.post(response.url, data=login_data)
        if response.status_code == 401:
            raise RuntimeError("Failed to authenticate")
        response.raise_for_status()

        # parse the page to get the api key
        soup = BeautifulSoup(response.text, "html.parser")
        explore_regions = soup.find("clo-suggest", attrs={"id": "exploreRegions"})
        assert explore_regions is not None, "Could not find exploreRegions element"
        search_url = explore_regions["url"]
        assert isinstance(search_url, str), "Could not find search url"
        self._api_key = parse_qs(urlparse(search_url).query)["key"][0]

        return self

    def get_bird_list(
        self, query: BirdListQuery = BirdListQuery()
    ) -> dict[BirdInfo, str]:
        """Gets a list of birds for the provided query."""
        cache_path = None
        if self.cache is not None:
            cache_path = self.cache / f"lists/{query!s}.csv"

        if cache_path is not None and cache_path.exists() and not query.is_current:
            print(f"Using cached bird list for {query} at {cache_path!s}")
            text = cache_path.read_text()
        else:
            sleep(1)  # rate limit
            print(f"Downloading bird list for {query}")
            response = self.get(
                "https://ebird.org/lifelist", query.get_args() | {"fmt": "csv"}
            )
            response.raise_for_status()
            text = response.text

            # save result to the cache
            if cache_path is not None and not query.is_current:
                print(f"Saving bird list for {query} at {cache_path!s}")
                cache_path.write_text(text)

        print(f"Got bird list for {query}")

        bird_list = dict()
        for row in csv.DictReader(StringIO(text)):
            cur_bird = BirdInfo(row["Common Name"], row["Scientific Name"])
            if cur_bird not in bird_list:
                bird_list[cur_bird] = row["Date"]

        return bird_list

    def get_last_6_months_list(
        self, region: Region = MajorRegion.WORLD
    ) -> dict[BirdInfo, str]:
        """Gets the list of birds seen in the previous 6 months"""

        date.today().month

        birds: dict[BirdInfo, str] = dict()

        # this gets the current month first
        for q in BirdListQuery.last_n_months(6, region=region):
            month_list = self.get_bird_list(q)
            # do it this way to get the date of the most recent sighting
            birds = month_list | birds

        return birds

    def get_region_from_code(self, region_code: str) -> Region:
        if any(len(s) > 3 or not s.isupper() for s in region_code.split("-")):
            raise ValueError(f"{region_code}: invalid region code")
        response = self.get(f"https://ebird.org/lifelist/{region_code}")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        region_header = soup.find(
            "span", attrs={"class": ["Heading-main", "u-inline-sm"]}
        )
        if region_header is None:
            raise ValueError(f"{region_code}: could not find region")

        return Region(region_code, region_header.text.strip())

    def get_region_from_name(self, name: str) -> Region:
        response = self.get(
            "https://api.ebird.org/v2/ref/region/find",
            params={
                "key": self._api_key,
                "q": name,
                "locale": "en",
            },
        )
        response.raise_for_status()
        results = response.json()
        if len(results) == 0:
            raise ValueError(f"{name}: found no matching region")

        # TODO: figure out how to handle when there are multiple results
        # what about casses like "essex" where there are multiple exact matches
        # I want to ignore the country codes in the names => strip the last 4 characters off of the end of the name, since that will always be the country code
        result = results[0]
        if len(results) == 1:
            return Region(result["code"], result["name"])
        p = r"(, [\w ]+)*?, ".join(
            [
                f"({re.escape(part)})" if i == 0 else f"({re.escape(part)})?"
                for i, part in enumerate(name.split(", "))
            ]
        )
        print(p)
        search_pattern = re.compile(p)

        matches = re.match(search_pattern, result["name"])
        if matches is None:
            raise ValueError(f"{name}: found no exact matches for region")

        def get_count(groups: tuple[str | None, ...]) -> int:
            return sum(g is not None for g in groups)

        best_match = get_count(matches.groups())

        equivalent_matches = [
            r["name"]
            for r in results
            if (match := re.match(search_pattern, r["name"])) is not None
            and get_count(match.groups()) == best_match
        ]

        if len(equivalent_matches) > 1:
            raise ValueError(
                f"Multiple possible matches for \"{name}\":\n{'\n'.join(f"- {m}" for m in equivalent_matches)}"
            )

        return Region(result["code"], result["name"])

    def get_region(self, search_str: str) -> Region:
        """
        Gets the region that matches the provided search string

        If the search string is all-caps, it will be treated as a region code,
        and it will perform a query to get the name of that region.

        Otherwise, it will perform a query to find the region that matches the name.
        If only one result is found, or the search string is an exact match for the
        first result, that region will be returned.
        If it cannot find a matching region, an exception will be raised.
        """
        if all(part.isupper() for part in search_str.split("-")):
            return self.get_region_from_code(search_str)
        else:
            return self.get_region_from_name(search_str)
