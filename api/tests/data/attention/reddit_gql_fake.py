"""In-process fake of the anonymous GraphQL surface (S-RGQL), shaped after the public Redlib fork sources
(`Nachtalb/redlib` `src/backends/gql.rs`, `src/oauth.rs`; REF `collector-identity-pool-gql-shapes_REF_07-11-26.md`).
No socket, no network: it is the `Transport` callable the method is handed. Every value is synthetic.

Token mint: POST `www.reddit.com/auth/v2/oauth/access-token/loid` with `Authorization: Basic base64(<client id>:)`
-> `{"access_token", "expires_in"}`. Operations: POST `gql-fed.reddit.com/` with `operationName`, `variables` and a
persisted-query hash; `SubredditFeedElements` (sort NEW, `pageSize`, base64 `after`) -> `data.postFeed.elements
{edges[].node, pageInfo{hasNextPage, endCursor}}`; `PostComments` (`id` t3, `after`) -> `data.postInfoById.
commentForest{trees[]{depth, parentId, node}, pageInfo}`. A comment node carrying its subreddit name is a FIXTURE
assumption the real PR1 capture must confirm (B2: a misfit is `schema_mismatch`, never data).
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from api.data.attention import reddit_gql as rg

CLIENT_ID = "FakeAppId_0123"
HASH_FEED = "a" * 64
HASH_COMMENTS = "b" * 64
TOKEN_PATH = "/auth/v2/oauth/access-token/loid"
GQL_HOST = "gql-fed.reddit.com"
AUTH_HOST = "www.reddit.com"


def section_raw(**over) -> dict:
    post_fields = {
        "id": {"pointer": "/node/id"}, "kind": {"const": "post"}, "subreddit": {"pointer": "/node/subreddit/name"},
        "created": {"pointer": "/node/createdAt", "transform": "iso_utc"},
        "author": {"pointer": "/node/authorInfo/name"},
        "text": {"pointers": ["/node/title", "/node/content/markdown"], "transform": "join:\n"},
        "text_complete": {"selftext_full": True}, "num_comments": {"pointer": "/node/commentCount"}}
    comment_fields = {
        "id": {"pointer": "/node/id"}, "kind": {"const": "comment"},
        "subreddit": {"pointer": "/node/subredditName"},
        "created": {"pointer": "/node/createdAt", "transform": "iso_utc"},
        "author": {"pointer": "/node/authorInfo/name"}, "text": {"pointer": "/node/content/markdown"},
        "text_complete": {"selftext_full": True}, "parent_id": {"pointer": "/parentId"}}
    raw = {
        "revision": 1, "hosts": [GQL_HOST, AUTH_HOST], "body_format": "json", "max_body_bytes": 1024 * 1024,
        "endpoints": [
            {"name": "feed_new", "lane": "posts",
             "match": {"method": "POST", "url": "/",
                       "operation": {"pointer": "/operationName", "equals": "SubredditFeedElements"}},
             "items": {"path": "/data/postFeed/elements/edges/[*]",
                       "where": {"pointer": "/node/__typename", "op": "eq", "value": "SubredditPost"}},
             "fields": post_fields,
             "continuation": {"next_cursor": "/data/postFeed/elements/pageInfo/endCursor",
                              "has_more": "/data/postFeed/elements/pageInfo/hasNextPage",
                              "request_cursor": "body:/variables/after"}},
            {"name": "post_comments", "lane": "comments",
             "match": {"method": "POST", "url": "/",
                       "operation": {"pointer": "/operationName", "equals": "PostComments"}},
             "items": {"path": "/data/postInfoById/commentForest/trees/[*]",
                       "where": {"pointer": "/node/__typename", "op": "eq", "value": "Comment"}},
             "fields": comment_fields,
             "continuation": {"next_cursor": "/data/postInfoById/commentForest/pageInfo/endCursor",
                              "has_more": "/data/postInfoById/commentForest/pageInfo/hasNextPage",
                              "request_cursor": "body:/variables/after"}}],
        "requests": requests_raw(),
    }
    raw.update(over)
    return raw


def requests_raw() -> dict:
    android = {"Content-Type": "application/json; charset=UTF-8", "x-reddit-compression": "1",
               "client-vendor-id": "00000000-0000-4000-8000-000000000000"}
    return {
        "client_id": CLIENT_ID,
        "token": {"host": AUTH_HOST, "method": "POST", "path": TOKEN_PATH, "header_template": dict(android),
                  "body_template": {"scopes": ["*", "email", "pii"]}, "token_pointer": "/access_token",
                  "expires_pointer": "/expires_in"},
        "operations": {
            "posts": {"host": GQL_HOST, "method": "POST", "path": "/",
                      "header_template": {**android, "Authorization": "Bearer {token}",
                                          "X-APOLLO-OPERATION-NAME": "SubredditFeedElements"},
                      "body_template": {"extensions": {"persistedQuery": {"version": 1, "sha256Hash": HASH_FEED}}},
                      "operationName": "SubredditFeedElements",
                      "variables_template": {"subredditName": "{subreddit}", "sort": "NEW", "pageSize": "{limit}",
                                             "includeSubredditInPosts": True, "after": "{after}"}},
            "comments": {"host": GQL_HOST, "method": "POST", "path": "/",
                         "header_template": {**android, "Authorization": "Bearer {token}",
                                             "X-APOLLO-OPERATION-NAME": "PostComments"},
                         "body_template": {"extensions": {"persistedQuery": {"version": 1,
                                                                             "sha256Hash": HASH_COMMENTS}}},
                         "operationName": "PostComments",
                         "variables_template": {"id": "{post_id}", "sortType": "NEW", "count": 200, "maxDepth": 10,
                                                "after": "{after}"}}},
    }


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


@dataclass
class FakeGql:
    """Posts and comments by subreddit; behaviour switches for every failure the method must survive."""
    now: datetime
    posts: list = field(default_factory=list)  # (id, sub, created, author, title, body)
    comments: list = field(default_factory=list)  # (id, post id, sub, created, author, body)
    page_size: int = 5
    comment_page: int = 2
    ttl: int = 3600
    token_status: int = 200
    stale_hash: bool = False
    block_after: int | None = None  # answer a 403 HTML block page after this many operation calls
    empty_shell: bool = False
    expire_tokens_after: int | None = None  # a token is rejected (401) after this many uses
    calls: list = field(default_factory=list)
    mints: int = 0
    seen_headers: list = field(default_factory=list)
    _tokens: dict = field(default_factory=dict)

    def num_comments(self, pid: str) -> int:
        return sum(1 for c in self.comments if c[1] == pid and c[3] <= self.now)

    def __call__(self, method: str, url: str, headers: dict, body: bytes | None) -> rg.Response:
        self.calls.append((method, url))
        self.seen_headers.append(dict(headers))
        if url == f"https://{AUTH_HOST}{TOKEN_PATH}":
            return self._mint(headers, body)
        assert url == f"https://{GQL_HOST}/" and method == "POST"
        auth = headers.get("Authorization", "")
        token = auth[len("Bearer "):] if auth.startswith("Bearer ") else None
        if token not in self._tokens:
            return self._json(401, {"error": "invalid_token"})
        self._tokens[token] += 1
        if self.expire_tokens_after is not None and self._tokens[token] > self.expire_tokens_after:
            return self._json(401, {"error": "invalid_token"})
        ops = sum(1 for _, u in self.calls if u.startswith(f"https://{GQL_HOST}"))
        if self.block_after is not None and ops > self.block_after:
            return rg.Response(403, "text/html", b"<html>blocked</html>")
        if self.empty_shell:
            return rg.Response(200, "application/json", b"")
        doc = json.loads(body)
        if self.stale_hash:
            return self._json(200, {"errors": [{"message": "PersistedQueryNotFound"}], "data": None})
        if doc["operationName"] == "SubredditFeedElements":
            return self._json(200, self._feed(doc["variables"]))
        return self._json(200, self._comments(doc["variables"]))

    def _json(self, status: int, doc) -> rg.Response:
        return rg.Response(status, "application/json; charset=utf-8", json.dumps(doc).encode())

    def _mint(self, headers, body) -> rg.Response:
        want = "Basic " + base64.b64encode(f"{CLIENT_ID}:".encode()).decode()
        if headers.get("Authorization") != want or json.loads(body) != {"scopes": ["*", "email", "pii"]}:
            return self._json(401, {"error": "bad_client"})
        if self.token_status != 200:
            return self._json(self.token_status, {"error": "nope"})
        self.mints += 1
        token = f"faketoken.{self.mints:04d}.abcdefghijklmnop"
        self._tokens[token] = 0
        return self._json(200, {"access_token": token, "token_type": "bearer", "expires_in": self.ttl,
                                "scope": "*"})

    def _feed(self, v) -> dict:
        rows = sorted((p for p in self.posts if p[1] == v["subredditName"] and p[2] <= self.now),
                      key=lambda p: p[2], reverse=True)
        start = 0
        if v.get("after"):
            last = base64.b64decode(v["after"]).decode()
            start = next(i for i, p in enumerate(rows) if p[0] == last) + 1
        size = min(int(v["pageSize"]), self.page_size)
        chunk = rows[start:start + size]
        edges = [{"node": {"__typename": "SubredditPost", "id": i, "title": title, "createdAt": iso(c),
                           "authorInfo": {"name": a}, "subreddit": {"name": s}, "commentCount": self.num_comments(i),
                           "content": {"markdown": text}}} for i, s, c, a, title, text in chunk]
        if start == 0:
            edges.insert(1, {"node": {"__typename": "AdPost", "id": "t3_ad"}})  # never an item
        more = start + size < len(rows)
        cursor = base64.b64encode(chunk[-1][0].encode()).decode() if chunk else None
        return {"data": {"postFeed": {"elements": {"edges": edges,
                                                   "pageInfo": {"hasNextPage": more, "endCursor": cursor}}}}}

    def _comments(self, v) -> dict:
        rows = sorted((c for c in self.comments if c[1] == v["id"] and c[3] <= self.now), key=lambda c: c[0])
        start = int(v["after"]) if v.get("after") else 0
        chunk = rows[start:start + self.comment_page]
        more = start + self.comment_page < len(rows)
        trees = [{"depth": 0, "parentId": p, "node": {"__typename": "Comment", "id": i, "subredditName": s,
                                                      "createdAt": iso(c), "authorInfo": {"name": a},
                                                      "content": {"markdown": b}}}
                 for i, p, s, c, a, b in chunk]
        return {"data": {"postInfoById": {"id": v["id"], "commentForest": {
            "trees": trees, "pageInfo": {"hasNextPage": more, "endCursor": str(start + self.comment_page)}}}}}


def advance(fake: FakeGql, hours: float) -> datetime:
    fake.now = fake.now + timedelta(hours=hours)
    return fake.now
