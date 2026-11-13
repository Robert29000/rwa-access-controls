"""HTTP session with a per-instance request pace and retries."""

import logging
import time

import requests

log = logging.getLogger(__name__)

RATE_LIMIT_MARKERS = ("rate limit", "max calls per sec", "too many requests")


class RateLimitedSession:
    """Wraps requests.Session. Keeps at least `min_interval` seconds between requests.

    requests reads HTTPS_PROXY and REQUESTS_CA_BUNDLE from the environment.
    """

    def __init__(self, min_interval: float, retries: int = 5, timeout: float = 30.0):
        self.min_interval = min_interval
        self.retries = retries
        self.timeout = timeout
        self._session = requests.Session()
        self._last = 0.0

    def _wait(self) -> None:
        delay = self._last + self.min_interval - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()

    def request_json(self, method: str, url: str, **kwargs) -> dict | list:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self._wait()
            try:
                resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
            else:
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                else:
                    resp.raise_for_status()
                    body = resp.json()
                    if not _is_rate_limited(body):
                        return body
                    last_error = RuntimeError(f"rate limited: {str(body)[:200]}")
            backoff = 2**attempt
            log.debug("retry %s %s in %ss: %s", method, url, backoff, last_error)
            time.sleep(backoff)
        raise RuntimeError(f"{method} {url} failed after {self.retries} attempts: {last_error}")

    def get_json(self, url: str, params: dict | None = None) -> dict | list:
        return self.request_json("GET", url, params=params)

    def post_json(self, url: str, payload: dict | list) -> dict | list:
        return self.request_json("POST", url, json=payload)


def _is_rate_limited(body) -> bool:
    """True for an API error about the request rate.

    Look only at error text: `message`, a string `result` and `error.message`.
    A successful result (for example verified source code) can contain the words
    "rate limit", so a list or object `result` is not examined.
    """
    if not isinstance(body, dict):
        return False
    result = body.get("result")
    text = f"{body.get('message', '')} {result if isinstance(result, str) else ''}".lower()
    if isinstance(body.get("error"), dict):
        text += " " + str(body["error"].get("message", "")).lower()
    return any(marker in text for marker in RATE_LIMIT_MARKERS)
