"""Deterministic, in-memory Reddit surface proposals and explicit publication.

Bodies are never written. Bootstrap executors call propose() while captures are
still in memory, then write_candidate(). CLI surface-propose displays that
validated candidate; --approve-surface publishes it, preserving sibling sections.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl

from api.data.attention import reddit_surface as rs
from api.data.attention.x_proxy_private import atomic_json, state_lock


@dataclass(frozen=True)
class Capture:
    url: str = field(repr=False)
    method: str
    status: int
    content_type: str
    body: bytes = field(repr=False)
    request_body: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True)
class Proposal:
    name: str
    section: dict | None
    reasons: tuple = ()
    stats: dict = field(default_factory=dict)

    @property
    def ok(self):
        return self.section is not None and not self.reasons

    def public(self):
        return {'section': self.name, 'ok': self.ok, 'reasons': list(self.reasons), 'stats': self.stats,
                'candidate_hosts': self.section['hosts'] if self.section else [],
                'revision': self.section['revision'] if self.section else None,
                'section_sha256': self.section['sha256'] if self.section else None}


class Refusal(ValueError):
    pass


def url_pattern(url, subreddits=()):
    u = urlsplit(url)
    parts = u.path.split('/')
    for i, p in enumerate(parts):
        if p in subreddits or any(c.isdigit() for c in p) or (i > 0 and parts[i-1] == 'comments'):
            parts[i] = '*'
    return '/'.join(parts) + ('*' if u.query else '')


def _leaves(node, path='', depth=0):
    if depth > 12:
        raise Refusal('unsupported_format')
    if isinstance(node, dict):
        for k, v in node.items():
            if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,63}', k):
                yield from _leaves(v, path + '/' + k, depth + 1)
    elif not isinstance(node, list):
        yield path, node


def _arrays(node, path='', depth=0):
    if depth > 10:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,63}', k):
                yield from _arrays(v, path + '/' + k, depth + 1)
    elif isinstance(node, list):
        if node and all(isinstance(v, dict) for v in node):
            yield path + '/[*]', node
        if len(node) <= 4:
            for i, v in enumerate(node):
                yield from _arrays(v, path + '/' + str(i), depth + 1)


def _pick(rows, field, aliases, valid):
    maps = [dict(_leaves(row)) for row in rows]
    paths = set.intersection(*(set(m) for m in maps)) if maps else set()
    paths = [p for p in paths if valid([m[p] for m in maps])]
    for alias in aliases:
        exact = [p for p in paths if p.split('/')[-1] == alias]
        if exact:
            paths = exact
            break
    if not paths:
        raise Refusal('ambiguous:' + field)
    shortest = min(p.count('/') for p in paths)
    paths = [p for p in paths if p.count('/') == shortest]
    if len(paths) != 1:
        raise Refusal('ambiguous:' + field)
    return paths[0]


def _shape(rows, kind):
    strings = lambda vs: all(isinstance(v, str) for v in vs)
    fields = {}
    rules = {
        'id': (('name', 'id'), lambda vs: all(isinstance(v, str) and rs.ID_RE.fullmatch(v) for v in vs)),
        'subreddit': (('subreddit', 'subreddit_name'), strings),
        'created': (('created_utc', 'created', 'createdAt'), lambda vs: all(type(v) in (int, float) for v in vs)),
        'author': (('author', 'author_name'), lambda vs: all(v is None or isinstance(v, str) for v in vs)),
        'text': (('selftext', 'body', 'text'), strings),
    }
    if kind == 'comment':
        rules['parent_id'] = (('parent_id', 'parentId'), lambda vs: all(isinstance(v, str) and rs.ID_RE.fullmatch(v) for v in vs))
    else:
        rules['num_comments'] = (('num_comments', 'commentCount'), lambda vs: all(type(v) is int and v >= 0 for v in vs))
    for name, (aliases, valid) in rules.items():
        fields[name] = {'pointer': _pick(rows, name, aliases, valid)}
    fields['kind'] = {'const': kind}
    stamp = rs.resolve(rows[0], rs.parse_pointer(fields['created']['pointer']))
    fields['created']['transform'] = 'epoch_ms' if stamp > 100_000_000_000 else 'epoch_s'
    for alias, expected in (('is_truncated', False), ('truncated', False), ('text_complete', True), ('is_complete', True)):
        try:
            ptr = _pick(rows, 'text_complete', (alias,), lambda vs: all(type(v) is bool and v == expected for v in vs))
            if ptr.split('/')[-1] != alias:
                continue
            flag = {'pointer': ptr}
            if not expected:
                flag['transform'] = 'bool_not'
            fields['text_complete'] = {'flag': flag}
            break
        except Refusal:
            pass
    if 'text_complete' not in fields:
        raise Refusal('unsupported_format')
    return fields


def _items(docs):
    choices = []
    for path, first in _arrays(docs[0]):
        try:
            rows = [r for d in docs for r in rs.resolve_all(d, rs.parse_pointer(path, wildcards=True))]
        except rs.SurfaceError:
            continue
        for prefix, kind in (('t1_', 'comment'), ('t3_', 'post')):
            selected = [r for r in rows if any(isinstance(v, str) and v.startswith(prefix) and rs.ID_RE.fullmatch(v)
                                             for _, v in _leaves(r))]
            if not selected:
                continue
            where = None
            if len(selected) != len(rows):
                # Closed discriminator values only, never an observed author/name/body value.
                tag = 't1' if kind == 'comment' else 't3'
                try:
                    pointer = _pick(selected, 'kind', ('kind',), lambda vs: all(v == tag for v in vs))
                except Refusal:
                    continue
                where = {'pointer': pointer, 'op': 'eq', 'value': tag}
            choices.append((kind, path, selected, where))
    comments = [v for v in choices if v[0] == 'comment']
    choices = comments or choices
    if len(choices) != 1:
        raise Refusal('ambiguous:items')
    return choices[0]


def _cursor(docs, item_path, captures):
    maps = [dict(_leaves(d)) for d in docs]
    # Root list responses require concrete index traversal for their continuation.
    if isinstance(docs[0], list):
        maps = [{f'/{i}' + p: v for i, part in enumerate(d) for p, v in _leaves(part)} for d in docs]
    candidates = set.intersection(*(set(m) for m in maps))
    candidates = [p for p in candidates if p.split('/')[-1] in ('after', 'next_cursor', 'endCursor')
                  and all(m[p] is None or isinstance(m[p], str) for m in maps)]
    def common(p):
        a, b = p.split('/'), item_path.split('/')
        n = 0
        for x, y in zip(a, b):
            if x != y:
                break
            n += 1
        return n
    if not candidates:
        raise Refusal('ambiguous:cursor')
    score = max(common(p) for p in candidates)
    candidates = [p for p in candidates if common(p) == score]
    if len(candidates) != 1:
        raise Refusal('ambiguous:cursor')
    ptr = candidates[0]
    # Longest linked page chain, not the sum of links across unrelated subreddit chains.
    placement, length = None, [1] * max(len(maps), len(captures))
    for i, m in enumerate(maps):
        value = m[ptr]
        if value is None:
            continue
        for j, later in enumerate(captures[i+1:], i + 1):
            hits = [k for k, v in parse_qsl(urlsplit(later.url).query) if v == value]
            if len(hits) == 1:
                found = 'query:' + hits[0]
                if placement is not None and placement != found:
                    raise Refusal('ambiguous:cursor')
                placement = found
                length[j] = max(length[j], length[i] + 1)
                break
    return {'next_cursor': ptr, 'has_more': None, 'request_cursor': placement or 'query:after'}, max(length)


def propose(name, captures, *, subreddits=(), refused_hosts=None, current=None):
    if name not in ('browser', 'gql_anon', 'x_session'):
        raise ValueError('section_invalid')
    hosts = list((current or {}).get('hosts', [] if name == 'x_session' else ['www.reddit.com']))
    hosts += sorted(h for h in (refused_hosts or {}) if isinstance(h, str) and rs.HOST_RE.fullmatch(h) and h not in hosts)
    section = {'revision': (current or {}).get('revision', 0) + 1, 'hosts': hosts}
    if not 1 <= len(hosts) <= rs.MAX_HOSTS:
        return Proposal(name, None, ('hosts_invalid',))
    if name == 'x_session':
        section['sha256'] = rs.section_sha256(section)
        return Proposal(name, section)
    groups = {}
    for c in captures:
        if c.status != 200 or 'json' not in c.content_type or len(c.body) > rs.MAX_BODY_BYTES_CAP:
            continue
        try:
            doc = json.loads(c.body)
        except ValueError:
            continue
        key = (c.method, url_pattern(c.url, subreddits))
        groups.setdefault(key, []).append((c, doc))
    if not groups:
        return Proposal(name, None, ('unsupported_format',))
    reasons, endpoints = [], []
    stats = {'posts': 0, 'comments': 0, 'chain_pages': 0}
    matched = []
    for (method, pattern), pairs in sorted(groups.items()):
        caps, docs = zip(*pairs)
        try:
            kind, path, rows, where = _items(docs)
            fields = _shape(rows, kind)
            cont, chain = _cursor(docs, path, caps)
            lane = 'comments' if kind == 'comment' else 'posts'
            items = {'path': path}
            if where:
                items['where'] = where
            ep = {'name': lane + '_' + str(len(endpoints)), 'lane': lane,
                  'match': {'method': method, 'url': pattern}, 'items': items, 'fields': fields, 'continuation': cont}
            endpoints.append(ep)
            matched.append((ep, caps))
            stats[lane] += len(rows)
            stats['chain_pages'] = max(stats['chain_pages'], chain)
        except Refusal as exc:
            reasons.append(str(exc))
    if stats['posts'] + stats['comments'] < 30:
        reasons.append('too_few_items')
    if stats['chain_pages'] < 2:
        reasons.append('no_cursor_chain')
    if not stats['comments']:
        reasons.append('no_comments_lane')
    if not stats['posts']:
        reasons.append('no_posts_lane')
    section.update(body_format='json', max_body_bytes=max(rs.DEFAULT_MAX_BODY_BYTES, max(len(c.body) for c in captures)),
                   endpoints=endpoints)
    section['sha256'] = rs.section_sha256(section)
    if not reasons:
        try:
            parsed = rs.load_section(name, section)
            for ep, caps in matched:
                endpoint = next(e for e in parsed.endpoints if e.name == ep['name'])
                for c in caps:
                    rs.extract_page(parsed, endpoint, status=c.status, content_type=c.content_type, body=c.body)
        except (rs.SurfaceInvalid, rs.SurfaceError) as exc:
            reasons.append(exc.reason)
    return Proposal(name, None if reasons else section, tuple(sorted(set(reasons))), stats)


def candidate_path(cache_root, name):
    if name not in ('browser', 'gql_anon', 'x_session'):
        raise ValueError('section_invalid')
    return Path(cache_root) / 'attention' / '_probes' / ('surface_candidate_' + name + '.json')


def write_candidate(cache_root, proposal):
    if not proposal.ok:
        raise ValueError('proposal_refused')
    atomic_json(candidate_path(cache_root, proposal.name),
                {'name': proposal.name, 'section': proposal.section, 'stats': proposal.stats})


def _read_candidate(cache_root, name):
    try:
        doc = json.loads(candidate_path(cache_root, name).read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise Refusal('no_candidate') from None
    except (OSError, ValueError):
        raise Refusal('candidate_invalid') from None
    try:
        section = doc['section']
        if doc['name'] != name or section['sha256'] != rs.section_sha256(section):
            raise ValueError()
        if name != 'x_session':
            rs.load_section(name, section)
        elif (set(section) != {'hosts', 'revision', 'sha256'} or type(section['revision']) is not int
              or section['revision'] < 1 or not 1 <= len(section['hosts']) <= 16
              or not all(rs.HOST_RE.fullmatch(h) for h in section['hosts'])):
            raise ValueError()
        return Proposal(name, section, stats=doc['stats'])
    except (KeyError, TypeError, ValueError):
        raise Refusal('candidate_invalid') from None


def main(argv=None, *, cache_root=None, surface_path=None, out=sys.stdout):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=('surface-propose',))
    parser.add_argument('--section', choices=('browser', 'gql_anon', 'x_session'), default='browser')
    parser.add_argument('--approve-surface', choices=('browser', 'gql_anon', 'x_session'))
    parser.add_argument('--surface-path', type=Path)
    args = parser.parse_args(argv)
    if cache_root is None:
        from api.data.cache import CACHE_ROOT
        cache_root = CACHE_ROOT
    name = args.approve_surface or args.section
    surface_path = args.surface_path or surface_path
    try:
        if args.approve_surface and surface_path is None:
            raise Refusal('surface_path_unset')
        p = _read_candidate(cache_root, name)
        if not args.approve_surface:
            result = p.public()
        else:
            surface_path = Path(surface_path)
            with state_lock(surface_path):
                if surface_path.exists():
                    document = json.loads(surface_path.read_text(encoding='utf-8'))
                else:
                    document = {'sections': {}}
                previous = document['sections'].get(name, {}).get('revision', 0)
                if p.section['revision'] != previous + 1:
                    raise Refusal('candidate_stale')
                document['sections'][name] = p.section
                atomic_json(surface_path, document)
                candidate_path(cache_root, name).unlink()
            result = {'section': name, 'state': 'published', 'revision': p.section['revision'],
                      'section_sha256': p.section['sha256']}
    except (Refusal, OSError, ValueError, KeyError) as exc:
        result = {'section': name, 'state': 'refused', 'reason': str(exc) if isinstance(exc, Refusal) else 'surface_invalid'}
    out.write(json.dumps(result, sort_keys=True) + '\n')
    return 2 if result.get('state') == 'refused' else 0


if __name__ == '__main__':
    raise SystemExit(main())
