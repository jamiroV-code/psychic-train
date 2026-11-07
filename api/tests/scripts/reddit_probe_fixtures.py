"""Synthetic Reddit-like captures and a loopback fake driver for the probe/surface tests (no network, no browser).

Every text value carries `SECRET_MARK` so the no-value scans can prove nothing of a body leaks into records,
inventories, candidates or CLI output.
"""
from __future__ import annotations

import json

from api.scripts.surface_tool import Capture

SECRET_MARK = "zqxSECRETmark"
HOST = "https://www.reddit.com"
BASE = 1_793_000_000  # 2026-10-26 UTC, absolute epoch seconds


def _post(sub: str, n: int) -> dict:
    return {"kind": "t3", "data": {
        "name": f"t3_{sub[:2]}{n}p", "id": f"{sub[:2]}{n}p", "subreddit": sub, "created_utc": BASE - n * 60,
        "author": f"user{n}", "selftext": f"{SECRET_MARK} post {n}", "is_truncated": False, "num_comments": 2,
        "score": n}}


def _comment(parent: str, n: int) -> dict:
    return {"kind": "t1", "data": {
        "name": f"t1_c{parent[3:]}{n}", "parent_id": parent, "subreddit": "bitcoin", "created_utc": BASE - n,
        "author": None if n == 1 else f"commenter{n}", "body": f"{SECRET_MARK} comment {n}", "is_truncated": False}}


def listing(sub: str, page: int, *, per_page: int = 12, pages: int = 3) -> dict:
    start = page * per_page
    after = f"t3_{sub[:2]}{start + per_page - 1}p" if page + 1 < pages else None
    return {"kind": "Listing", "data": {"after": after, "dist": per_page,
                                        "children": [_post(sub, start + i) for i in range(per_page)]}}


def thread(sub: str, post_n: int) -> list:
    post = _post(sub, post_n)
    parent = post["data"]["name"]
    return [{"kind": "Listing", "data": {"after": None, "children": [post]}},
            {"kind": "Listing", "data": {"after": None, "children": [
                _comment(parent, 1), _comment(parent, 2),
                {"kind": "more", "data": {"count": 4, "children": ["abc"]}}]}}]


def capture(url: str, doc, *, status: int = 200, ctype: str = "application/json; charset=utf-8") -> Capture:
    return Capture(url=url, method="GET", status=status, content_type=ctype,
                   body=json.dumps(doc).encode("utf-8"))


def listing_url(sub: str, page: int) -> str:
    if page == 0:
        return f"{HOST}/svc/r/{sub}/new.json?limit=12"
    return f"{HOST}/svc/r/{sub}/new.json?limit=12&after=t3_{sub[:2]}{page * 12 - 1}p"


def bootstrap_captures(subs=("bitcoin", "ethereum"), pages: int = 3) -> list[Capture]:
    out = []
    for sub in subs:
        out += [capture(listing_url(sub, p), listing(sub, p, pages=pages)) for p in range(pages)]
    out.append(capture(f"{HOST}/svc/r/{subs[0]}/comments/{subs[0][:2]}0p.json", thread(subs[0], 0)))
    return out


class FakeDriver:
    """Loopback fake of the PR2 driver seam: listing page 0 on navigate, one more page per scroll, a thread on a
    thread navigation; optional challenge/status injection. Records every action for budget assertions."""

    def __init__(self, *, pages: int = 3, status: int = 200, challenge: bool = False, refused=None,
                 body_bytes: int | None = None):
        self.pages, self.status, self.challenge = pages, status, challenge
        self.refused = dict(refused or {})
        self.body_bytes = body_bytes
        self.actions: list[tuple[str, str]] = []
        self._pending: list[Capture] = []
        self._sub: str | None = None
        self._page = 0

    def _emit(self, url, doc):
        c = capture(url, doc, status=self.status)
        if self.body_bytes is not None:
            c = Capture(url=c.url, method=c.method, status=c.status, content_type=c.content_type,
                        body=b" " * self.body_bytes)
        self._pending.append(c)

    def navigate(self, url: str) -> str:
        self.actions.append(("navigate", url))
        if self.challenge:
            return "challenge"
        parts = url.split("/")
        sub = parts[4]
        if "/comments/" in url:
            n = int(parts[6][2:-1])
            self._emit(f"{HOST}/svc/r/{sub}/comments/{parts[6]}.json", thread(sub, n))
        else:
            self._sub, self._page = sub, 0
            self._emit(listing_url(sub, 0), listing(sub, 0, pages=self.pages))
        return "ok"

    def scroll(self) -> None:
        self.actions.append(("scroll", self._sub or ""))
        if self._sub is not None and self._page + 1 < self.pages:
            self._page += 1
            self._emit(listing_url(self._sub, self._page), listing(self._sub, self._page, pages=self.pages))

    def drain(self) -> list[Capture]:
        out, self._pending = self._pending, []
        return out

    def refused_hosts(self) -> dict:
        return dict(self.refused)
