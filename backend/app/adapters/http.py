"""Shared HTTP session for the public sports APIs."""

import time

import requests

TIMEOUT = 30
RETRIES = 2

session = requests.Session()
session.headers["User-Agent"] = "trade-superstars/dev"

BROWSER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _get(url: str, params: dict | None = None, headers: dict | None = None):
    """GET, retrying once. Raises on persistent failure."""
    last = None
    for attempt in range(RETRIES):
        try:
            response = session.get(
                url, params=params, headers=headers, timeout=TIMEOUT
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(1)
    raise RuntimeError(f"GET {url} failed: {last}")


def get_json(url: str, params: dict | None = None) -> dict:
    return _get(url, params).json()


def get_text(url: str) -> str:
    """HTML GET. Public pages refuse the dev agent, so send a browser one."""
    return _get(url, headers={"User-Agent": BROWSER_AGENT}).text
