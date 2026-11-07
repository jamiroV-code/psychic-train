"""Lazy unauthenticated static sentinel; called only at an X unit boundary.

The caller supplies the next selected account's admitted route/policy, never an
account or cookies. Missing admission cannot fall back to direct. Off is inert.
"""
from __future__ import annotations

import hashlib
import re

from api.data.attention import web_queries, x_proxy as p, x_queryids as q


async def static_get(route, policy, url):
    from api.data.attention.x_proxy_runtime import one_shot
    p.require(url == q.EMBED_URL or isinstance(url, str) and re.fullmatch(
        re.escape(q.STATIC_BASE) + r"[a-f0-9]{7,32}\.js", url) is not None, "proxy_policy")
    return await one_shot(route, policy, url, q.BUNDLE_LIMIT,
                         headers={"user-agent": web_queries.HONEST_USER_AGENT})


def run_check(config, *, cache_root, now, route=None, policy=None, get=static_get):
    """One bounded discovery+bundle check. Charge before each GET across restarts.

    Must run on the collector's synchronous single-writer unit boundary. The
    upstream selector owns admission and never passes a stale account route.
    """
    if config.x_queryid_mode == "off":
        return None
    if config.x_queryid_mode not in ("sentinel", "auto"):
        raise ValueError("invalid query-id mode")
    configured = config.x_proxy_required or any(getattr(config, key) is not None for key in
        ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path"))
    if not configured and (route is not None or policy is not None):
        raise ValueError("unexpected static route")
    path = q.state_path(cache_root)
    state = q.load(path)
    if state["budget"]["day"] != now.date().isoformat():
        state["budget"] = {"day": now.date().isoformat(), "used": 0}
    if configured:
        if route is None or policy is None:
            return state
        try:
            policy.validate_url(q.EMBED_URL)
            policy.validate_url(q.bundle_url("0" * 16))
        except p.ProxyFailure:
            state = q.apply_check(state, now, outcome="refused_by_policy")
            q.save(path, state)
            return state
    if state["budget"]["used"] + 2 > config.x_queryid_static_budget_per_day:
        return state

    async def check():
        nonlocal state
        async def fetch(url):
            state["budget"]["used"] += 1
            q.save(path, state)
            return await get(route, policy, url)
        try:
            html = await fetch(q.EMBED_URL)
        except Exception:
            return q.apply_check(state, now, outcome="blocked")
        try:
            if not isinstance(html, bytes) or len(html) > q.BUNDLE_LIMIT:
                raise ValueError("static size")
            name = q.bundle_hash(html.decode("utf-8"))
            if name is None:
                raise ValueError("static discovery")
        except (ValueError, UnicodeError):
            return q.apply_check(state, now, outcome="malformed")
        try:
            body = await fetch(q.bundle_url(name))
        except Exception:
            return q.apply_check(state, now, outcome="blocked")
        try:
            if not isinstance(body, bytes) or len(body) > q.BUNDLE_LIMIT:
                raise ValueError("static size")
            mapping = q.parse_bundle(body.decode("utf-8"))
            if mapping is None:
                raise ValueError("static grammar")
        except (ValueError, UnicodeError):
            return q.apply_check(state, now, outcome="malformed")
        return q.apply_check(state, now, outcome="ok", mapping=mapping, sha256=hashlib.sha256(body).hexdigest())

    import asyncio
    state = asyncio.run(check())
    q.save(path, state)
    return state
