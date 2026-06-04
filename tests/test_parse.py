from pkgguard.models import Ecosystem
from pkgguard.parse import parse_input


def names(items):
    return {(str(i.ecosystem), i.name) for i in items}


def test_requirements_parsing():
    text = "requests==2.31.0\nnumpy>=1.26\nFlask\n# comment\n"
    items = parse_input(text, fmt="requirements")
    n = names(items)
    assert ("pypi", "requests") in n
    assert ("pypi", "numpy") in n
    assert ("pypi", "Flask") in n
    req = next(i for i in items if i.name == "requests")
    assert req.version == "2.31.0"


def test_package_json_parsing():
    text = '{"dependencies":{"express":"^4.18.0","left-pad":"1.3.0"},"devDependencies":{"jest":"^29"}}'
    items = parse_input(text, fmt="package-json")
    n = names(items)
    assert ("npm", "express") in n
    assert ("npm", "left-pad") in n
    assert ("npm", "jest") in n
    lp = next(i for i in items if i.name == "left-pad")
    assert lp.version == "1.3.0"


def test_chat_text_extracts_install_and_repo():
    text = (
        "Install with: pip install requests pandas==2.1.0\n"
        "Repo: https://github.com/psf/requests\n"
        "Also `numpy` and try `scikit-learn`.\n"
    )
    items = parse_input(text, fmt="chat")
    n = names(items)
    assert ("pypi", "requests") in n        # from pip install
    assert ("pypi", "pandas") in n
    assert ("github", "psf/requests") in n  # from URL
    assert ("unknown", "numpy") in n        # from code span, ecosystem unknown
    assert ("unknown", "scikit-learn") in n


def test_chat_text_ignores_prose_stopwords():
    text = "You should install the packages and use them with your project.\n"
    items = parse_input(text, fmt="chat")
    # No bullet/code/install — nothing high-signal to extract.
    assert items == [] or all(i.name not in {"the", "and", "your"} for i in items)


def test_auto_detect_package_json():
    text = '{"name":"x","dependencies":{"react":"^18"}}'
    items = parse_input(text)  # auto
    assert names(items) == {("npm", "react")}


def test_list_with_github_slug_and_scoped_npm():
    items = parse_input("requests\nopenai/openai-python\n@types/node", fmt="list")
    n = names(items)
    assert ("github", "openai/openai-python") in n
    assert ("npm", "@types/node") in n


def test_cargo_toml_parsing():
    text = (
        "[dependencies]\n"
        'serde = "1.0"\n'
        'tokio = { version = "1" }\n'
        "[dependencies.rand]\n"
        'version = "0.8"\n'   # property, not a crate
        "[dev-dependencies]\n"
        'criterion = "0.5"\n'
    )
    n = names(parse_input(text, fmt="cargo"))
    assert ("crates", "serde") in n
    assert ("crates", "tokio") in n
    assert ("crates", "rand") in n
    assert ("crates", "criterion") in n
    assert ("crates", "version") not in n  # sub-table property must be ignored


def test_gemfile_parsing():
    text = "source 'https://rubygems.org'\ngem 'rails', '~> 7'\ngem 'puma'\n"
    n = names(parse_input(text, fmt="gemfile"))
    assert ("rubygems", "rails") in n
    assert ("rubygems", "puma") in n


def test_gomod_parsing():
    text = "module x\ngo 1.21\nrequire (\n  github.com/gin-gonic/gin v1.9.1\n  golang.org/x/text v0.14.0\n)\n"
    n = names(parse_input(text, fmt="go-mod"))
    assert ("go", "github.com/gin-gonic/gin") in n
    assert ("go", "golang.org/x/text") in n
