"""Minimal Codeforces API client with request pacing and retries.

Codeforces allows roughly one request every two seconds per client. All calls in
this process share one lock so concurrent syncs never exceed that pace.
"""

import threading
import time

import httpx

from . import config


class CodeforcesError(Exception):
    """Raised when Codeforces returns FAILED or cannot be reached."""


class HandleNotFound(CodeforcesError):
    pass


_lock = threading.Lock()
_last_call = 0.0


def _paced_get(client: httpx.Client, method: str, params: dict) -> dict:
    global _last_call
    with _lock:
        wait = config.CF_MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = client.get(f"{config.CF_API}/{method}", params=params)
        finally:
            _last_call = time.monotonic()
    try:
        return resp.json()
    except ValueError as exc:
        raise CodeforcesError(f"{method}: HTTP {resp.status_code}, not JSON") from exc


def call(method: str, retries: int = 4, timeout: float = 60.0, **params) -> object:
    """Call a Codeforces API method and return its `result` field."""
    delay = 2.0
    last_error = "unknown error"
    with httpx.Client(timeout=timeout, headers={"User-Agent": "upsolve-course-project/1.0"}) as client:
        for _ in range(retries):
            try:
                body = _paced_get(client, method, params)
            except (httpx.HTTPError, CodeforcesError) as exc:
                last_error = str(exc)
                time.sleep(delay)
                delay *= 2
                continue
            if body.get("status") == "OK":
                return body["result"]
            comment = body.get("comment", "")
            if "not found" in comment.lower():
                raise HandleNotFound(comment)
            if "limit exceeded" in comment.lower():
                last_error = comment
                time.sleep(delay)
                delay *= 2
                continue
            raise CodeforcesError(f"{method}: {comment}")
    raise CodeforcesError(f"{method}: {last_error}")


def user_info(handles: list[str]) -> list[dict]:
    return call("user.info", handles=";".join(handles))


def user_status(handle: str, start: int = 1, count: int | None = None) -> list[dict]:
    params = {"handle": handle, "from": start}
    if count:
        params["count"] = count
    return call("user.status", timeout=120.0, **params)


def user_rating(handle: str) -> list[dict]:
    return call("user.rating", handle=handle)


def problemset() -> dict:
    return call("problemset.problems", timeout=120.0)


def contest_rating_changes(contest_id: int) -> list[dict]:
    return call("contest.ratingChanges", contestId=contest_id, timeout=120.0)


def contest_list() -> list[dict]:
    return call("contest.list", gym="false")
