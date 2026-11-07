"""Finish plan contract B1-B2, B6: the Reddit surface grammar engine (finite grammar v1). Pure; no network, no I/O
beyond reading the surface file.

A surface section (`browser`, `gql_anon`) of the file at `reddit_surface_path` SELECTS among the constructs coded
here; it can never supply parser code. Supported body format: `json` only (anything else is `unsupported_format`).
Per section: `revision`, `hosts`, `max_body_bytes` (default 262144, hard cap 2 MiB), `sha256` (of the canonical
section without the `sha256` key), `body_format` and `endpoints`. Per endpoint:
- `match`: `method` + URL glob over path and query (only `*`; the host comes from the section's `hosts`) and an
  optional `operation` equality (`pointer` into the request-body JSON, `equals`);
- `items`: a JSON pointer whose `[*]` segments iterate arrays (depth <= 12, <= 2 wildcards), an optional single
  `where` predicate (`eq|exists|startswith` on one pointer) and an optional `discriminator` union (alternative item
  shapes keyed by one pointer's value);
- `fields` (per shape under a discriminator): `id`, `kind` (`post|comment`, a pointer or `const`), `subreddit`,
  `created`, `author` (optional `deleted_pointer`), `text`, `text_complete`, and optional `parent_id`,
  `num_comments`;
- `continuation`: `next_cursor` pointer, `has_more` pointer (or null), `request_cursor` placement from the closed set
  `query:<key>`, `body:<pointer>`, `path:<segment index>`.
Closed transform list: `identity`, `epoch_s`, `epoch_ms`, `iso_utc`, `lower`, `strip_prefix:<literal <= 8>`,
`to_int`, `bool_not`, `join:<sep <= 2>` (<= 4 pointers, `text` only). Full text is proven only by exactly one of a
`flag` (true means complete), a `declared_length` equal to the text length, or `selftext_full`; a section without one
is `unsupported_format`. Bounds: <= 200 pointers and <= 64 KiB per section.

Fail closed (B2): a missing mandatory field, a wrong type, preview text, an id not `t3_/t1_[a-z0-9]{1,16}`, a
timestamp that is not absolute, or an unsupported format raises `SurfaceError`; the lane is then
`schema_mismatch`/`unsupported_format`, never a zero and never partial data. Extracted `RawItem`s hold the text
in memory only (never in a repr); `reddit_core.reduce_item` reduces them at once.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from api.data.attention.web_queries import SUBREDDIT_RE

SECTIONS = ("browser", "gql_anon")
BODY_FORMATS = ("json",)
DEFAULT_MAX_BODY_BYTES = 262_144
MAX_BODY_BYTES_CAP = 2 * 1024 * 1024
MAX_SECTION_BYTES = 64 * 1024
MAX_POINTERS = 200
MAX_DEPTH = 12
MAX_WILDCARDS = 2
MAX_ENDPOINTS = 8
MAX_HOSTS = 16
WILDCARD = "[*]"
ID_RE = re.compile(r"t[13]_[a-z0-9]{1,16}")
HOST_RE = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+")
NAME_RE = re.compile(r"[a-z0-9_]{1,32}")
SHA_RE = re.compile(r"[0-9a-f]{64}")
QUERY_KEY_RE = re.compile(r"[A-Za-z0-9_.-]{1,32}")
LANES = ("posts", "comments")
KINDS = ("post", "comment")
METHODS = ("GET", "POST")
WHERE_OPS = ("eq", "exists", "startswith")
TRANSFORMS = ("identity", "epoch_s", "epoch_ms", "iso_utc", "lower", "to_int", "bool_not")
MANDATORY = ("id", "kind", "subreddit", "created", "author", "text", "text_complete")
OPTIONAL = ("parent_id", "num_comments")
# Extraction failures (lane stop reasons, a subset of `reddit_core.STOP_REASONS`).
FAILURES = ("schema_mismatch", "unsupported_format", "empty_shell", "cap", "error")


class SurfaceInvalid(ValueError):
    """The surface section is not valid grammar v1; `reason` is `unsupported_format` or `surface_invalid`."""

    def __init__(self, reason: str, key: str):
        super().__init__(f"{reason}: {key}")
        self.reason = reason


class SurfaceError(ValueError):
    """One response cannot be read through the grammar; `reason` is one of `FAILURES`. Never holds a value."""

    def __init__(self, reason: str, what: str = ""):
        assert reason in FAILURES
        super().__init__(f"{reason}: {what}" if what else reason)
        self.reason = reason


# --- pointers and transforms ---

def parse_pointer(text, *, wildcards: bool = False) -> tuple[str, ...]:
    if not isinstance(text, str) or not (text == "" or text.startswith("/")):
        raise SurfaceInvalid("surface_invalid", "pointer")
    segs = tuple(s.replace("~1", "/").replace("~0", "~") for s in text.split("/")[1:]) if text else ()
    if len(segs) > MAX_DEPTH or (segs.count(WILDCARD) and not wildcards) or segs.count(WILDCARD) > MAX_WILDCARDS:
        raise SurfaceInvalid("surface_invalid", "pointer")
    return segs


_MISSING = object()


def _step(node, seg: str):
    if isinstance(node, dict):
        return node.get(seg, _MISSING)
    if isinstance(node, list) and seg.isdigit() and (seg == "0" or not seg.startswith("0")):
        i = int(seg)
        return node[i] if i < len(node) else _MISSING
    return _MISSING


def resolve(node, segs: tuple[str, ...]):
    """The value at a wildcard-free pointer, or `_MISSING`."""
    for seg in segs:
        node = _step(node, seg)
        if node is _MISSING:
            return _MISSING
    return node


def resolve_all(node, segs: tuple[str, ...]) -> list:
    """Every value at a pointer with `[*]` segments; a missing step or a wildcard over a non-array fails closed."""
    nodes = [node]
    for seg in segs:
        nxt = []
        for n in nodes:
            if seg == WILDCARD:
                if not isinstance(n, list):
                    raise SurfaceError("schema_mismatch", "items path")
                nxt.extend(n)
            else:
                v = _step(n, seg)
                if v is _MISSING:
                    raise SurfaceError("schema_mismatch", "items path")
                nxt.append(v)
        nodes = nxt
    return nodes


def _valid_transform(t, *, join_ok: bool) -> bool:
    if not isinstance(t, str):
        return False
    if t in TRANSFORMS:
        return True
    if t.startswith("strip_prefix:"):
        return 1 <= len(t) - len("strip_prefix:") <= 8
    if t.startswith("join:"):
        return join_ok and 1 <= len(t) - len("join:") <= 2
    return False


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def apply_transform(t: str, v):
    """Apply one transform; a wrong input type is a schema mismatch (no coercion beyond the closed list)."""
    try:
        if t == "identity":
            return v
        if t in ("epoch_s", "epoch_ms"):
            if not _number(v):
                raise SurfaceError("schema_mismatch", t)
            return datetime.fromtimestamp(v / (1000.0 if t == "epoch_ms" else 1.0), tz=timezone.utc)
        if t == "iso_utc":
            if not isinstance(v, str):
                raise SurfaceError("schema_mismatch", t)
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if d.tzinfo is None:
                raise SurfaceError("schema_mismatch", t)
            return d.astimezone(timezone.utc)
        if t == "lower":
            if not isinstance(v, str):
                raise SurfaceError("schema_mismatch", t)
            return v.lower()
        if t == "to_int":
            if isinstance(v, int) and not isinstance(v, bool):
                return v
            if isinstance(v, str) and v.isdigit():
                return int(v)
            raise SurfaceError("schema_mismatch", t)
        if t == "bool_not":
            if not isinstance(v, bool):
                raise SurfaceError("schema_mismatch", t)
            return not v
        if t.startswith("strip_prefix:"):
            if not isinstance(v, str):
                raise SurfaceError("schema_mismatch", "strip_prefix")
            p = t[len("strip_prefix:"):]
            return v[len(p):] if v.startswith(p) else v
        if t.startswith("join:"):
            if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
                raise SurfaceError("schema_mismatch", "join")
            return t[len("join:"):].join(v)
    except (OverflowError, OSError, ValueError) as exc:
        if isinstance(exc, SurfaceError):
            raise
        raise SurfaceError("schema_mismatch", t) from None
    raise SurfaceError("schema_mismatch", "transform")


# --- the section ---

@dataclass(frozen=True)
class FieldSpec:
    name: str
    pointers: tuple[tuple[str, ...], ...] = ()
    transform: str = "identity"
    const: str | None = None
    deleted_pointer: tuple[str, ...] | None = None


@dataclass(frozen=True)
class FullText:
    mode: str  # "flag" | "declared_length" | "selftext_full"
    pointer: tuple[str, ...] = ()
    transform: str = "identity"


@dataclass(frozen=True)
class Shape:
    fields: dict[str, FieldSpec]
    full_text: FullText


@dataclass(frozen=True)
class Endpoint:
    name: str
    lane: str
    method: str
    url_glob: str
    url_re: re.Pattern
    operation: tuple[tuple[str, ...], str] | None
    items_path: tuple[str, ...]
    where: tuple[tuple[str, ...], str, str | None] | None
    discriminator: tuple[str, ...] | None
    shapes: dict[str | None, Shape]
    next_cursor: tuple[str, ...]
    has_more: tuple[str, ...] | None
    request_cursor: tuple[str, str]


@dataclass(frozen=True)
class Section:
    name: str
    revision: int
    hosts: tuple[str, ...]
    max_body_bytes: int
    sha256: str
    endpoints: tuple[Endpoint, ...]
    # `gql_anon` only: the raw B7 request grammar block, validated by `reddit_gql` (hash-bound with the section).
    requests: dict | None = None


def canonical(section: dict) -> bytes:
    return json.dumps({k: v for k, v in section.items() if k != "sha256"}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True).encode("ascii")


def section_sha256(section: dict) -> str:
    return hashlib.sha256(canonical(section)).hexdigest()


def _keys(d, required: set[str], optional: set[str], where: str) -> dict:
    if not isinstance(d, dict) or not required <= set(d) or set(d) - required - optional:
        raise SurfaceInvalid("surface_invalid", where)
    return d


class _Count:
    def __init__(self):
        self.n = 0

    def ptr(self, text, *, wildcards: bool = False) -> tuple[str, ...]:
        self.n += 1
        if self.n > MAX_POINTERS:
            raise SurfaceInvalid("surface_invalid", "too many pointers")
        return parse_pointer(text, wildcards=wildcards)


def _field(name: str, raw, c: _Count) -> FieldSpec:
    if name == "kind" and isinstance(raw, dict) and "const" in raw:
        _keys(raw, {"const"}, set(), "fields.kind")
        if raw["const"] not in KINDS:
            raise SurfaceInvalid("surface_invalid", "fields.kind")
        return FieldSpec(name, const=raw["const"])
    opt = {"transform"} | ({"deleted_pointer"} if name == "author" else set())
    if isinstance(raw, dict) and "pointers" in raw:
        _keys(raw, {"pointers", "transform"}, set(), f"fields.{name}")
        ps = raw["pointers"]
        if (name != "text" or not str(raw["transform"]).startswith("join:") or not isinstance(ps, list)
                or not 1 <= len(ps) <= 4 or not _valid_transform(raw["transform"], join_ok=True)):
            raise SurfaceInvalid("surface_invalid", f"fields.{name}")
        return FieldSpec(name, tuple(c.ptr(p) for p in ps), raw["transform"])
    _keys(raw, {"pointer"}, opt, f"fields.{name}")
    t = raw.get("transform", "identity")
    if not _valid_transform(t, join_ok=False):
        raise SurfaceInvalid("surface_invalid", f"fields.{name}")
    deleted = c.ptr(raw["deleted_pointer"]) if "deleted_pointer" in raw else None
    return FieldSpec(name, (c.ptr(raw["pointer"]),), t, None, deleted)


def _full_text(raw, c: _Count) -> FullText:
    if not isinstance(raw, dict) or len(raw) != 1:
        raise SurfaceInvalid("unsupported_format", "text_complete")
    (mode, v), = raw.items()
    if mode == "flag":
        _keys(v, {"pointer"}, {"transform"}, "text_complete.flag")
        t = v.get("transform", "identity")
        if t not in ("identity", "bool_not"):
            raise SurfaceInvalid("surface_invalid", "text_complete.flag")
        return FullText("flag", c.ptr(v["pointer"]), t)
    if mode == "declared_length":
        return FullText("declared_length", c.ptr(v))
    if mode == "selftext_full" and v is True:
        return FullText("selftext_full")
    raise SurfaceInvalid("unsupported_format", "text_complete")


def _shape(raw, c: _Count) -> Shape:
    if not isinstance(raw, dict) or "text_complete" not in raw:
        raise SurfaceInvalid("unsupported_format", "text_complete")
    _keys(raw, set(MANDATORY), set(OPTIONAL), "fields")
    full = _full_text(raw["text_complete"], c)
    return Shape({k: _field(k, v, c) for k, v in raw.items() if k != "text_complete"}, full)


def _glob(text) -> re.Pattern:
    if not isinstance(text, str) or not text.startswith("/") or len(text) > 512 or any(ch.isspace() for ch in text):
        raise SurfaceInvalid("surface_invalid", "match.url")
    return re.compile(".*".join(re.escape(p) for p in text.split("*")))


def _request_cursor(text, c: _Count) -> tuple[str, str]:
    if not isinstance(text, str) or ":" not in text:
        raise SurfaceInvalid("surface_invalid", "request_cursor")
    kind, arg = text.split(":", 1)
    if kind == "query" and QUERY_KEY_RE.fullmatch(arg):
        return kind, arg
    if kind == "body":
        if not c.ptr(arg):
            raise SurfaceInvalid("surface_invalid", "request_cursor")
        return kind, arg
    if kind == "path" and arg.isdigit() and 1 <= int(arg) <= MAX_DEPTH:
        return kind, arg
    raise SurfaceInvalid("surface_invalid", "request_cursor")


def _endpoint(raw, c: _Count) -> Endpoint:
    _keys(raw, {"name", "lane", "match", "items", "continuation"}, {"fields"}, "endpoint")
    if not NAME_RE.fullmatch(str(raw["name"])) or raw["lane"] not in LANES:
        raise SurfaceInvalid("surface_invalid", "endpoint")
    m = _keys(raw["match"], {"method", "url"}, {"operation"}, "match")
    if m["method"] not in METHODS:
        raise SurfaceInvalid("surface_invalid", "match.method")
    op = None
    if "operation" in m:
        o = _keys(m["operation"], {"pointer", "equals"}, set(), "match.operation")
        if not isinstance(o["equals"], str) or not 1 <= len(o["equals"]) <= 64:
            raise SurfaceInvalid("surface_invalid", "match.operation")
        op = (c.ptr(o["pointer"]), o["equals"])
    it = _keys(raw["items"], {"path"}, {"where", "discriminator"}, "items")
    path = c.ptr(it["path"], wildcards=True)
    where = None
    if "where" in it:
        w = _keys(it["where"], {"pointer", "op"}, {"value"}, "items.where")
        if w["op"] not in WHERE_OPS or (w["op"] == "exists") != ("value" not in w) or (
                "value" in w and not isinstance(w["value"], str)):
            raise SurfaceInvalid("surface_invalid", "items.where")
        where = (c.ptr(w["pointer"]), w["op"], w.get("value"))
    disc = None
    if "discriminator" in it:
        if "fields" in raw:
            raise SurfaceInvalid("surface_invalid", "fields with discriminator")
        d = _keys(it["discriminator"], {"pointer", "shapes"}, set(), "items.discriminator")
        if not isinstance(d["shapes"], dict) or not 1 <= len(d["shapes"]) <= 4:
            raise SurfaceInvalid("surface_invalid", "items.discriminator")
        disc = c.ptr(d["pointer"])
        shapes = {k: _shape(v, c) for k, v in d["shapes"].items()}
    else:
        if "fields" not in raw:
            raise SurfaceInvalid("surface_invalid", "fields")
        shapes = {None: _shape(raw["fields"], c)}
    cont = _keys(raw["continuation"], {"next_cursor", "has_more", "request_cursor"}, set(), "continuation")
    has_more = None if cont["has_more"] is None else c.ptr(cont["has_more"])
    return Endpoint(raw["name"], raw["lane"], m["method"], m["url"], _glob(m["url"]), op, path, where, disc, shapes,
                    c.ptr(cont["next_cursor"]), has_more, _request_cursor(cont["request_cursor"], c))


def load_section(name: str, raw) -> Section:
    """Validate one section of the surface file; any deviation from grammar v1 raises `SurfaceInvalid`."""
    if name not in SECTIONS or not isinstance(raw, dict):
        raise SurfaceInvalid("surface_invalid", "section")
    if len(canonical(raw)) > MAX_SECTION_BYTES:
        raise SurfaceInvalid("surface_invalid", "section size")
    _keys(raw, {"revision", "hosts", "body_format", "endpoints"},
          {"max_body_bytes", "sha256"} | ({"requests"} if name == "gql_anon" else set()), "section")
    if "requests" in raw and not isinstance(raw["requests"], dict):
        raise SurfaceInvalid("surface_invalid", "requests")
    if raw["body_format"] not in BODY_FORMATS:
        raise SurfaceInvalid("unsupported_format", "body_format")
    rev, hosts = raw["revision"], raw["hosts"]
    if isinstance(rev, bool) or not isinstance(rev, int) or rev < 1:
        raise SurfaceInvalid("surface_invalid", "revision")
    if (not isinstance(hosts, list) or not 1 <= len(hosts) <= MAX_HOSTS or len(set(hosts)) != len(hosts)
            or not all(isinstance(h, str) and HOST_RE.fullmatch(h) for h in hosts)):
        raise SurfaceInvalid("surface_invalid", "hosts")
    mb = raw.get("max_body_bytes", DEFAULT_MAX_BODY_BYTES)
    if isinstance(mb, bool) or not isinstance(mb, int) or not 1024 <= mb <= MAX_BODY_BYTES_CAP:
        raise SurfaceInvalid("surface_invalid", "max_body_bytes")
    digest = section_sha256(raw)
    if "sha256" in raw and raw["sha256"] != digest:
        raise SurfaceInvalid("surface_invalid", "sha256")
    eps = raw["endpoints"]
    if not isinstance(eps, list) or not 1 <= len(eps) <= MAX_ENDPOINTS:
        raise SurfaceInvalid("surface_invalid", "endpoints")
    c = _Count()
    endpoints = tuple(_endpoint(e, c) for e in eps)
    if len({e.name for e in endpoints}) != len(endpoints):
        raise SurfaceInvalid("surface_invalid", "endpoint names")
    return Section(name, rev, tuple(hosts), mb, digest, endpoints, copy.deepcopy(raw.get("requests")))


def load_surface(path: Path, name: str) -> Section:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SurfaceInvalid("surface_invalid", "file") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("sections"), dict) or name not in doc["sections"]:
        raise SurfaceInvalid("surface_invalid", "sections")
    return load_section(name, doc["sections"][name])


# --- requests ---

def match_request(section: Section, method: str, url: str, body: bytes | None = None) -> Endpoint | None:
    """The endpoint a captured request belongs to, or None (another host, path or operation)."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in section.hosts or parts.port not in (None, 443):
        return None
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    for ep in section.endpoints:
        if ep.method != method or not ep.url_re.fullmatch(target):
            continue
        if ep.operation is not None:
            try:
                doc = json.loads(body or b"")
            except ValueError:
                continue
            if resolve(doc, ep.operation[0]) != ep.operation[1]:
                continue
        return ep
    return None


