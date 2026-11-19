"""Parse a date of birth however a patient gives it, by typing or speaking.

normalize_dob(text) returns "YYYY-MM-DD", or None when it can't tell or the date is impossible.

Accepted, for example (all mean June 14, 1985):
  Numbers ........ 6/14/1985  06/14/85  6-14-1985  6.14.1985  6 14 1985  06141985  061485  1985-06-14  19850614
  Day first ...... 14/6/1985 (only when the first number can't be a month)
  Month names .... June 14 1985  June 14, 1985  Jun 14 85  Jun. 14th '85  14 June 1985  the 14th of June, 1985
                   June the 14th 1985  JUNE 14TH 1985  14-Jun-1985  1985 June 14
  Spanish ........ 14 de junio de 1985  junio 14, 1985
  Spoken ......... June fourteenth nineteen eighty-five  six fourteen eighty five  fourteenth of June nineteen
                   eighty five  June fourteen, nineteen eighty five
  Years in words . two thousand three  two thousand and three  twenty oh three  nineteen oh five  twenty twenty
  With filler .... DOB: 6/14/1985  I was born on June 14th, 1985  my birthday is 6/14/85  it's June 14 1985

Rules: US order (month first) unless the first number is over 12. Two-digit years are the most recent
past year ("85" is 1985, "03" is 2003). Dates in the future or more than 120 years ago are rejected.
"""
import datetime
import re

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
    # Spanish
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

_ONES = {"zero": 0, "oh": 0, "o": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
             "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
             "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
             "twentieth": 20, "thirtieth": 30}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def _words_to_numbers(tokens: list[str]) -> list[str]:
    """Turn spoken numbers into digits: 'nineteen eighty five' -> '1985', 'fourteenth' -> '14'."""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in _TENS:                                   # twenty / twenty five / twenty fifth
            val = _TENS[t]
            if i + 1 < len(tokens) and (tokens[i + 1] in _ONES or tokens[i + 1] in _ORDINALS) and \
                    0 < _ONES.get(tokens[i + 1], _ORDINALS.get(tokens[i + 1], 0)) < 10:
                val += _ONES.get(tokens[i + 1], _ORDINALS.get(tokens[i + 1]))
                i += 1
            out.append(str(val))
        elif t in _ONES and i + 1 < len(tokens) and tokens[i + 1] == "thousand":   # two thousand (and) three
            val = _ONES[t] * 1000
            i += 2
            if i < len(tokens) and tokens[i] == "and":
                i += 1
            rest = _words_to_numbers(tokens[i:i + 2])
            if rest and rest[0].isdigit() and int(rest[0]) < 100:
                val += int(rest[0])
                i += 2 if (i + 1 < len(tokens) and tokens[i] in _TENS and tokens[i + 1] in _ONES) else 1
            out.append(str(val))
            continue
        elif t in ("oh", "o") and out and i + 1 < len(tokens) and tokens[i + 1] in _ONES:   # nineteen oh five
            out.append("0" + str(_ONES[tokens[i + 1]]))
            i += 1
        elif t in _ONES:
            out.append(str(_ONES[t]))
        elif t in _ORDINALS:
            out.append(str(_ORDINALS[t]))
        else:
            out.append(t)
        i += 1
    # Spoken years come in two halves: "19" "85" -> "1985", "20" "03" -> "2003", "20" "20" -> "2020"
    merged: list[str] = []
    for tok in out:
        if (merged and merged[-1] in ("19", "20") and tok.isdigit() and len(tok) <= 2
                and (len(tok) == 2 or tok.startswith("0") or int(tok) >= 10)):
            merged[-1] = merged[-1] + tok.zfill(2)
        else:
            merged.append(tok)
    return merged


def _year(y: str) -> int:
    n = int(y)
    if len(y) <= 2:
        this = datetime.date.today().year
        n += 2000 if 2000 + n <= this else 1900
    return n


def _build(year: int, month: int, day: int) -> str | None:
    try:
        d = datetime.date(year, month, day)
    except ValueError:
        return None
    today = datetime.date.today()
    if d > today or d.year < today.year - 120:
        return None
    return d.isoformat()


def normalize_dob(value: str) -> str | None:
    if not value:
        return None
    text = value.lower().strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):                       # ISO, the model's usual form
        y, m, d = text.split("-")
        return _build(int(y), int(m), int(d))
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text)                      # 14th -> 14
    text = re.sub(r"'(\d{2})\b", r"\1", text)                               # '85 -> 85
    text = re.sub(r"(\d)\s*-\s*([a-z])", r"\1 \2", text)                    # 14-jun -> 14 jun
    text = re.sub(r"([a-z])\s*-\s*(\d)", r"\1 \2", text)
    text = re.sub(r"[-/.,]", " ", text) if re.search(r"[a-z]", text) else re.sub(r"[-.,\s]+", "/", text)
    tokens = re.findall(r"[a-z]+|\d+|/", text)
    tokens = [t for t in _words_to_numbers([t for t in tokens if t != "/"])] if re.search(r"[a-z]", text) \
        else [t for t in tokens if t != "/"]

    month = next((MONTHS[t] for t in tokens if t in MONTHS), None)
    nums = [t for t in tokens if t.isdigit()]

    if month is None and len(nums) == 1:                                    # 06141985, 061485, 19850614
        n = nums[0]
        if len(n) == 8 and n[:2] in ("19", "20") and int(n[4:6]) <= 12:
            return _build(int(n[:4]), int(n[4:6]), int(n[6:]))
        if len(n) == 8:
            return _build(int(n[4:]), int(n[:2]), int(n[2:4]))
        if len(n) == 6:
            return _build(_year(n[4:]), int(n[:2]), int(n[2:4]))
        return None

    if month is not None:                                                   # June 14 1985, 14 de junio de 1985
        if len(nums) != 2:
            return None
        a, b = nums
        if len(a) == 4:                                                     # 1985 June 14
            return _build(int(a), month, int(b))
        if len(b) == 4 or int(a) <= 31:
            return _build(_year(b), month, int(a))
        return None

    if len(nums) != 3:
        return None
    a, b, c = nums
    if len(a) == 4:                                                         # 1985/06/14
        return _build(int(a), int(b), int(c))
    if int(a) > 12 and int(b) <= 12:                                        # 14/6/1985: day first
        return _build(_year(c), int(b), int(a))
    return _build(_year(c), int(a), int(b))                                 # US: month first
