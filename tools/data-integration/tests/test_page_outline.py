"""AC-33/AC-34: page outline content, exact bounds and sanitising. Pure function, no I/O, no network."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from data_integration import parse
from data_integration.parse import ParseError, SelectorMatchedNothing, outline, render_outline

FIX = Path(__file__).parent / "fixtures_outline"
RICH = (FIX / "rich.html").read_bytes()
HOSTILE = (FIX / "hostile.html").read_bytes()
HOST = "page.example.test"


def nums(n):
    return " ".join(f"{i}.5" for i in range(1, n + 1))


def lines(body, host=HOST):
    return render_outline(outline(body, host))


# ---- AC-33 -----------------------------------------------------------------------------------------------------

def test_selector_miss_raises_subclass_with_same_message():
    with pytest.raises(SelectorMatchedNothing) as e:
        parse.parse_table(b"<p>x</p>", "table.zz")
    assert isinstance(e.value, ParseError) and str(e.value) == "selector matched nothing: table.zz"


def test_other_parse_errors_stay_plain():
    with pytest.raises(ParseError) as e:
        parse.parse_table(b"<table></table>", "table")
    assert not isinstance(e.value, SelectorMatchedNothing)


def test_rich_page_title_counts_hosts_links_candidates_size():
    o = outline(RICH, HOST)
    assert o.title == "Daily Prices: BTC, ETF flows"
    c = dict(o.counts)
    assert c["pre"] == 1 and c["ul"] == 1 and c["ol"] == 1 and c["canvas"] == 1 and c["svg"] == 1
    assert c["iframe"] == 1 and c["form"] == 1 and c["script"] == 2 and c["img"] == 1 and c["table"] == 0
    assert o.hosts == ("cdn.example.com", "stats.example.org", "frame.example.net")
    assert o.links == ("files/data.csv", "export/series.json")
    assert [(t, k, n) for t, k, n in o.candidates] == [("div", "#grid", 25)]
    assert o.size == len(RICH)
    text = "\n".join(render_outline(o))
    assert "Daily Prices" in text and "cdn.example.com" in text and "files/data.csv" in text and "div#grid" in text


def test_no_page_host_keeps_relative_links_only():
    assert outline(RICH, None).links == ("files/data.csv",)


def test_page_without_signal_still_renders_size():
    body = (FIX / "plain.html").read_bytes()
    assert any(x.startswith("size:") and str(len(body)) in x for x in lines(body))


@pytest.mark.parametrize("n,kept", [(10, 10), (11, 10)])
def test_host_bound(n, kept):
    body = "".join(f'<script src="https://h{i}.example.com/a.js"></script>' for i in range(n))
    assert len(outline(body, HOST).hosts) == kept


@pytest.mark.parametrize("n,kept", [(10, 10), (11, 10)])
def test_link_bound(n, kept):
    body = "".join(f'<a href="/d/f{i}.csv">x</a>' for i in range(n))
    assert len(outline(body, HOST).links) == kept


def test_candidate_bound_15_of_16():
    body = "".join(f'<div id="c{i}">{nums(25)}</div>' for i in range(16))
    assert len(outline(body, HOST).candidates) == 15


def test_twenty_tokens_listed_nineteen_not():
    assert [n for _, _, n in outline(f'<div id="a">{nums(20)}</div>', HOST).candidates] == [20]
    assert outline(f'<div id="a">{nums(19)}</div>', HOST).candidates == ()


def test_ancestor_with_same_count_is_dropped_but_larger_is_kept():
    same = f'<div id="outer"><div id="inner">{nums(30)}</div></div>'
    assert [(k, n) for _, k, n in outline(same, HOST).candidates] == [("#inner", 30)]
    more = f'<div id="outer">{nums(5)}<div id="inner">{nums(30)}</div></div>'
    assert [k for _, k, _ in outline(more, HOST).candidates] == ["#outer", "#inner"]


def test_html_and_body_are_skipped():
    assert outline(f'<html id="h"><body id="b">{nums(40)}</body></html>', HOST).candidates == ()


def test_class_token_is_used_when_no_id():
    o = outline(f'<table class="prices big">{"<tr><td>" + nums(25) + "</td></tr>"}</table>', HOST)
    assert o.candidates and o.candidates[0][0] == "table" and o.candidates[0][1] in (".prices", ".big")
    assert any("table." in x for x in render_outline(o))


def test_only_first_two_megabytes_are_parsed():
    late = b"<script src='https://late.example.com/a.js'></script>"
    body = b"<p>" + b"x" * (2 * 1024 * 1024 + 10) + b"</p>" + late
    o = outline(body, HOST)
    assert o.size == len(body) and o.hosts == ()


def test_element_cap_and_depth_do_not_raise():
    deep = "<div>" * 200 + nums(30) + "</div>" * 200
    many = "".join(f'<span id="s{i}">1 2</span>' for i in range(5000))
    assert outline(deep, HOST).size > 0 and outline(many, HOST).size > 0


def test_outline_never_raises(monkeypatch):
    monkeypatch.setattr(parse, "Selector", lambda *a, **k: 1 / 0)
    assert render_outline(outline(b"<p>x</p>", HOST)) == ()


# ---- AC-34 -----------------------------------------------------------------------------------------------------

def test_every_line_is_printable_ascii():
    for body in (RICH, HOSTILE):
        for x in lines(body):
            assert re.fullmatch(r"[\x20-\x7e]*", x), x


def test_hostile_title_is_restricted_and_short():
    o = outline(HOSTILE, HOST)
    assert re.fullmatch(r"[A-Za-z0-9 .,:-]*", o.title) and "\x1b" not in o.title and "<" not in o.title
    long = outline(b"<title>" + b"abcd " * 100 + b"</title>", HOST)
    assert 0 < len(long.title) <= 60
    assert outline(b"<title>\x1b\x07<>!</title>", HOST).title == ""
    assert not any(x.startswith("title") for x in lines(b"<title>\x1b<>!</title><p>x</p>"))


def test_hostile_tokens_hosts_and_paths_never_appear_raw():
    text = "\n".join(lines(HOSTILE))
    for bad in ("ev il", "&quot;", "&lt;", "a<b", "8080", "secret", "pw", "Bad_Host", "evil.example.com:", "we ird", "\x1b", "?q="):
        assert bad not in text, bad


def test_page_text_and_attribute_values_never_appear():
    for body in (RICH, HOSTILE):
        text = "\n".join(lines(body))
        for bad in ("Secret narrative", "PAGETEXT_SECRET", "attrvalue_secret", "raw block", "nothing here"):
            assert bad not in text


def test_token_over_40_chars_is_not_listed():
    body = f'<div id="{"a" * 41}">{nums(25)}</div>'
    assert outline(body, HOST).candidates == ()