def place_cursor(ep: Endpoint, url: str, body: dict | None, cursor: str) -> tuple[str, dict | None]:
    """The next page's request: the cursor placed where the endpoint's `request_cursor` says."""
    if not isinstance(cursor, str) or not 1 <= len(cursor) <= 256:
        raise SurfaceError("schema_mismatch", "cursor")
    kind, arg = ep.request_cursor
    parts = urlsplit(url)
    if kind == "query":
        q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != arg] + [(arg, cursor)]
        return urlunsplit(parts._replace(query=urlencode(q))), body
    if kind == "path":
        segs = parts.path.split("/")
        i = int(arg)
        if i >= len(segs):
            raise SurfaceError("schema_mismatch", "cursor path")
        segs[i] = cursor
        return urlunsplit(parts._replace(path="/".join(segs))), body
    new = copy.deepcopy(body) if isinstance(body, dict) else None
    segs = parse_pointer(arg)
    parent = resolve(new, segs[:-1]) if new is not None else _MISSING
    if not isinstance(parent, dict):
        raise SurfaceError("schema_mismatch", "cursor body")
    parent[segs[-1]] = cursor
    return url, new


# --- responses ---

@dataclass(frozen=True)
class RawItem:
    """One extracted item; `text` lives in memory only for coin matching and never appears in a repr."""
    id: str
    kind: str
    subreddit: str
    created: datetime
    author: str | None
    parent_id: str | None
    num_comments: int | None
    text: str = field(repr=False)


