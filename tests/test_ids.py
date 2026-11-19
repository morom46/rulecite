import pytest

from rulecite.ids import cite, find_references, parse_id, split_citation, strip_type


@pytest.mark.parametrize("text, kind, chapter, section", [
    ("DISP 1.6.2", "rule", "DISP 1", "DISP 1.6"),
    ("DISP 1.6.2A", "rule", "DISP 1", "DISP 1.6"),
    ("DISP 1.1.10AB", "rule", "DISP 1", "DISP 1.1"),
    ("PRIN 2A.2.1", "rule", "PRIN 2A", "PRIN 2A.2"),
    ("DISP 1.1.5-A", "rule", "DISP 1", "DISP 1.1"),
    ("PRIN 3.4.-1", "rule", "PRIN 3", "PRIN 3.4"),
    ("DISP App 3.2.1", "app", "DISP App 3", "DISP App 3.2"),
    ("DISP 1 Annex 1", "annex", "DISP 1", "DISP 1 Annex 1"),
    ("DISP App 4 Annex 1", "annex", "DISP App 4", "DISP App 4 Annex 1"),
    ("DISP Sch 3.1", "sch", "DISP Sch 3", "DISP Sch 3"),
    ("BCOBS Sch 3", "sch", "BCOBS Sch 3", "BCOBS Sch 3"),
    ("BCOBS TP 1", "tp", "BCOBS TP 1", "BCOBS TP 1"),
    ("DISP INTRO 1.1", "intro", "DISP INTRO 1", "DISP INTRO 1"),
])
def test_parse_id(text, kind, chapter, section):
    pid = parse_id(text)
    assert (pid.kind, pid.chapter, pid.section, pid.book) == (kind, chapter, section,
                                                              text.split()[0])


def test_parse_id_normalises_spaces():
    assert parse_id("DISP  1.6.2 ").text == "DISP 1.6.2"


@pytest.mark.parametrize("bad", ["DISP", "1.6.2", "disp 1.6.2", "DISP 1.6.2 R extra"])
def test_parse_id_rejects(bad):
    with pytest.raises(ValueError):
        parse_id(bad)


def test_cite():
    assert cite("DISP 1.6.2", "R") == "DISP 1.6.2R"
    assert cite("DISP 1 Annex 1", "") == "DISP 1 Annex 1"


@pytest.mark.parametrize("text, known, expected", [
    ("DISP 1.6.2 R", set(), ("DISP 1.6.2", "R")),
    ("DISP 1.6.2R", set(), ("DISP 1.6.2", "R")),
    ("DISP 1.6.2AR", set(), ("DISP 1.6.2A", "R")),
    ("DISP 1.6.2", set(), ("DISP 1.6.2", "")),
    ("DISP 1.6.2D", {"DISP 1.6.2D"}, ("DISP 1.6.2D", "")),
    ("DISP 1.6.2D", {"DISP 1.6.2"}, ("DISP 1.6.2", "D")),
])
def test_split_citation(text, known, expected):
    assert split_citation(text, known) == expected


def test_find_references():
    text = ("Subject to DISP 1.6.2AR, see DISP 2.8.2 R or DISP 2.8.7R, COBS 4.7.1 R "
            "and DISP 1 Annex 3R, but not the chapter SYSC 4 or the section DISP 1.6.")
    assert find_references(text) == ["DISP 1.6.2AR", "DISP 2.8.2", "DISP 2.8.7",
                                      "COBS 4.7.1", "DISP 1 Annex 3"]
    # Known IDs settle a letter that could belong to the ID or be the type.
    assert find_references(text, known={"DISP 1.6.2A"})[0] == "DISP 1.6.2A"


def test_find_references_no_repeats():
    assert find_references("DISP 1.1.1R and again DISP 1.1.1 R") == ["DISP 1.1.1"]


@pytest.mark.parametrize("ref, known, expected", [
    ("DISP 2.8.7R", set(), "DISP 2.8.7"),
    ("DISP 1.6.2AR", set(), "DISP 1.6.2AR"),
    ("DISP 1.6.2AR", {"DISP 1.6.2A"}, "DISP 1.6.2A"),
    ("DISP 1.1.10D", {"DISP 1.1.10D"}, "DISP 1.1.10D"),
    ("DISP 1 Annex 3R", set(), "DISP 1 Annex 3"),
])
def test_strip_type(ref, known, expected):
    assert strip_type(ref, known) == expected
