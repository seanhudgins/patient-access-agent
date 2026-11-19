"""Verification must accept the ways people actually type their name and date of birth.

Run: uv run python tests/test_verify.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import tools  # noqa: E402

# Every way we've thought of to say June 14, 1985: typed, spoken (phone channel), Spanish, with filler words.
DOB_FORMATS = [
    "6/14/1985", "06/14/1985", "6/14/85", "06/14/85", "6-14-1985", "6.14.1985", "6 14 1985", "06141985", "061485",
    "1985-06-14", "19850614", "1985/06/14", "1985.6.14", "14/6/1985", "14.06.1985", "14-06-85",
    "June 14 1985", "June 14, 1985", "june 14th, 1985", "Jun 14 85", "Jun. 14th '85", "14 June 1985",
    "the 14th of June, 1985", "June the 14th 1985", "JUNE 14TH 1985", "14-Jun-1985", "1985 June 14", "14 June '85",
    "June 14 '85", "Jun-14-1985", "14 de junio de 1985", "junio 14, 1985", "14 junio 1985",
    "June fourteenth nineteen eighty-five", "six fourteen eighty five", "fourteenth of June nineteen eighty five",
    "June fourteen, nineteen eighty five", "june fourteenth, eighty five", "6 14 eighty five",
    "DOB: 6/14/1985", "I was born on June 14th, 1985", "my birthday is 6/14/85", "it's June 14 1985", "born 6-14-85",
]

OTHER_DATES = {
    "March 3rd, two thousand three": "2003-03-03", "march third two thousand and three": "2003-03-03",
    "3/3/03": "2003-03-03", "January fifth nineteen twenty five": "1925-01-05", "Feb 29 2000": "2000-02-29",
    "December twenty fifth twenty twenty": "2020-12-25", "sept 9 1990": "1990-09-09", "9/10/1990": "1990-09-10",
    "twenty first of march nineteen ninety": "1990-03-21", "thirty first december nineteen ninety nine": "1999-12-31",
    "octubre 3 de 1979": "1979-10-03",
}


def test_dob_formats():
    for d in DOB_FORMATS:
        assert tools.normalize_dob(d) == "1985-06-14", d


def test_other_dates():
    for text, want in OTHER_DATES.items():
        assert tools.normalize_dob(text) == want, (text, tools.normalize_dob(text))


def test_bad_dates_rejected():
    # impossible, future, too old, incomplete, or not a date
    for d in ["2/30/1985", "Feb 29 2001", "13/13/1985", "13/45/1985", "6/14/2099", "6/14/1850", "July 4", "1985",
              "two thousand three", "hello", ""]:
        assert tools.normalize_dob(d) is None, d


def test_sarah_verifies_with_any_format_and_case():
    for d in DOB_FORMATS:
        s = tools.new_session()
        assert tools.verify_patient("sarah", " Bellum ", d, s)["success"], d


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