@dataclass(frozen=True)
class Page:
    items: tuple[RawItem, ...]
    next_cursor: str | None
    has_more: bool | None


def _json_type(content_type: str | None) -> bool:
    main = (content_type or "").split(";", 1)[0].strip().lower()
    return main == "application/json" or (main.startswith("application/") and main.endswith("+json"))


def _value(item, spec: FieldSpec, *, mandatory: bool):
    if spec.const is not None:
        return spec.const
    if spec.transform.startswith("join:"):
        vals = [resolve(item, p) for p in spec.pointers]
        if any(v is _MISSING for v in vals):
            raise SurfaceError("schema_mismatch", spec.name)
        return apply_transform(spec.transform, vals)
    v = resolve(item, spec.pointers[0])
    if v is _MISSING or v is None:
        if mandatory and not (spec.name == "author" and v is None):
            raise SurfaceError("schema_mismatch", spec.name)
        return None
    return apply_transform(spec.transform, v)


def _matches_where(item, where) -> bool:
    if where is None:
        return True
    ptr, op, val = where
    v = resolve(item, ptr)
    if op == "exists":
        return v is not _MISSING and v is not None
    if op == "eq":
        return v == val
    return isinstance(v, str) and v.startswith(val)


def _item(raw, shape: Shape) -> RawItem:
    f = shape.fields
    item_id = _value(raw, f["id"], mandatory=True)
    kind = _value(raw, f["kind"], mandatory=True)
    sub = _value(raw, f["subreddit"], mandatory=True)
    created = _value(raw, f["created"], mandatory=True)
    text = _value(raw, f["text"], mandatory=True)
    if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
        raise SurfaceError("schema_mismatch", "id")
    if kind not in KINDS or item_id[:3] != ("t3_" if kind == "post" else "t1_"):
        raise SurfaceError("schema_mismatch", "kind")
    if not isinstance(sub, str) or not SUBREDDIT_RE.fullmatch(sub):
        raise SurfaceError("schema_mismatch", "subreddit")
    if not isinstance(created, datetime) or created.tzinfo is None:
        raise SurfaceError("schema_mismatch", "created")
    if not isinstance(text, str):
        raise SurfaceError("schema_mismatch", "text")
    a = f["author"]
    deleted = a.deleted_pointer is not None and resolve(raw, a.deleted_pointer) is True
    author = None if deleted else _value(raw, a, mandatory=True)
    if author is not None and not isinstance(author, str):
        raise SurfaceError("schema_mismatch", "author")
    full = shape.full_text
    if full.mode == "flag":
        flag = resolve(raw, full.pointer)
        if flag is _MISSING or apply_transform(full.transform, flag) is not True:
            raise SurfaceError("schema_mismatch", "preview text")
    elif full.mode == "declared_length":
        n = resolve(raw, full.pointer)
        if not isinstance(n, int) or isinstance(n, bool) or n != len(text):
            raise SurfaceError("schema_mismatch", "preview text")
    parent = _value(raw, f["parent_id"], mandatory=False) if "parent_id" in f else None
    if parent is not None and (not isinstance(parent, str) or not ID_RE.fullmatch(parent)):
        raise SurfaceError("schema_mismatch", "parent_id")
    nc = _value(raw, f["num_comments"], mandatory=False) if "num_comments" in f else None
    if nc is not None and (not isinstance(nc, int) or isinstance(nc, bool) or nc < 0):
        raise SurfaceError("schema_mismatch", "num_comments")
    return RawItem(item_id, kind, sub, created.astimezone(timezone.utc), author, parent, nc, text)


