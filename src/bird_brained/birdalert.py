import csv
from io import StringIO
from typing import Self

import requests
from bs4 import BeautifulSoup

from .data import BirdInfo


class BirdAlertSession(requests.Session):
    """Starts a session that is authenticated to birdalerts.info"""

    _login_url = "https://birdalerts.info/login"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        super().__init__()

    def __enter__(self) -> Self:
        super().__enter__()

        response = self.get(self._login_url)
        response.raise_for_status()
        print(0)
        # print(response.text)
        soup = BeautifulSoup(response.text, "html.parser")
        login_input = soup.find("input", attrs={"type": "hidden", "id": "csrf_token"})
        assert login_input is not None, "Login input not found"
        self._csrf_token = login_input["value"]
        print(self._csrf_token)

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
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.find("div", attrs={"class": "alert-danger"}):
            raise RuntimeError("Login attempt failed")
        print(1)
        # print(response.headers)
        print(response.status_code)
        # print(response.text)

        return self

    def upload_list(self, birds: list[BirdInfo], list_name: str):
        """Uploads the provided birds and creates a list with the provided name."""

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
        print(2)
        print(response.status_code)

        # create bird list
        response = self.post(
            bird_list_create_url,
            data=bird_list_post_data,
            files={"file": ("bird_list.csv", out.getvalue())},
        )
        response.raise_for_status()
        print(3)
        print(f"Updated '{list_name}' with {len(birds)} birds")
