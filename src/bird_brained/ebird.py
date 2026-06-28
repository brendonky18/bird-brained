import csv
from dataclasses import dataclass
from datetime import date
from enum import Enum
from io import StringIO
from typing import Self

import requests
from bs4 import BeautifulSoup

from .data import BirdInfo


class Region(Enum):
    """The regions used by ebird.org"""

    WORLD = "world"
    WESTERN_HEMISPHERE = "wh"
    NORTH_AMERICA = "na"
    CENTRAL_AMERICA = "ca"
    WEST_INDIES = "caribbean"
    CARIBBEAN = "caribbean2"
    USA_LOWER_48 = "lower48"
    ABA_AREA = "aba"
    ABA_CONTINENTAL = "abac"
    AOU_AREA = "aou"
    LATIN_AMERICA_AND_CARIBBEAN = "latam"
    SOUTH_AMERICA = "sa"
    EASTERN_HEMISPHERE = "eh"
    AFRICA = "africa"
    AFRICA_ABA = "af"
    SOUTHERN_AFRICA = "saf"
    EURASIA = "es"
    WESTERN_PALEARTIC = "wp"
    EUROPE = "eu"
    ASIA = "as"
    MIDDLE_EAST = "me"
    OSME_REGION = "osme"
    AUSTRALASIA = "aue"
    AUSTRALASIA_ABA = "au"
    AUSTRALASIA_AND_TERRITORIES = "aut"
    SOUTH_POLAR = "sp"
    ATLANTIC_AND_ARCTIC_OCEANS = "ao"
    INDIAN_OCEAN = "io"
    PACIFIC_OCEAN = "po"
    ISLAND_OF_SPAIN = "islandhisp"
    ISLAND_OF_NEW_GUINEA = "islandng"
    ISLAND_OF_BORNEO = "islandborneo"
    MALAYSIA_BORNEO = "myborneo"
    MALAYSIA_PENINSULA = "mypeninsula"
    MAINLAND_PORTUGAL = "mainlandpt"

    @property
    def proper_name(self) -> str:
        return (
            self.name.title()
            .replace("_", " ")
            .replace(" Of ", " of ")
            .replace(" And ", " and ")
            .replace("Aba", "ABA")
            .replace("Osme", "Ornithological Society of the Middle East")
        )


@dataclass
class BirdListQuery:
    """Creates a filter for a bird list"""

    region: Region = Region.WORLD
    year: int | None = None
    month: int | None = None
    day: int | None = None

    def __post_init__(self):
        if self.day is not None and self.month is None:
            raise ValueError("Cannot specify day without month")

    def get_args(self) -> dict[str, str]:
        args = {"r": self.region.value}

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
        return args

    @classmethod
    def last_n_months(
        cls,
        n_months: int,
        cur_month: int = date.today().month,
        cur_year: int = date.today().year,
        region: Region = Region.WORLD,
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
            for i in range(cur_month):
                queries.append(cls(year=cur_year, month=cur_month - i, region=region))
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

    def __init__(self, username: str, password: str) -> None:
        super().__init__()
        self.username = username
        self.password = password

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

        return self

    def get_bird_list(
        self, query: BirdListQuery = BirdListQuery()
    ) -> dict[BirdInfo, str]:
        """Gets a list of birds for the provided query."""

        response = self.get(
            "https://ebird.org/lifelist", query.get_args() | {"fmt": "csv"}
        )
        response.raise_for_status()

        bird_list = dict()
        for row in csv.DictReader(StringIO(response.text)):
            cur_bird = BirdInfo(row["Common Name"], row["Scientific Name"])
            if cur_bird not in bird_list:
                bird_list[cur_bird] = row["Date"]

        return bird_list

    def get_last_6_months_list(
        self, region: Region = Region.WORLD
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
