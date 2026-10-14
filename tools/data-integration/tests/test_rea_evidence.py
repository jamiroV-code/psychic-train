"""S-T5a: evidence template and note rendering."""
from __future__ import annotations

import pytest

from data_integration.rea import wrapper

FOOTER = (
    "REA cannot see server-side methodology and does not search public datasets. "
    "Nothing above says how the numbers are produced on the provider's server."
)


def test_template_ends_with_footer():
    text = wrapper.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert text.rstrip().endswith(FOOTER)
    assert wrapper.EVIDENCE_FOOTER == FOOTER
    assert text.count(FOOTER) == 1
    assert text.isascii()


def test_template_has_header_fields():
    text = wrapper.TEMPLATE_PATH.read_text(encoding="utf-8")
    for ph in ["{source}", "{rea_version}", "{date}", "{command}", "{raw_output}", "{findings}"]:
        assert ph in text


def test_render_note():
    note = wrapper.render_evidence_note(
        source="demo", command="compare", date="2026-10-14", raw_output="2026-10-14/compare.json",
        findings=[("VERIFIED", "bundle exposes one export"), ("ASSUMED", "export is stable")],
    )
    assert "6.4.0" in note and "demo" in note and "2026-10-14/compare.json" in note
    assert "- VERIFIED: bundle exposes one export" in note
    assert "- ASSUMED: export is stable" in note
    assert note.rstrip().endswith(FOOTER)
    assert "{source}" not in note and "{findings}" not in note


@pytest.mark.parametrize("tag", ["verified", "MAYBE", "", "VERIFIED:"])
def test_render_rejects_bad_tag(tag):
    with pytest.raises(ValueError):
        wrapper.render_evidence_note("d", "compare", "2026-10-14", "x.json", [(tag, "t")])


def test_render_rejects_multiline_finding():
    with pytest.raises(ValueError):
        wrapper.render_evidence_note("d", "compare", "2026-10-14", "x.json", [("VERIFIED", "a\nb")])


def test_render_no_findings_still_ends_with_footer():
    note = wrapper.render_evidence_note("d", "compare", "2026-10-14", "x.json", [])
    assert note.rstrip().endswith(FOOTER)