def extract_page(section: Section, ep: Endpoint, *, status: int, content_type: str | None, body: bytes) -> Page:
    """Read one captured response through the grammar, all or nothing (`SurfaceError` on any failure)."""
    if status != 200:
        raise SurfaceError("error", "status")
    if len(body) > section.max_body_bytes:
        raise SurfaceError("cap", "body size")
    if not _json_type(content_type):
        raise SurfaceError("unsupported_format", "content type")
    if not body.strip():
        raise SurfaceError("empty_shell", "empty body")
    try:
        doc = json.loads(body)
    except ValueError:
        raise SurfaceError("empty_shell", "not json") from None
    if not isinstance(doc, (dict, list)):
        raise SurfaceError("empty_shell", "not a document")
    items = []
    for raw in resolve_all(doc, ep.items_path):
        if not _matches_where(raw, ep.where):
            continue
        if ep.discriminator is None:
            shape = ep.shapes[None]
        else:
            key = resolve(raw, ep.discriminator)
            if not isinstance(key, str) or key not in ep.shapes:
                raise SurfaceError("schema_mismatch", "discriminator")
            shape = ep.shapes[key]
        items.append(_item(raw, shape))
    cursor = resolve(doc, ep.next_cursor)
    cursor = None if cursor is _MISSING else cursor
    if cursor is not None and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 256):
        raise SurfaceError("schema_mismatch", "next_cursor")
    more = None
    if ep.has_more is not None:
        more = resolve(doc, ep.has_more)
        if not isinstance(more, bool):
            raise SurfaceError("schema_mismatch", "has_more")
    return Page(tuple(items), cursor, more)
