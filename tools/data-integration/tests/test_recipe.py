"""recipe.py: a recipe is data only; every field is checked before any path, SQL or network use."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_integration import recipe
from data_integration.recipe import RecipeError, load_recipe

EXAMPLE = Path(__file__).resolve().parents[1] / "recipes" / "example.recipe.json"


def good(**over):
    data = {
        "schema_version": 1, "source": "example-src", "tier": 1, "url": "https://example.test/data/prices.html",
        "selector": "table.prices", "dataset": {"symbol": "BTC-HIST", "timeframe": "1d"}, "min_rows": 2,
    }
    data.update(over)
    return data


def write(tmp_path, data, raw=None):
    p = tmp_path / "r.recipe.json"
    p.write_text(raw if raw is not None else json.dumps(data), encoding="utf-8")
    return p


def test_example_recipe_loads():
    r = load_recipe(EXAMPLE)
    assert (r.source, r.tier, r.symbol, r.timeframe) == ("example-src", 1, "BTC-HIST", "1d")
    assert r.url.startswith("https://example.test/")


def test_valid_recipe_without_politeness(tmp_path):
    r = load_recipe(write(tmp_path, good()))
    assert r.politeness is None and r.min_rows == 2


@pytest.mark.parametrize("symbol", ["..\\x", "BTC\n", "btc", "CON", "NUL", "COM1", "LPT9", "NUL.txt", "", "A" * 33, "-BTC", "BTC/X"])
def test_bad_symbols_rejected(tmp_path, symbol):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(dataset={"symbol": symbol, "timeframe": "1d"})))


def test_btc_hist_accepted(tmp_path):
    assert load_recipe(write(tmp_path, good())).symbol == "BTC-HIST"


@pytest.mark.parametrize("tf", ["5m", "1D", "", "1d ", 5, None])
def test_bad_timeframes_rejected(tmp_path, tf):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(dataset={"symbol": "BTC", "timeframe": tf})))


@pytest.mark.parametrize("tf", ["15m", "1h", "4h", "1d", "1w"])
def test_good_timeframes(tmp_path, tf):
    assert load_recipe(write(tmp_path, good(dataset={"symbol": "BTC", "timeframe": tf}))).timeframe == tf


def test_oversize_file_rejected_before_read(tmp_path, monkeypatch):
    p = write(tmp_path, good(), raw=" " * (16 * 1024 + 1))
    monkeypatch.setattr(Path, "read_bytes", lambda self: (_ for _ in ()).throw(AssertionError("read before size check")))
    with pytest.raises(RecipeError):
        load_recipe(p)


def test_missing_and_directory_rejected(tmp_path):
    with pytest.raises(RecipeError):
        load_recipe(tmp_path / "nope.json")
    with pytest.raises(RecipeError):
        load_recipe(tmp_path)


@pytest.mark.parametrize("raw", ["not json", "[1]", "null", '"x"', "{"])
def test_not_an_object_rejected(tmp_path, raw):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, None, raw=raw))


def test_invalid_utf8_rejected(tmp_path):
    p = tmp_path / "r.json"
    p.write_bytes(b"\xff\xfe{}")
    with pytest.raises(RecipeError):
        load_recipe(p)


def test_unknown_top_level_key_rejected(tmp_path):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(proxy="x")))


def test_unknown_dataset_key_rejected(tmp_path):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(dataset={"symbol": "BTC", "timeframe": "1d", "x": 1})))


def test_duplicate_key_rejected(tmp_path):
    raw = json.dumps(good()).replace('"tier": 1', '"tier": 1, "tier": 2')
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, None, raw=raw))


def test_missing_key_rejected(tmp_path):
    data = good()
    del data["selector"]
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, data))


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_nan_and_infinity_rejected(tmp_path, token):
    raw = json.dumps(good(politeness={"min_delay": 2.0})).replace("2.0", token)
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, None, raw=raw))


@pytest.mark.parametrize("field", ["schema_version", "tier", "min_rows"])
def test_bool_as_int_rejected(tmp_path, field):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(**{field: True})))


@pytest.mark.parametrize("version", [0, 2, "1", 1.0, None])
def test_schema_version_must_be_one(tmp_path, version):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(schema_version=version)))


@pytest.mark.parametrize("tier", [0, 4, "1", 1.5, None])
def test_bad_tier_rejected(tmp_path, tier):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(tier=tier)))


@pytest.mark.parametrize("source", ["Bad Src", "", "con", "a/b", "UPPER", 5])
def test_bad_source_rejected(tmp_path, source):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(source=source)))


@pytest.mark.parametrize("rows", [1, 0, 100001, 2.5, "2", None])
def test_bad_min_rows_rejected(tmp_path, rows):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(min_rows=rows)))


@pytest.mark.parametrize("rows", [2, 100000])
def test_min_rows_bounds_accepted(tmp_path, rows):
    assert load_recipe(write(tmp_path, good(min_rows=rows))).min_rows == rows


@pytest.mark.parametrize("url", [
    "ftp://example.test/data/", "file:///etc/passwd", "https://user:pw@example.test/data/", "https:///data/",
    "example.test/data/", "https://example.test/" + "a" * 2048, "", 5, None, "https://exa mple.test/",
])
def test_bad_urls_rejected(tmp_path, url):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(url=url)))


def test_http_url_accepted(tmp_path):
    assert load_recipe(write(tmp_path, good(url="http://example.test/data/x"))).url.startswith("http://")


@pytest.mark.parametrize("sel", ["", "a\nb", "a\x00b", "a\x7fb", "x" * 501, 5, None])
def test_bad_selectors_rejected(tmp_path, sel):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(selector=sel)))


def test_selector_500_accepted(tmp_path):
    assert len(load_recipe(write(tmp_path, good(selector="x" * 500))).selector) == 500


@pytest.mark.parametrize("pol", [
    {"min_delay": 0.5}, {"min_delay": 0}, {"min_delay": 3601}, {"min_delay": True}, {"min_delay": "2"},
    {"min_delay": 1e999}, {"max_concurrent": 3}, {"max_concurrent": 0}, {"max_concurrent": 1.5}, {"max_concurrent": True},
    {"max_per_host": 2}, {"max_per_host": 0}, {"delay": 2}, "fast", [], None,
])
def test_loosening_or_bad_politeness_rejected(tmp_path, pol):
    with pytest.raises(RecipeError):
        load_recipe(write(tmp_path, good(politeness=pol)))


def test_tighter_politeness_accepted(tmp_path):
    pol = {"min_delay": 3600, "max_concurrent": 2, "max_per_host": 1}
    r = load_recipe(write(tmp_path, good(politeness=pol)))
    assert r.politeness == {"min_delay": 3600.0, "max_concurrent": 2, "max_per_host": 1}


def test_partial_politeness_fills_defaults(tmp_path):
    r = load_recipe(write(tmp_path, good(politeness={"min_delay": 5})))
    assert r.politeness == {"min_delay": 5.0, "max_concurrent": 2, "max_per_host": 1}


def test_error_message_never_echoes_path(tmp_path):
    with pytest.raises(RecipeError) as exc:
        load_recipe(tmp_path / "secret-dir" / "x.json")
    assert str(tmp_path) not in str(exc.value)


def test_recipe_module_has_error_class():
    assert issubclass(recipe.RecipeError, ValueError)
