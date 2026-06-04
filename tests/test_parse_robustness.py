"""Regression tests for parser edge cases found in adversarial review."""

from pkgguard.parse import parse_input


def names(text, fmt="chat"):
    return {(str(i.ecosystem), i.name) for i in parse_input(text, fmt=fmt)}


def test_prose_bullets_are_not_packages():
    text = (
        "- Note that this requires Python 3.8+.\n"
        "- Make sure pip is installed.\n"
        "- Check out the docs.\n"
        "- flask\n"
        "- some-cool-pkg\n"
    )
    n = names(text)
    assert ("unknown", "Note") not in n
    assert ("unknown", "Make") not in n
    assert ("unknown", "Check") not in n
    assert ("unknown", "flask") in n
    assert ("unknown", "some-cool-pkg") in n


def test_emphasized_titlecase_package_kept():
    assert ("unknown", "Django") in names("- **Django** is a great web framework")


def test_pip_install_inside_backticks():
    # The most common LLM presentation; the package must still be captured.
    assert ("pypi", "requests") in names("Install with `pip install requests`.")


def test_pip_install_dash_r_does_not_create_phantom():
    n = names("Run `pip install -r requirements.txt` then go.")
    assert ("pypi", "requirements.txt") not in n
    assert ("pypi", "then") not in n
    assert ("pypi", "go") not in n


def test_trailing_prose_after_install_ignored():
    n = names("pip install requests pandas numpy then run it")
    assert ("pypi", "requests") in n
    assert ("pypi", "pandas") in n
    assert ("pypi", "numpy") in n
    assert ("pypi", "then") not in n and ("pypi", "it") not in n


def test_scoped_npm_in_code_span():
    n = names("Use `@vue/cli` and `@types/node`.")
    assert ("npm", "@vue/cli") in n
    assert ("npm", "@types/node") in n


def test_non_ascii_name_not_truncated():
    # "Děčín" must NOT be silently vetted as "D".
    n = names("Děčín==1.0\nrequests==2.0", fmt="requirements")
    assert ("pypi", "requests") in n
    assert ("pypi", "D") not in n


def test_empty_and_whitespace_input():
    assert parse_input("", fmt="chat") == []
    assert parse_input("   \n\t\n", fmt="auto") == []


def test_git_url_in_chat_still_captured():
    n = names("Try `pip install git+https://github.com/psf/requests`")
    assert ("github", "psf/requests") in n
