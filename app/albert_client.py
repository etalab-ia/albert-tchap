from datetime import datetime, timedelta, timezone

import requests

from matrix_bot.config import logger


def log_and_raise_for_status(response):
    if not response.ok:
        try:
            logger.error(f'Error Detail: {response.json().get("detail")}')
        except Exception:
            pass
    response.raise_for_status()


class AlbertApiClient:
    def __init__(self, config, api_token=None):
        if api_token is not None and (
            config.albert_username or config.albert_password
        ):
            logger.error(
                "Error: You need to either set the api_token or the username/password couple, but not both at the same time."
            )
            exit(2)

        self.url = config.albert_api_url.rstrip("/")
        self.username = config.albert_username
        self.password = config.albert_password

        # Token:
        self.token = None
        self.token_dt = None
        self.token_ttl = config.albert_access_token_ttl - 2
        self.api_token = api_token

    def _fetch(self, method, route, headers: dict | None = None, json_data=None):
        d = {
            "POST": requests.post,
            "GET": requests.get,
            "PUT": requests.put,
            "DELETE": requests.delete,
        }
        response: requests.Response = d[method](
            f"{self.url}{route}", headers=headers, json=json_data
        )
        log_and_raise_for_status(response)
        return response

    def _is_token_expired(self):
        if self.token is None or self.token_dt is None:
            return True
        dt_ttl = datetime.now(timezone.utc) - timedelta(seconds=self.token_ttl)
        return self.token_dt < dt_ttl

    def _sign_in(self):
        json_data = {"username": self.username, "password": self.password}
        response: requests.Response = self._fetch("POST", "/sign_in", json_data=json_data)
        self.token = response.json()["token"]
        self.token_dt = datetime.now(timezone.utc)

    def _signed_in_fetch(self, method, route, json_data=None):
        if self.api_token:
            self.token = self.api_token
        elif self._is_token_expired():
            self._sign_in()
        headers = {"Authorization": f"Bearer {self.token}"}
        return self._fetch(method, route, headers=headers, json_data=json_data)

    def create_stream(self) -> int:
        """
        Create a user stream on Albert API
        Returns the stream_id
        """
        json_data = {
            "model_name": "albert",
            "mode": "stream",
            "query": "",
            "limit": 0,
            "with_history": True,
            "context": "",
            "institution": "",
            "links": "",
            "temperature": 20,
            "sources": ["service-public"],
            "should_sids": [],
            "must_not_sids": [],
            "response": "",
            "rag_sources": [],
            "postprocessing": [],
        }
        response: requests.Response = self._signed_in_fetch("POST", "/stream", json_data=json_data)
        return int(response.json()["stream_id"])

    def get_stream(self, stream_id: int) -> dict:
        # Get stream data
        response: requests.Response = self._signed_in_fetch("GET", f"/stream/{stream_id}")
        stream = response.json()
        return stream
