"""Test Level 1 — heading_parser.parse_sections."""

from __future__ import annotations

from app.indexing.heading_parser import parse_sections


def test_nested_headings_chain():
    text = "# A\n\nx\n\n## B\n\ny\n\n### C\n\nz\n"
    sections = parse_sections(text)

    chains = [s.headings for s in sections]
    bodies = [s.body.strip() for s in sections]

    assert bodies == ["x", "y", "z"]
    assert chains[0] == {"h1": "A"}
    assert chains[1] == {"h1": "A", "h2": "B"}
    assert chains[2] == {"h1": "A", "h2": "B", "h3": "C"}


def test_higher_heading_resets_deeper_levels():
    text = "# A\n\nx\n\n## B\n\ny\n\n# C\n\nz\n"
    sections = parse_sections(text)

    # Sau khi gặp lại "# C", h2 phải bị xoá khỏi chain.
    assert sections[-1].headings == {"h1": "C"}
    assert sections[-1].body.strip() == "z"


def test_empty_body_between_consecutive_headings_skipped():
    text = "# A\n## B\n\nbody\n"
    sections = parse_sections(text)

    assert len(sections) == 1
    assert sections[0].headings == {"h1": "A", "h2": "B"}
    assert sections[0].body.strip() == "body"


def test_deep_six_levels():
    text = "# 1\n## 2\n### 3\n#### 4\n##### 5\n###### 6\n\nleaf\n"
    sections = parse_sections(text)

    assert len(sections) == 1
    assert sections[0].headings == {
        "h1": "1", "h2": "2", "h3": "3", "h4": "4", "h5": "5", "h6": "6",
    }


def test_offsets_match_source_text():
    text = "# A\n\nĐoạn một.\n\n## B\n\nĐoạn hai.\n"
    sections = parse_sections(text)

    for section in sections:
        # Offset phải khớp tuyệt đối với text gốc.
        assert text[section.abs_start : section.abs_end] == section.body


def test_seven_hashes_not_heading():
    # 7 dấu # không phải heading hợp lệ (tối đa h6) -> coi là body.
    text = "# A\n\n####### khong phai heading\n"
    sections = parse_sections(text)

    assert len(sections) == 1
    assert "####### khong phai heading" in sections[0].body
