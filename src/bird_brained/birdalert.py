import csv
import logging
import time
from datetime import datetime
from datetime import timedelta
from io import StringIO
from random import randint
from typing import Self

import requests
from bs4 import BeautifulSoup

from .data import BirdInfo

log = logging.getLogger(__name__)


class BirdAlertSession(requests.Session):
    """Starts a session that is authenticated to birdalerts.info"""

    _delay: int = 2000  # the amount of milliseconds to wait between sending requests
    _jitter: int = 500  # the amount of milliseconds to add or subtract from the delay

    _login_url = "https://birdalerts.info/login"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

        self._next_request = datetime.now()

        super().__init__()

    def __enter__(self) -> Self:
        super().__enter__()

        response = self.get(self._login_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        login_input = soup.find("input", attrs={"type": "hidden", "id": "csrf_token"})
        assert login_input is not None, "Login input not found"
        self._csrf_token = login_input["value"]

        # send login request
        response = self.post(
            self._login_url,
            data={
                "username": self.username,
                "password": self.password,
                "submit": "Login",
                "csrf_token": self._csrf_token,
            },
        )
        log.debug(f"logged in as {self.username}")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.find("div", attrs={"class": "alert-danger"}):
            raise RuntimeError("Login attempt failed")

        return self

    def request(self, *args, **kwargs):
        now = datetime.now()
        if now < self._next_request:
            time.sleep((self._next_request - now).total_seconds())

        jitter = randint(-self._jitter, self._jitter)
        self._next_request = datetime.now() + timedelta(
            milliseconds=self._delay + jitter
        )
        return super().request(*args, **kwargs)

    def upload_list(self, birds: list[BirdInfo], list_name: str):
        """Uploads the provided birds and creates a list with the provided name."""
        log.debug("Uploading bird list")

        bird_list_upload_url = "https://birdalerts.info/upload_bird_list_file"
        bird_list_create_url = "https://birdalerts.info/create_bird_list"

        # convert list of birds to csv
        out = StringIO()
        writer = csv.DictWriter(out, fieldnames=["Common Name", "Scientific Name"])
        writer.writeheader()
        for bird in birds:
            writer.writerow(
                {
                    "Common Name": bird.common_name,
                    "Scientific Name": bird.scientific_name,
                }
            )

        # upload bird list
        bird_list_post_data = {
            "edit_bird_list_id": "",
            "csrf_token": self._csrf_token,
            "list_name": list_name,
            "bird": "",
        }
        response = self.post(
            bird_list_upload_url,
            data=bird_list_post_data,
            files={"file": ("bird_list.csv", out.getvalue())},
        )
        response.raise_for_status()

        # create bird list
        response = self.post(
            bird_list_create_url,
            data=bird_list_post_data,
            files={"file": ("bird_list.csv", out.getvalue())},
        )
        response.raise_for_status()
        log.info(f"Updated '{list_name}' with {len(birds)} birds")
