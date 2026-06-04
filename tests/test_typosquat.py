from pkgguard.checks.typosquat import _canonical, _closest, _levenshtein, _load


def test_levenshtein_bounded():
    assert _levenshtein("requests", "requests") == 0
    assert _levenshtein("reqeusts", "requests") == 2   # transposition = 2 edits
    assert _levenshtein("requets", "requests") == 1     # one omission
    assert _levenshtein("totally", "different", cap=3) == 4  # exceeds cap


def test_canonical_collapses_separators():
    assert _canonical("beautiful-soup_4.0") == "beautifulsoup40"


def test_closest_finds_popular_lookalike():
    popular = _load("popular_pypi.txt")
    assert popular, "popular pypi list should load"
    # exact popular name -> distance 0
    assert _closest("requests", popular) == ("requests", 0)
    # near miss -> small distance to requests
    match = _closest("reqeusts", popular)
    assert match is not None and match[0] == "requests" and match[1] <= 2


def test_closest_returns_none_for_unrelated():
    popular = _load("popular_pypi.txt")
    assert _closest("my-very-unique-internal-tool-xyz", popular) is None


def test_homoglyph_fold_catches_digit_substitution():
    popular = _load("popular_pypi.txt")
    m1 = _closest("dj4ng0", popular)
    assert m1 is not None and m1[0] == "django"
    m2 = _closest("reque5t5", popular)
    assert m2 is not None and m2[0] == "requests"


def test_homoglyph_no_false_positive_on_clean_name():
    popular = _load("popular_pypi.txt")
    assert _closest("internal-data-pipeline", popular) is None
