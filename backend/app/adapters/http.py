"""Shared HTTP session for the public sports APIs."""

import time

import requests

TIMEOUT = 30
RETRIES = 2

session = requests.Session()
session.headers["User-Agent"] = "trade-superstars/dev"


def get_json(url: str, params: dict | None = None) -> dict:
    """GET returning JSON, retrying once. Raises on persistent failure."""
    last = None
    for attempt in range(RETRIES):
        try:
            response = session.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(1)
    raise RuntimeError(f"GET {url} failed: {last}")
